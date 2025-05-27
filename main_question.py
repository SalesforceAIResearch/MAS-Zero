import argparse
from datasets import load_dataset
import pandas as pd
from common import HTML_JINJA, SingleEvalResult
import search
import re
import common
from common import ANSWER_PATTERN, check_equality
from sampler.chat_completion_sampler import ChatCompletionSampler
from sampler.o_chat_completion_sampler import OChatCompletionSampler
from sampler.together_completion_sampler import ChatCompletionSampler as ToChatCompletionSampler
from sampler.vllm_completion_sampler import ChatCompletionSampler as VllmChatCompletionSampler
import json
from utils import load_questions
from prompts.swe.patch_oracle import AGENTLESS_REPAIR
from swe_utils import run_swebench_evaluation, sanity_check
from utils import  extract_xml
from shared_vars import set_global, get_global

parser = argparse.ArgumentParser()
parser.add_argument('--valid_size', type=int, default=128)
parser.add_argument('--test_size', type=int, default=800)
parser.add_argument('--shuffle_seed', type=int, default=0)
parser.add_argument('--n_repeats', type=int, default=1)
parser.add_argument('--multiprocessing', action='store_true', default=True)
parser.add_argument('--max_workers', type=int, default=48)
parser.add_argument('--debug', action='store_true', default=True)
parser.add_argument('--save_dir', type=str, default='results/')
parser.add_argument('--expr_name', type=str)
parser.add_argument('--n_generation', type=int, default=10)
parser.add_argument('--max_round', type=int, default=5)
parser.add_argument('--max_sc', type=int, default=5)
parser.add_argument('--debug_max', type=int, default=3)
parser.add_argument('--option', type=str, default='')
parser.add_argument('--meta_model',
                    type=str)
parser.add_argument('--node_model',
                    type=str)
parser.add_argument('--verifier_model',
                    type=str,
                    default="o3-mini")
                    # gpt-4o
parser.add_argument('--shorten_context', action='store_true')
parser.add_argument('--merge_context', action='store_true')

                    
parser.add_argument(
    "--blocks", type=str, nargs="*", help="Number of examples to use (overrides default)"
)
parser.add_argument('--dataset', type=str)
parser.add_argument(
    "--given_examples", type=int, nargs="*", help="Number of examples to use (overrides default)"
)
parser.add_argument(
    "--use_oracle_verifier", action='store_true'
)
parser.add_argument(
    "--defer_verifier", action='store_true'
)
parser.add_argument(
    "--no_decompose", action='store_true'
)
parser.add_argument(
    "--no_meta_reward", action='store_true'
)

class DataScorer:

    def __init__(self, dataset, technique):
        self.dataset = dataset
        self.technique = technique
        self.equality_checker = ChatCompletionSampler(model="gpt-4-turbo-preview")
        self.LETTER_TO_INDEX = {'A': 0, 'B': 1, 'C': 2, 'D': 3}


    def run_score(self, answer, extracted_answer, use_oracle_verifier, judge_path, instance_id, n, code_snippet):

        if 'swe_bench' in self.dataset:
            score, percentage, passed_tests, total_tests = run_swebench_evaluation(judge_path, instance_id, extracted_answer, self.technique, n, code_snippet)

            with open(judge_path, 'a+') as judge_file:
                judge_file.write(f'{instance_id} → {passed_tests} passed test | {total_tests} total_tests | {passed_tests}/{total_tests} passed → {percentage:.1f}% | Score: {score}\n')

            return score

        elif 'aime24' in self.dataset:
            return float(check_equality(self.equality_checker, answer, extracted_answer, use_oracle_verifier=True, judge_path=judge_path))
        elif 'gpqa_diamond' in self.dataset:
            
            res = extracted_answer
            is_early_stop = False
            try:
                if isinstance(res, str) and res in self.LETTER_TO_INDEX:
                    predicted_idx = self.LETTER_TO_INDEX[res]
                elif 'A)' in res:
                    predicted_idx = 0
                elif 'B)' in res:
                    predicted_idx = 1
                elif 'C)' in res:
                    predicted_idx = 2
                elif 'D)' in res:
                    predicted_idx = 3
                elif isinstance(res, list):
                    try_res = res[1]
                    predicted_idx = self.LETTER_TO_INDEX[try_res.content]
                elif res.content in self.LETTER_TO_INDEX:
                    predicted_idx = self.LETTER_TO_INDEX[res.content]
                elif 'A)' in res.content:
                    predicted_idx = 0
                elif 'B)' in res.content:
                    predicted_idx = 1
                elif 'C)' in res.content:
                    predicted_idx = 2
                elif 'D)' in res.content:
                    predicted_idx = 3
                else:
                    print(f"error in q {q_idx}")
                    score = 0
                    is_early_stop = True
            except Exception as e:
                score = 0
                is_early_stop = True

            if not is_early_stop: # if cannot find predicted_idx, then done
                if predicted_idx == answer:
                    score = 1
                else:
                    score = 0

            print(f'extracted_answer: {extracted_answer}; answer: {answer}; score: {score}')

            return score
        
        else:
            raise NotImplementedError

    def score(self, example_id, n, prompt_message, question, response_text, answer, sub_tasks_text, use_oracle_verifier, judge_path, response_path, response_dict, instance_id, code_snippet):

        if 'swe_bench' in self.dataset:
            extracted_answer = response_text.split('\n\nAnswer:', 1)[-1].strip()
            if '<patch>' in extracted_answer:
                extracted_answer = extract_xml(extracted_answer, 'patch').strip()   
        else:
            match = re.search(ANSWER_PATTERN, response_text)
            extracted_answer = match.group(1) if match else None    
            extracted_answer = extracted_answer.strip()


        print('extracted_answer: ',extracted_answer)

        with open(judge_path, 'a+') as judge_file:
            judge_file.write(f'Question: {question}\nproposed answer: {response_text}\nExtracted answer: {extracted_answer}\nCorrect answer: {answer}\n')
            
        with open(response_path, 'w') as json_file:
            response_dict.append({
                'example_id':example_id, 
                'problem': question, 
                'correct_answer': answer, 
                'n':n, 
                'response': response_text, 
                'sub_tasks_text': sub_tasks_text})

            json.dump(response_dict, json_file, indent=4)
            

        if use_oracle_verifier:
            score_oracle_verifier = self.run_score(answer, extracted_answer, use_oracle_verifier=True, judge_path=judge_path, instance_id=instance_id, n=n, code_snippet=code_snippet)
            score = score_oracle_verifier
            score_model_verifier = None 
        else:
            if sub_tasks_text is None:
                score_model_verifier = self.run_score(mode_verifier, question, response_text, use_oracle_verifier=False, judge_path=judge_path, instance_id=instance_id, n=n, code_snippet=code_snippet)
            else:
                score_model_verifier = self.run_score(mode_verifier, question, sub_tasks_text, use_oracle_verifier=False, judge_path=judge_path, instance_id=instance_id, n=n, code_snippet=code_snippet)
            score = score_model_verifier

        html = common.jinja_env.from_string(HTML_JINJA).render(
            prompt_messages=prompt_message,
            next_message=dict(content=response_text, role="assistant"),
            score=score,
            correct_answer=answer,
            extracted_answer=extracted_answer,
        )
        convo = prompt_message + [dict(content=response_text, role="assistant")]
        results = SingleEvalResult(html=html, score=score, convo=convo)
        return score_oracle_verifier, score_model_verifier, results



args = parser.parse_args()



if __name__ == "__main__":

    blocks = args.blocks
    meta_model = args.meta_model
    node_model = args.node_model
    verifier_model = args.verifier_model
    use_oracle_verifier = args.use_oracle_verifier
    max_round = args.max_round
    max_sc = args.max_sc

    SEARCHING_MODE = True

    technique = args.dataset.split('/')[0] 
    data_scorer = DataScorer(args.dataset, technique)

    print('verifier_model: ',verifier_model)
    print('technique: ',technique)
    print('node_model: ',node_model)

    model_sampler_map = {
        "o3-mini": OChatCompletionSampler(
            model="o3-mini",
        ),
        "gpt-4o_chatgpt": ChatCompletionSampler(
            model="gpt-4o",
        ),
        "qwen-2.5-32b-instr": VllmChatCompletionSampler(
            model="qwen-2.5-32b-instr",
        ),
        "qwq-32b": ToChatCompletionSampler(
            model="Qwen/Qwen2.5-32B-Instruct",
        ),
        "llama-3.3-70b-instr": ToChatCompletionSampler(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        ),
    }

    json_model = ['gpt']
    xml_model = ['qwen', 'llama-3.3']


    if any(kw in node_model for kw in json_model):

        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!\n\n"""
        set_global("global_format_choice", 'json')

    elif any(kw in node_model for kw in xml_model):
        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following XML format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object!\n\n"""
        set_global("global_format_choice", 'xml')

    else:
        raise NotImplementedError


    mode_verifier = model_sampler_map[verifier_model]

    set_global("global_FORMAT_INST", FORMAT_INST)
    set_global("global_model_sampler_map", model_sampler_map)
    set_global("global_shorten_context", args.shorten_context)
    set_global("global_merge_context", args.merge_context)
    set_global("global_COST_TOTAL", 0.0)
    set_global("global_no_decompose", args.no_decompose)
    set_global("global_no_meta_reward", args.no_meta_reward)

    print('shorten_context: ',args.shorten_context)
    print('merge_context: ',args.merge_context)
    print('global_no_meta_reward: ',args.no_meta_reward)
    print('global_no_decompose: ',args.no_decompose)


    code_snippet = None
    for n in range(args.n_repeats):


        if 'swe_bench' in args.dataset:

            cot_instruction = "Put your thinking process in the 'thinking' entry and the final patch in the 'answer' entry." #TODO: may need something for xml

            debate_role = ['Computer Science Professor', 'Software Engineer']

            # output_description = "Return ONLY an integer. DO NOT return anything other than the integer answer."
            output_description = "If the question is asked for a patch to fix an issue, Return ONLY the solution and DO NOT return anything other than the patch; If the question is asked for more than a patch, Return what the question asked and make sure the answer is complete."


            # Load SWE-bench dataset
            examples = load_dataset("princeton-nlp/SWE-bench_Lite_oracle", split="test")

            for example_id,example in enumerate(examples):

                if args.given_examples:
                    if example_id not in args.given_examples: continue                                              

                # if example_id <= 1: continue 

                args.expr_name = f'question/meta_agent/{args.dataset}/{example_id}/{meta_model}_{node_model}_{verifier_model}_{n}'
                print('args.expr_name: ',args.expr_name)

                instance_id = example['instance_id']
                example_text = example['text']

                if get_global("global_format_choice") == 'xml': # conflict with xml TODO: ADAS and OURS may also need to change
                    example_text = example_text.replace('<patch>','<answer>').replace('</patch>','</answer>')
                    example_text = example_text.replace('Please respond with a single patch file in the following format.','If asked for <answer> field, the <answer> field should be a single patch file in the following format')
                    # example_text += '\n\nIf asked for <thinking> field, you should put your thinking in the <thinking> field.'
                    cot_instruction = "Put your thinking process in the <thinking> field and the final patch in the <answer> field." #TODO: may need something for xml

                code_snippet = extract_xml(example_text, 'code').strip()
                print('code_snippet: ',code_snippet)
                
                questions = [example_text + '\n\n' + AGENTLESS_REPAIR]

                answers = [None]

                print('instance_id: ',instance_id)

                task_queue = []
                for q in questions:
                    taskInfo = ('task', 'User', q, None, None, None, -1)
                    task_queue.append(taskInfo)

                set_global("global_output_description", output_description)
                set_global("global_score_compute", data_scorer.score)
                set_global("global_max_round", max_round)
                set_global("global_max_sc", max_sc)
                set_global("global_debate_role", debate_role)
                set_global("global_cot_instruction", cot_instruction)
                set_global("global_node_model", node_model)
                set_global("global_answers", answers)
                set_global("global_questions", questions)
                set_global("global_use_oracle_verifier", use_oracle_verifier)
                set_global("global_example_id", example_id)
                set_global("global_response_dict", [])
                set_global("global_dataset", args.dataset)
                set_global("global_instance_id", instance_id)
                set_global("global_code_snippet", code_snippet)

                # search
                search.search(args, task_queue, meta_model, blocks, verifier_model)

        elif 'aime24' in args.dataset:


            cot_instruction = "Please think step by step and then solve the task."
            # output_description = "Return ONLY an integer. DO NOT return anything other than the integer answer."
            output_description = "If the question is asked for a numeric result, Return ONLY an integer and DO NOT return anything other than the integer answer; If the question is asked for more than numeric results, Return what the question asked and make sure the answer is complete."

            debate_role = ['Math Professor', 'Grade School Teacher']


            dataset = load_dataset("simplescaling/aime24_nofigures")
            df = pd.DataFrame(dataset['train'])
            examples = [row.to_dict() for _, row in df.iterrows()]

            for example_id,example in enumerate(examples):
                instance_id = example_id

                if args.given_examples:
                    if example_id not in args.given_examples: continue                                              

                args.expr_name = f'question/meta_agent/{args.dataset}/{example_id}/{meta_model}_{node_model}_{verifier_model}_{n}'
                print('args.expr_name: ',args.expr_name)

                questions = [example['problem']]
                answers = [example['answer']]

                task_queue = []
                for q in questions:
                    taskInfo = ('task', 'User', q, None, None, None, -1)
                    task_queue.append(taskInfo)


                set_global("global_output_description", output_description)
                set_global("global_score_compute", data_scorer.score)
                set_global("global_max_round", max_round)
                set_global("global_max_sc", max_sc)
                set_global("global_debate_role", debate_role)
                set_global("global_cot_instruction", cot_instruction)
                set_global("global_node_model", node_model)
                set_global("global_answers", answers)
                set_global("global_questions", questions)
                set_global("global_use_oracle_verifier", use_oracle_verifier)
                set_global("global_example_id", example_id)
                set_global("global_response_dict", [])
                set_global("global_dataset", args.dataset)
                set_global("global_instance_id", instance_id)
                set_global("global_code_snippet", code_snippet)



                # search
                search.search(args, task_queue, meta_model, blocks, verifier_model)

        elif 'gpqa_diamond' in args.dataset:


            cot_instruction = "Please think step by step and then solve the task."
            # output_description = "Return ONLY the alphabet choice, i.e. A or B or C or D."
            output_description = "If the question is asked for a multiple-choice result, Return ONLY the alphabet choice, i.e. A or B or C or D; If the question is asked for more than multiple-choice results, Return what the question asked and make sure the answer is complete."
            # need to consider sub-task output as well (no fixed form for sub-tasks)
            debate_role = ['Biology Expert', 'Physics Expert', 'Chemistry Expert', 'Science Generalist']


            # set seed 0 for valid set
            questions = load_questions('dataset/gpqa_diamond.csv', seed=0)
            answers = [question.correct_index for question in questions]

            examples = [{'problem': questions[i], 'answer': answers[i]} for i in range(len(questions))]

            for example_id, example in enumerate(examples):
                instance_id = example_id

                if args.given_examples:
                    if example_id not in args.given_examples: continue     

                args.expr_name = f'question/meta_agent/{args.dataset}/{example_id}/{meta_model}_{node_model}_{verifier_model}_{n}'
                print('args.expr_name: ',args.expr_name)

                questions = [example['problem']]
                answers = [example['answer']]

                final_question = []
                task_queue = []
                for q in questions:
                    task_content = f"What is the correct answer to this question: {q.question}" \
                                + f"\n\nChoices:\n(A) {q.choice1}\n(B) {q.choice2}\n(C) {q.choice3}\n(D) {q.choice4}"
                    taskInfo = ('task', 'User', task_content, None, None, None, -1)
                    task_queue.append(taskInfo)
                    final_question.append(task_content)

                set_global("global_output_description", output_description)
                set_global("global_score_compute", data_scorer.score)
                set_global("global_max_round", max_round)
                set_global("global_max_sc", max_sc)
                set_global("global_debate_role", debate_role)
                set_global("global_cot_instruction", cot_instruction)
                set_global("global_node_model", node_model)
                set_global("global_answers", answers)
                set_global("global_questions", final_question)
                set_global("global_use_oracle_verifier", use_oracle_verifier)
                set_global("global_example_id", example_id)
                set_global("global_response_dict", [])
                set_global("global_dataset", args.dataset)
                set_global("global_instance_id", instance_id)
                set_global("global_code_snippet", code_snippet)



                # search
                search.search(args, task_queue, meta_model, blocks, verifier_model)


        else:
            raise NotImplementedError



