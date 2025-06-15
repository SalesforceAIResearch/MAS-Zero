import argparse
import copy
import json
import os
import random
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

import backoff
import numpy as np
import openai
from tqdm import tqdm

import re

from typing import Any
from datasets import load_dataset
import pandas as pd
import common
from common import HTML_JINJA, get_init_archive, get_prompt, get_reflexion_prompt, SingleEvalResult, get_reflexion_after_eval
from common import get_json_response_from_gpt, get_json_response_from_gpt_reflect, _pack_message
from utils import random_id, bootstrap_confidence_interval
from common import ANSWER_PATTERN, shorten_context, merge_context
import copy
from prompts.swe.patch_oracle import AGENTLESS_REPAIR
from utils import  extract_xml
from shared_vars import set_global, get_global


client = openai.OpenAI()

Info = namedtuple('Info', ['name', 'author', 'content', 'prompt', 'sub_tasks', 'agents', 'iteration_idx'])

ROLE_DESC = lambda role: f"You are a {role}."
SYSTEM_MSG = ""

PRINT_LLM_DEBUG = False
SEARCHING_MODE = True

class LLMAgentBase():
    """
    Attributes:
    """

    def __init__(self, output_fields: list, agent_name: str,
                 role='helpful assistant', model=None, temperature=None) -> None:
        self.output_fields = output_fields
        self.agent_name = agent_name

        self.role = role
        self.model = model
        self.temperature = temperature
        # give each instance a unique id
        self.id = random_id()
        
    def extract_pattern(self, prompt):
        # pattern = r"\s*(.*?)\s*\n\nRelated original question"
        pattern = r"Given the above, answer the following question: \s*(.*?)\s*\n\n"

        sub_question = prompt[-1]['content']
        match = re.search(pattern, sub_question, re.DOTALL)
        extracted_question = match.group(1)

        return extracted_question

    def generate_prompt(self, input_infos, instruction, is_sub_task=False) -> str:

        global_node_model = get_global("global_node_model")
        global_output_description = get_global("global_output_description")
        global_FORMAT_INST = get_global("global_FORMAT_INST")

        global_format_choice = get_global("global_format_choice")

        if global_format_choice == 'json':
            output_fields_and_description = {key: f"Your {key}." if not 'answer' in key else f"Your {key}. {global_output_description}" for key in self.output_fields}
        elif global_format_choice == 'xml':
            output_fields_and_description = '\n'.join([f"<{key}> [Your {key}.] </{key}>" if not 'answer' in key else f"<{key}> [Your {key}. {global_output_description}] </{key}>\n" for key in self.output_fields])
        else:
            raise NotImplementedError

        system_prompt = ROLE_DESC(self.role) + "\n\n" + global_FORMAT_INST(output_fields_and_description)
        

        # construct input infos text
        input_infos_text = ''
        prev_extracted_question = ''
        for input_info in input_infos:
            if isinstance(input_info, Info):
                (field_name, author, content, prompt, _, _, iteration_idx) = input_info
            else:
                continue
            if author == self.__repr__():
                author += ' (yourself)'
            if field_name == 'task':
                if is_sub_task: 
                    input_infos_text += f'Related original question:\n\n{content}. \n\nRelated sub-task questions and answers:\n\n'
                else:
                    input_infos_text += f'{content}\n\n'
            elif iteration_idx != -1:
                if is_sub_task and prompt is not None: 
                    extracted_question = self.extract_pattern(prompt)
                    if extracted_question != prev_extracted_question:
                        input_infos_text += f'### {extracted_question} \n\n ### {field_name} #{iteration_idx + 1} by {author}:\n{content}\n\n'
                        prev_extracted_question = extracted_question
                    else:
                        input_infos_text += f'### {field_name} #{iteration_idx + 1} by {author}:\n{content}\n\n'

                else:
                    input_infos_text += f'### {field_name} #{iteration_idx + 1} by {author}:\n{content}\n\n'
            else:
                if is_sub_task and prompt is not None: 
                    extracted_question = self.extract_pattern(prompt)
                    if extracted_question != prev_extracted_question:
                        input_infos_text += f'### {extracted_question} \n\n ### {field_name} by {author}:\n{content}\n\n'
                        prev_extracted_question = extracted_question # we do not want to duplicate the prompt
                    else:
                        input_infos_text += f'### {field_name} by {author}:\n{content}\n\n'
                else:
                    input_infos_text += f'### {field_name} by {author}:\n{content}\n\n'

        if is_sub_task: 


            if global_format_choice == 'json':

                prompt = input_infos_text + f'Given the above, answer the following question: {instruction}\n\nIf the question is too complicated or informaion is missing, you still need to give your best answer but add (1) an additional mark [TOO_HARD] in the next line of your final answer (2) information request or decomposison suggestion in the next line of the [TOO_HARD] mark, in the "answer" entry (for example, 300\n[TOO_HARD]\nSuggestion:...) and justify why you think so in the "thinking" entry'# instruction (sub-task in above)

            elif global_format_choice == 'xml':

                prompt = input_infos_text + f"""Given the above, answer the following question: {instruction}\n\n 
                
                If the question is too complicated or informaion is missing, you still need to give your best guess but add (1) an additional mark [TOO_HARD] in the next line of your final answer (2) information request or decomposison suggestion in the next line of the [TOO_HARD] mark, in the "answer" entry. In the "thinking", justify why you think so. Following the format below:
                
                "answer" entry: [Your best guess, e.g., 300]\n[TOO_HARD]\nSuggestion: [your suggestion]
                "thinking" entry:  [why you thinking is is too complicated or missing information. How to you arrive your best guess regardless]

                Otherwise, give your answer and thinking normally.

                "answer" entry: [your answer]
                "thinking" entry: [How do you arrive your answer]

                IMPORTANT: You need to give your best guess in both cases. Do not give [TOO_HARD] directly but always give your best guess first

                """
            else:
                raise NotImplementedError


        else:
            prompt = input_infos_text + instruction
        return system_prompt, prompt

    def query(self, input_infos: list, instruction, iteration_idx=-1, is_sub_task=False) -> dict:
        

        system_prompt, prompt = self.generate_prompt(input_infos, instruction, is_sub_task=is_sub_task)

        prompt = [
            _pack_message(content=system_prompt, role="system"),
            _pack_message(content=prompt, role="user")]
        # use system prompt

        response_json = get_json_response_from_gpt(prompt, self.model, self.output_fields, self.temperature)

        output_infos = []
        for key, value in response_json.items():
            info = Info(key, self.__repr__(), value, prompt, None, None, iteration_idx)
            output_infos.append(info)
        return output_infos

    def __repr__(self):
        return f"{self.agent_name} {self.id}"

    def __call__(self, input_infos: list, instruction, iteration_idx=-1, is_sub_task=False):
        return self.query(input_infos, instruction, iteration_idx=iteration_idx,  is_sub_task=is_sub_task)




class AgentSystem():
    def __init__(self) -> None:
        pass

    def make_final_answer(self, thinking, answer, sub_tasks=None, agents=None):

        name = thinking.name
        author = thinking.author
        prompt = thinking.prompt
        iteration_idx = thinking.iteration_idx

        if type(answer) == str:
            answer_content = answer
        else:
            answer_content = answer.content

        if agents is None: # this means sub_task is None, according to the propose prompt
            sub_tasks, agents = agents, sub_tasks

        if sub_tasks is None and agents is None:
            final_answer = Info(name, author, f'{thinking.content}\n\nAnswer:{answer_content}', prompt, None, None, iteration_idx)
        elif agents is not None: # when remove decomposition, we still have agent output logged
            final_answer = Info(name, author, f'{thinking.content}\n\nAnswer:{answer_content}', prompt, None, '\n'.join(agents), iteration_idx)
        else:
            final_answer = Info(name, author, f'{thinking.content}\n\nAnswer:{answer_content}', prompt, '\n'.join(sub_tasks), '\n'.join(agents), iteration_idx)
        return final_answer

def evaluate_forward_fn(args, forward_str):
    # dynamically define forward()
    # modified from https://github.com/luchris429/DiscoPOP/blob/main/scripts/launch_evo.py


    print('forward_str: ',forward_str)

    # if you want debug, remove the section so that you can see the detailed error line
    namespace = {}
    exec(forward_str, globals(), namespace)
    names = list(namespace.keys())
    if len(names) != 1:
        raise AssertionError(f"{len(names)} things in namespace. Please only provide 1")
    func = namespace[names[0]]
    if not callable(func):
        raise AssertionError(f"{func} is not callable")
    setattr(AgentSystem, "forward", func)

    agentSystem = AgentSystem()

    global_max_workers = get_global("global_max_workers")
    global_task_queue = get_global("global_task_queue")
    global_answers = get_global("global_answers")

    agentSystem.node_model = get_global("global_node_model")
    agentSystem.cot_instruction = get_global("global_cot_instruction")
    agentSystem.max_sc = get_global("global_max_sc")
    agentSystem.max_round = get_global("global_max_round")
    agentSystem.debate_role = get_global("global_debate_role")
    agentSystem.dataset = get_global("global_dataset")
    agentSystem.example_id = get_global("global_example_id")
    agentSystem.instance_id = get_global("global_instance_id")


    with ThreadPoolExecutor(max_workers=global_max_workers) as executor:
        results = list(tqdm(executor.map(agentSystem.forward, global_task_queue), total=len(global_task_queue)))


    prompt_messages = [res.prompt for q_idx, res in enumerate(results)]
    response_texts = [str(res.content) for q_idx, res in enumerate(results)]
    if not get_global("global_no_decompose"):
        sub_tasks = [res.sub_tasks for q_idx, res in enumerate(results)]
        sub_tasks_text = sub_tasks[0] # only one sample
    else:
        sub_tasks = None
        sub_tasks_text = None

    agents = [res.agents for q_idx, res in enumerate(results)]


    print('response_texts: ',response_texts[0])
    print('gold answers: ',global_answers[0])
    print('length: ', len(response_texts), len(global_answers))


    global_score_compute = get_global("global_score_compute")
    global_example_id = get_global("global_example_id")
    global_n = get_global("global_n")
    global_questions = get_global("global_questions")
    global_answers = get_global("global_answers")
    global_use_oracle_verifier = get_global("global_use_oracle_verifier")
    global_judge_path = get_global("global_judge_path")
    global_reponse_path = get_global("global_reponse_path")
    global_response_dict = get_global("global_response_dict")
    global_instance_id = get_global("global_instance_id")
    global_code_snippet = get_global("global_code_snippet")

    result_list = [
        global_score_compute(
            global_example_id,
            global_n,
            prompt_messages[response_text_id], 
            global_questions[response_text_id], 
            response_text, 
            global_answers[response_text_id],
            sub_tasks_text, 
            global_use_oracle_verifier,
            global_judge_path, 
            global_reponse_path,
            global_response_dict,
            global_instance_id,
            global_code_snippet) 
        for response_text_id, response_text in enumerate(response_texts)
        ]
    
    acc_oracle_verifier_list = [x[0] for x in result_list]
    acc_model_verifier_list = [x[1] for x in result_list]
    result_list = [x[2] for x in result_list]
    results = common.aggregate_results(result_list)

    print(f"acc_oracle_verifier_list:", acc_oracle_verifier_list)
    print(f"acc_model_verifier_list:", acc_model_verifier_list)


    return acc_oracle_verifier_list, acc_model_verifier_list, results, sub_tasks, agents, response_texts



def search(args, task_queue, meta_model, blocks, verifier_model):

    questions = get_global("global_questions")
    global_node_model = get_global("global_node_model")

    n_generation = args.n_generation
    print(f"a new search start")


    print(f"problem length: {len(questions)}")
    max_workers = min(len(questions), args.max_workers) if args.multiprocessing else 1

    task_queue = [Info(field_name, author, content, prompt, sub_tasks, agnets, iteration_idx) for field_name, author, content, prompt, sub_tasks, agnets, iteration_idx in task_queue]

    set_global("global_max_workers", max_workers)
    set_global("global_task_queue", task_queue)

    next_solution_path = os.path.join(args.save_dir, f"{args.expr_name}_{args.option}_next_solution.json")
    msg_path = os.path.join(args.save_dir, f"{args.expr_name}_{args.option}_msg.json")
    mem_path = os.path.join(args.save_dir, f"{args.expr_name}_{args.option}_mem.json")
    file_path = os.path.join(args.save_dir, f"{args.expr_name}_{args.option}_archive.json")
    result_path = f'./results/question/meta_agent/{args.dataset}/{meta_model}_{global_node_model}_{verifier_model}.results'
    oracle_acc_result_path = f'./results/question/meta_agent/{args.dataset}/{meta_model}_{global_node_model}_oracle.results'
    judge_path = os.path.join(args.save_dir, f"{args.expr_name}_{args.option}_judge")
    reponse_path = os.path.join(args.save_dir, f"{args.expr_name}_{args.option}_reponse")
    os.makedirs(os.path.dirname(judge_path), exist_ok=True)

    print('file_path: ',file_path)
    print('msg_path: ',msg_path)
    print('result_path: ',result_path)
    print('next_solution_path: ',next_solution_path)
    print('oracle_acc_result_path: ',oracle_acc_result_path)
    print('judge_path: ',judge_path)
    print('reponse_path: ',reponse_path)
    print('mem_path: ',mem_path)

    set_global("global_judge_path", judge_path)
    set_global("global_reponse_path", reponse_path)

    if os.path.exists(mem_path):
        with open(mem_path, 'r') as json_file:
            memory = json.load(json_file)
    else:
        memory = []

    if os.path.exists(reponse_path):
        with open(reponse_path, 'r') as json_file:
            global_response_dict = json.load(json_file)
        set_global("global_response_dict", global_response_dict)

    if os.path.exists(file_path):
        with open(file_path, 'r') as json_file:
            archive = json.load(json_file)
        if "generation" in archive[-1] and isinstance(archive[-1]["generation"], int):
            start = archive[-1]["generation"]
        else:
            start = 0
    else:
        archive = get_init_archive(blocks) # TODO: make this with arguement
        start = 0

    cur_archive = copy.deepcopy(archive) # do not change the solution inside, need deepcopy

    global_use_oracle_verifier = get_global("global_use_oracle_verifier")
    example_id = get_global("global_example_id")

    global_ns = []

    for solution_i, solution in enumerate(cur_archive):

        if 'fitness' in solution:
            continue

        solution["generation"] = "initial"
        print(f'============Initial Archive: {solution["name"]}=================')

        if solution["name"] in global_ns: # TODO: seprate it
            set_global("global_n", f'{solution["name"]}_{solution_i}')

        else:
            set_global("global_n", solution["name"])

        global_n = get_global("global_n")
        global_ns.append(global_n)

        # print(solution["code"])
        acc_oracle_verifier_list, acc_model_verifier_list, results, _, _, final_reponse = evaluate_forward_fn(args, solution["code"])

        #TODO: can we somehow also log acc_oracle_verifier_list so that we can know how accurate acc_model_verifier_list is?
        if global_use_oracle_verifier:
            acc_list = acc_oracle_verifier_list
        else:
            acc_list = acc_model_verifier_list


        if args.defer_verifier:
            fitness_str = bootstrap_confidence_interval([0.0])
            solution["acc"] = np.mean([0.0])

        else:
            fitness_str = bootstrap_confidence_interval(acc_list)
            solution["acc"] = np.mean(acc_list)

        solution["fitness"] = fitness_str
        solution["total_cost"] = get_global("global_COST_TOTAL")

        print(f"acc_list:", acc_list)
        print(f"mean acc_list:", np.mean(acc_list))
        print(f"bootstrap_confidence_interval: {fitness_str}")


        if 'swe_bench' in args.dataset:
            extracted_answer = final_reponse[0].split('\n\nAnswer:', 1)[-1].strip()
            if '<patch>' in extracted_answer:
                extracted_answer = extract_xml(extracted_answer, 'patch').strip()   
        else:
            extracted_answer = re.search(ANSWER_PATTERN, final_reponse[0]).group(1)     

        if '[TOO_HARD]' in extracted_answer: # we cannot add [TOO_HARD] in memory
            extracted_answer = extracted_answer[:extracted_answer.index('[TOO_HARD]')]        
        memory.append({extracted_answer:fitness_str})
        print(f'save json to {mem_path}')
        with open(mem_path, 'w') as json_file:
            json.dump(memory, json_file, indent=4)


        # save results
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        print(f'save json to {file_path}')
        with open(file_path, 'w') as json_file:
            json.dump(cur_archive, json_file, indent=4)

        report_filename = os.path.join(args.save_dir, f'{args.expr_name}_{solution["name"]}_{args.option}_debug.html')
        print(f"Writing report to {report_filename}")
        with open(report_filename, "w") as fh:
            fh.write(common.make_report(results))
        metrics = results.metrics | {"score": results.score}
        print('metrics: ',metrics)
        print(f"COST_TOTAL:", get_global("global_COST_TOTAL"))

        with open(oracle_acc_result_path, "a+") as fh:
            fh.write(f'experiemnt {example_id}: 1 (initial {solution["name"]}): acc_oracle_verifier_list: {acc_oracle_verifier_list} acc_model_verifier_list: {acc_model_verifier_list}\n')

        if not args.defer_verifier:
            if np.mean(acc_list) == 1: 
                if global_use_oracle_verifier:
                    with open(result_path, "a+") as fh:
                        fh.write(f'experiemnt {example_id}: 1 (initial {solution["name"]})\n')

                else:
                    # check with the real answer to decide whether to mark as correct
                    if np.mean(acc_oracle_verifier_list) == 1: # 
                        with open(result_path, "a+") as fh:
                            fh.write(f'experiemnt {example_id}: 1 (initial {solution["name"]})\n')

                # even the judge is incorrect, we still stop becasue have to listen to the judge    
                n_generation = 0 # no need
                start= 0 # no need
                print(f'write to {result_path}. break')
                break

            if acc_oracle_verifier_list[0] == 1: exit() #debug 
    # exit()

    global_task_queue = get_global("global_task_queue")
    global_format_choice = get_global("global_format_choice")

    for n in range(start, n_generation):
        print(f"============Generation {n + 1}=================")
        set_global("global_n", n)

        if n == 0: # initial propose
            system_prompt, prompt = get_prompt(cur_archive, option=args.option, task_queue=global_task_queue)
            msg_list = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            next_solution = get_json_response_from_gpt_reflect(copy.deepcopy(msg_list), meta_model)

        if os.path.exists(msg_path):
            print(f'load msg_list from {msg_path}')
            with open(msg_path, 'r') as json_file:
                msg_list = json.load(json_file) # use the saved msg_list
        
        if os.path.exists(next_solution_path):
            print(f'load next_solution_path from {next_solution_path}')
            with open(next_solution_path, 'r') as json_file:
                next_solution = json.load(json_file) # use the saved msg_list

        else:
            #if no next solutionm, you have to do it again
            system_prompt, prompt = get_prompt(cur_archive, option=args.option, task_queue=global_task_queue)
            
            msg_list = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Initial Round (Round 0):\n\n" + prompt + '\n\nIMPORTANT: You must follow all the requirements in the Initial Round (Round 0) (e.g., what is wrong and correct in code implmenetation; You need to ACTUALLY IMPLEMENET the structure for self-consistency, LLM Debate and Relexion, by wrting the for-loop, if you choose to use them).'},
            ]

            next_solution = get_json_response_from_gpt_reflect(copy.deepcopy(msg_list), meta_model)


        acc_list = []
        for _ in range(args.debug_max):
            try: # in case the generated code is not correct
                acc_oracle_verifier_list, acc_model_verifier_list, results, sub_tasks, agents, final_reponse = evaluate_forward_fn(args, next_solution["code"])

                if global_use_oracle_verifier:
                    acc_list = acc_oracle_verifier_list
                else:
                    acc_list = acc_model_verifier_list
                break
            except Exception as e:
                # %%%%%%%%%%%%% only for debug
                print("During evaluation:")
                print(e)
                debug_list = copy.deepcopy(msg_list) #deep copy
                print('finish deep copy')

                debug_list.append({"role": "assistant", "content": next_solution})

                if global_format_choice == 'xml':

                    global_shorten_context = get_global("global_shorten_context")
                    if global_shorten_context:
                        debug_list_reflect = shorten_context(debug_list)
                    else:
                        debug_list_reflect = debug_list
                    debug_list_reflect.append({"role": "user", "content": f"Error during evaluation:\n{e}\nCarefully consider where you went wrong in your latest implementation. Using insights from previous attempts, try to debug the current code to implement the exact same thought without any shortcut. You still need to follow all the requirement mentioed in this histroy. Give the fixed (implememnt the same thought) code in 'code'. Repeat your previous thought in 'thought', and put your thinking for debugging in 'debug_thought'. Repeat name in 'name'\n\nMake sure to return in a WELL-FORMED XML object. Wrap the required entries with <(entry_name)> and </(entry_name)>. For example, 'code' entry should be wrapped by <code> ...(your code)... </code>. However, Do not use XML format inside each entry"}) 
                else:
                    debug_list_reflect = debug_list # if you have enough length
                    debug_list_reflect.append({"role": "user", "content": f"Error during evaluation:\n{e}\nCarefully consider where you went wrong in your latest implementation. Using insights from previous attempts, try to debug the current code to implement the same thought. You still need to follow all the requirement mentioed in this histroy. Give the fixed (implememnt the same thought) code in 'code'. Repeat your previous thought in 'thought', and put your thinking for debugging in 'debug_thought'. Repeat name in 'name',"}) 
                    #TODO: sometimes still cannot fix. The reason is, the forward is a string, which provide limitted error information

                try:
                    next_solution = get_json_response_from_gpt_reflect(debug_list_reflect, meta_model)
                except Exception as e:
                    print("During LLM generate new solution:")
                    print(e)
                    continue
                # %%%%%%%%%%%%%

                continue

        if not acc_list:
            n -= 1 # rerun
            continue

        if args.defer_verifier:
            fitness_str = bootstrap_confidence_interval([0.0])
            next_solution["acc"] =[0.0]

        else:
            fitness_str = bootstrap_confidence_interval(acc_list)
            next_solution["acc"] = np.mean(acc_list)

        #Only have these after excusion
        next_solution["fitness"] = fitness_str
        next_solution["generation"] = n + 1
        next_solution["total_cost"] = get_global("global_COST_TOTAL")

        if not (get_global("global_no_decompose") or get_global("global_no_meta_reward")):
            next_solution["sub_tasks"] = sub_tasks
        if not get_global("global_no_meta_reward"):
            next_solution["agents"] = agents

        next_solution["final_reponse"] = final_reponse


        if 'swe_bench' in args.dataset:
            extracted_answer = final_reponse[0].split('\n\nAnswer:', 1)[-1].strip()
            if '<patch>' in extracted_answer:
                extracted_answer = extract_xml(extracted_answer, 'patch').strip()   
        else:
            extracted_answer = re.search(ANSWER_PATTERN, final_reponse[0]).group(1)     

        if '[TOO_HARD]' in extracted_answer:
            extracted_answer = extracted_answer[:extracted_answer.index('[TOO_HARD]')]
        memory.append({extracted_answer:fitness_str})
        print(f'save json to {mem_path}')
        with open(mem_path, 'w') as json_file:
            json.dump(memory, json_file, indent=4)

        cur_archive.append(next_solution) # propose

        # save results
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        print(f'save json to {file_path}')
        with open(file_path, 'w') as json_file:
            json.dump(cur_archive, json_file, indent=4)

        print(f"COST_TOTAL:", get_global("global_COST_TOTAL"))

        with open(oracle_acc_result_path, "a+") as fh:
            fh.write(f'experiemnt {example_id}: 1 (genration {n}+1): acc_oracle_verifier_list: {acc_oracle_verifier_list} acc_model_verifier_list: {acc_model_verifier_list}\n')

        if not args.defer_verifier:
            if np.mean(acc_list) == 1: 
                if global_use_oracle_verifier:
                    with open(result_path, "a+") as fh:
                        fh.write(f'experiemnt {example_id}: 1 (genration {n}+1) \n')
                else:
                    # check with the real answer to decide whether to mark as correct
                    if np.mean(acc_oracle_verifier_list) == 1: # 
                        with open(result_path, "a+") as fh:
                            fh.write(f'experiemnt {example_id}: 1 (genration {n}+1) \n')

                print(f'write to {result_path}. break')
                break # good enough

        # not good, need update again %%%%%%%%%%%%%
        Reflexion_after_eval_prompt = get_reflexion_after_eval(option=args.option)

        if 'workflow_search' in args.dataset and  'swe_bench' in args.dataset:
            global_code_snippet = get_global("global_code_snippet")
            Reflexion_after_eval_prompt =  f'Recall the requirement of original questions: \n\nGiven code_snippet \n\n{global_code_snippet}; Generate a patch following requirements: {AGENTLESS_REPAIR} \n\n Now please ' + Reflexion_after_eval_prompt + f'\n\nIMPORTANT Note: The above "code" entry is only for the code of your improved architecture and sub-tasks.'  
            # For example: {EXAMPLE_META} # Add Example may make the output patch worse
        
        # recall the xml format
        if global_format_choice == 'xml':
            Reflexion_after_eval_prompt += "IMPORTANT: 1. Make sure to return in a WELL-FORMED XML object. Wrap the required entries with <(entry_name)> and </(entry_name)>. Reply EXACTLY with the following XML fileds.\n<reflection> [Your reflection] </reflection>\n<thought> [Your thought.] </thought>\n<name> [Your name.] </name>\n<code> [Your code.] </code>\n\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object! However, Do not use XML format inside each entry\n\n2. You must follow all the requirements in the Initial Round (Round 0) (for example, If you choose to use self-consistency, LLM Debate or Relexion, you need to ACTUALLY IMPLEMENET their structure by wrting the for-loop explictly).\n\n3.the <code> corresponds to the exact “forward()” function in Python code that you would like to try. You must write a COMPLETE CODE in <code>: Your code will be part of the entire project (so do not implement any other part), so please implement complete, reliable, reusable code snippets."

        next_solution["memory"] = memory #TODO: it may output 128K limit
        # print('memory: ',memory) # TODO: Too large, we may not need to print it
        msg_list.append({"role": "assistant", "content": copy.deepcopy(next_solution)})
        # msg_list.append({"role": "user", "content": Reflexion_after_eval_prompt})
        # TODO: We need to handle the multi-turn repeating issues
        msg_list.append({"role": "user", "content": f'Round {n+1}: The entries (code, thoughts, agents, reflection, etc.) have been updated since last round (Round {n}). Now Using insights from previous rounds, reflect again on the new outputs after round {n}.\n\n' + Reflexion_after_eval_prompt.replace('round [last_round]',f'round {n}').replace('round [last_last_round]',f'round {n-1}')})


        global_shorten_context = get_global("global_shorten_context")
        global_merge_context = get_global("global_merge_context")

        if global_shorten_context:
            msg_list_reflect = shorten_context(msg_list)  # the maximum length is limitted, we cannot use all
        else:
            msg_list_reflect = msg_list # if you have enough length

        if global_merge_context: #merge to single turn
            msg_list_reflect = merge_context(msg_list_reflect) 

            #TODO: do we want more previous sampeld? we need to be careful about the max limit for qwen

        next_solution = get_json_response_from_gpt_reflect(copy.deepcopy(msg_list_reflect), meta_model) # deep copy to avoid in-place changes
        if next_solution == 'bad_request':
            print('bad_request; break fo now')
            break

        # meta agent results html --------
        prompt_message = []
        #TODO: let's look at the refect msg, to see whehter it is correct (04/15)
        for msg in  msg_list_reflect: # want a better output
            messgae = {'role': msg["role"]}
            if msg["role"] == 'assistant':
                try:
                    messgae["content"] =  '\n\n'.join([f'{key}: {item}' for key, item in msg["content"].items()])
                except Exception as e:
                    print("content e: ",e)
                    messgae["content"] = msg["content"]
            else:
                messgae["content"] =  msg["content"]
            prompt_message.append(messgae)

        response_text = '\n\n'.join([f'{key}: {item}' for key, item in next_solution.items()])

        html = common.jinja_env.from_string(HTML_JINJA).render(
            prompt_messages=prompt_message,
            next_message=dict(content=response_text, role="assistant"),
            score=0,
            correct_answer=0,
            extracted_answer=0,
        )
        convo = prompt_message + [dict(content=response_text, role="assistant")]
        results = SingleEvalResult(html=html, score=0, convo=convo)
        results = common.aggregate_results([results])
        report_filename = os.path.join(args.save_dir, f'{args.expr_name}_{next_solution["name"].strip()}_{args.option}_generation_{n}_debug.html')
        print(f"Writing report to {report_filename}")
        with open(report_filename, "w") as fh:
            fh.write(common.make_report(results))
        # meta agent results html -------

        if 'debug_thought' in next_solution:
            del next_solution["debug_thought"]

        with open(msg_path, 'w') as json_file:
            json.dump(msg_list, json_file, indent=4)
        with open(next_solution_path, 'w') as json_file:
            json.dump(next_solution, json_file, indent=4)

        if not args.defer_verifier:
            if acc_oracle_verifier_list[0] == 1: exit() #debug 
