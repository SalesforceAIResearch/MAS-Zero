import argparse
import copy
import json
import os
import random
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import openai
from tqdm import tqdm

import re

from typing import Any
from datasets import load_dataset
import pandas as pd

import copy

from sampler.o_chat_completion_sampler import OChatCompletionSampler
from sampler.claude_sampler import ClaudeCompletionSampler, CLAUDE_SYSTEM_MESSAGE_LMSYS
from sampler.chat_completion_sampler import (
    OPENAI_SYSTEM_MESSAGE_API,
    OPENAI_SYSTEM_MESSAGE_CHATGPT,
    ChatCompletionSampler,
)

from openai import OpenAI
from transformers import AutoTokenizer
import numpy as np

import re


from collections import Counter, defaultdict
from typing import List

from llm_judge import self_verifier_list_wise
from common import EQUALITY_TEMPLATE, MCQ_EQUALITY_TEMPLATE, ANSWER_PATTERN

from sampler.vllm_completion_sampler import ChatCompletionSampler as VllmChatCompletionSampler
from sampler.together_completion_sampler import ChatCompletionSampler as ToChatCompletionSampler
from shared_vars import set_global, get_global

def rule_equality(correct, candidate):

    LETTER_TO_INDEX = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

    res = candidate
    answer = correct

    is_early_stop = False
    try:
        if isinstance(res, str) and res in LETTER_TO_INDEX:
            predicted_idx = LETTER_TO_INDEX[res]
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
            predicted_idx = LETTER_TO_INDEX[try_res.content]
        elif res.content in LETTER_TO_INDEX:
            predicted_idx = LETTER_TO_INDEX[res.content]
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
    print(f'rule_based: extracted_answer: {extracted_answer}; answer: {answer}; score: {score}')
    return score

def check_equality(dataset, question, correct, candidate):

    FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!\n\n"""

    output_description = "Return ONLY 'yes' or 'no' and DO NOT return anything other than these two."
    thinking_description = "Give your detialed thinking, Specifically, what is expression 1 and what is expression 2."

    output_fields_and_description = {key: f"Your {key}. {thinking_description}" if 'thinking' in key else f"Your {key}. {output_description}" for key in ['thinking', 'equal']}

    system_prompt = 'You are a helpful assistant. ' + FORMAT_INST(output_fields_and_description)

    if dataset == 'aime24':
 
        prompt = EQUALITY_TEMPLATE % {"expression1": correct, "expression2": candidate}

        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]    


        while True:
            try:
                response, _ = equality_checker(msg)
                json_dict = json.loads(response)
                break
            except Exception as e:
                print(f'Error: {e}')    

        print(f'json_dict: {json_dict}')
        score = json_dict['equal'].lower().strip() == "yes"

    elif dataset == 'gpqa_diamond':

        score = rule_equality(correct, candidate)

        if score == 1:
            print('Take rule based as it directly matched')
            return score # we are done
        else:
            return score # we are done; TODO: Dp not use LLM

            # use LLM to decide, sometimes it gives the value instead of the option
            INDEX_TO_LETTER = {0: 'A', 1: 'B', 2: 'C', 3 : 'D'}

            prompt = MCQ_EQUALITY_TEMPLATE % {"question": question, "expression1": INDEX_TO_LETTER[correct], "expression2": candidate}

            msg = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]    

            while True:
                try:
                    response, _ = equality_checker(msg)
                    json_dict = json.loads(response)
                    break
                except Exception as e:
                    print(f'Error: {e}')    

            print(f'json_dict: {json_dict}')
            score = json_dict['equal'].lower().strip() == "yes"

    return score



parser = argparse.ArgumentParser()
parser.add_argument('--judge_method', type=str)
parser.add_argument('--baseline', type=str)
parser.add_argument('--dataset', type=str)
parser.add_argument('--max_sample', type=int)
parser.add_argument('--min_sample', type=int, default=0)
parser.add_argument('--max_response_per_sample', type=int)
parser.add_argument('--model', type=str, default="gpt-4o_chatgpt")
parser.add_argument('--majority_vote', action='store_true')

args = parser.parse_args()

if __name__ == "__main__":


    dataset = args.dataset
    judge_method = args.judge_method
    max_sample = args.max_sample
    min_sample = args.min_sample
    max_response_per_sample = args.max_response_per_sample
    model = args.model
    majority_vote = args.majority_vote

    special_ids = []
    root_dir = f'./results/question/meta_agent/{args.baseline}'

    # all results
    if judge_method == 'external':
        prm_model_path = "Skywork/Skywork-o1-Open-PRM-Qwen-2.5-7B"
        result_path = f'{root_dir}/{dataset}/{model}_{model}_Skywork-o1-Open-PRM-Qwen-2.5-7B.results'
    else:
        result_path = f'{root_dir}/{dataset}/{model}_{model}_{judge_method}.results_{max_response_per_sample}'
    if os.path.exists(result_path):
        os.remove(result_path) # remove the file, do not repeat


    print('result_path: ',result_path)

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


    # we always use gpt-4o for post-process and equilty check
    post_processer = model_sampler_map['gpt-4o_chatgpt']
    equality_checker = model_sampler_map['gpt-4o_chatgpt']
    sampler = model_sampler_map[model]

    correct_example = []

    for example_id in range(min_sample,max_sample+1):
    # subset = [0,1,2,3,4,31,32,33,51,52,53,54,55,56,57,70,71,72,73,131,132,133,134,135,136,137,138]
    # print(f'length: {len(subset)}')

    # for example_id in subset:

        print(f'-------- example_id {example_id} --------')

        reponse_path = f'{root_dir}/{dataset}/{example_id}/{model}_{model}_{model}_0_plan_reponse'
        # reponse_path = f'{root_dir}/{dataset}/{example_id}/{model}_{model}_{model}_0__reponse' #sometimes miss "plan"

        try:
            with open(reponse_path, 'r') as json_file:
                responses = json.load(json_file)
        except Exception as e:
            print(f'example_id {example_id} response file {reponse_path} does not exisit')
            special_ids.append(f'example_id {example_id} response file {reponse_path} does not exisit')
            continue 

        if len(responses) < max_response_per_sample:
            print(f'responses length {len(responses)} is lower than {max_response_per_sample}')
            special_ids.append(f'example_id {example_id}: responses length {len(responses)} is lower than {max_response_per_sample}')
            # just a warning is fine
            # continue


        question = responses[0]['problem'] # all responses have the same answer

        #accumulate
        extracted_answers = []
        correct_answers = []

        for response in responses:
            filter_response = response['response']

            #TODO: for gpqa, in some cases, it gives the final answer instead of final selection
            if '<TOO_HARD>' in filter_response:
                filter_response = filter_response[:filter_response.index('<TOO_HARD>')]
                # print(f'<TOO_HARD> detected: response: {response['response']}; filter_response: {filter_response}')

            match = re.search(ANSWER_PATTERN, filter_response)
            extracted_answer = match.group(1) if match else None    
            extracted_answers.append(extracted_answer.strip() if extracted_answer is not None else extracted_answer) # for exact match, "strip()" can make a significant difference
            
            correct_answer = response['correct_answer']
            correct_answers.append(correct_answer)

        print('extracted_answers: ',extracted_answers)
        print('correct_answers: ',correct_answers)

        is_correct = False

        if judge_method == 'oracle':

            for round_id, (correct_answer, extracted_answer) in enumerate(zip(correct_answers, extracted_answers)):
                
                if round_id == max_response_per_sample: break # Do not go futher

                print('round_id: ',round_id)
                print('extracted_answer: ',extracted_answer)

                score = check_equality(dataset,question, correct_answer, extracted_answer)

                if score == 1:
                    print(f'correct: correct_answer: {correct_answer} vs. extracted_answer: {extracted_answer}')
                    with open(result_path, "a+") as fh:
                        fh.write(f'experiemnt {example_id}: 1 ({responses[round_id]["n"]}); correct_answer: {correct_answer} vs. extracted_answer: {extracted_answer}\n')
                    is_correct = True
                    break

        elif judge_method == 'external':
            from llm_judge import prm
            post_process_path = f'{root_dir}/{dataset}/{example_id}/{model}_{model}_{model}_0_plan_post_process.json'
            print('post_process_path: ',post_process_path)

            try:
                chosen_id = prm.run_judge(prm_model_path, result_path, post_process_path, responses, sampler,post_processer,  extracted_answers, dataset)
            except Exception as e:
                special_ids.append(f'Error: {e}; skip')
                print(f'Error: {e}; skip')
                continue
            print(f'chosen_id: {chosen_id}')

            correct_answer = correct_answers[chosen_id]
            extracted_answer = extracted_answers[chosen_id]

            score = check_equality(dataset, question, correct_answer, extracted_answer)
            
            if score == 1: # if the chosen one is correct
                print(f'correct: correct_answer: {correct_answer} vs. extracted_answer: {extracted_answer}')
                with open(result_path, "a+") as fh:
                    fh.write(f'experiemnt {example_id}: 1 ({responses[chosen_id]["n"]}); correct_answer: {correct_answer} vs. extracted_answer: {extracted_answer}\n')
                is_correct = True


        if judge_method == 'self':
            #TODO: consider a list-wise judge

            post_process_path = f'{root_dir}/{dataset}/{example_id}/{model}_{model}_{model}_0_plan_sub_task_post_process.json'
            log_path = f'{root_dir}/{dataset}/{example_id}/{model}_{model}_{model}_0_plan_sub_self_verifier_log'
            score_path = f'{root_dir}/{dataset}/{example_id}/{model}_{model}_{model}_0_plan_score.json'

            chosen_id = self_verifier_list_wise.run_self_verifier(post_process_path, log_path, score_path, responses, sampler, post_processer, extracted_answers, dataset, max_response_per_sample, majority_vote)

            print('chosen_id: ',chosen_id) 
            correct_answer = correct_answers[chosen_id]
            extracted_answer = extracted_answers[chosen_id]

            score = check_equality(dataset, question, correct_answer, extracted_answer)
            
            if score == 1:
                print(f'correct: correct_answer: {correct_answer} vs. extracted_answer: {extracted_answer}')
                with open(result_path, "a+") as fh:
                    fh.write(f'experiemnt {example_id}: 1 ({responses[chosen_id]["n"]}); correct_answer: {correct_answer} vs. extracted_answer: {extracted_answer}\n')
                is_correct = True


        if is_correct:
            correct_example.append(1)
        else:
            print(f'Cannot Find Correct Answer acorss reponses for example_id: {example_id}')
            correct_example.append(0)

    for special_id in special_ids:
        print('special_id: ',special_id)
        
    acc = sum(correct_example) / len(correct_example)
    print(f'coorect {sum(correct_example)}; Total: {len(correct_example)}; Acc: {acc}')

    with open(result_path, "a+") as fh:
        fh.write(f'coorect {sum(correct_example)}; Total: {len(correct_example)}; Acc: {acc}\n')
