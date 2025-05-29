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
from llm_judge.common import post_process, filter_and_sort
import random

import copy

from shared_vars import set_global, get_global


def majority_vote_funct(responses, extracted_answers, max_response_per_sample):
    answer_list = []
    extracted_list = []
    for response_id, (response, extracted_answer) in enumerate(zip(responses, extracted_answers)):
        if response_id == max_response_per_sample: break # Do not go futher

        answer_list.append(response_id)
        extracted_list.append(extracted_answer)

    extracted_answers = extracted_list
    print('answer_list: ',answer_list)
    print('extracted_answers: ',extracted_answers)
    # filter and sort based on final answer, but give both thought and final answer to the self-judge
    extracted_answers, answer_list = filter_and_sort(extracted_answers, answer_list, dataset)
    major_answer = answer_list[0]
    return major_answer


def multiple_choice_funct(responses, extracted_answers, max_response_per_sample, dataset, post_process_path, sampler):

    answer_list = []
    extracted_list = []
    for response_id, (response, extracted_answer) in enumerate(zip(responses, extracted_answers)):
        if response_id == max_response_per_sample: break # Do not go futher
        if extracted_answer not in extracted_list: #deduplicate
            answer_list.append(f'ID: {response_id}: Answer: {extracted_answer}')
            extracted_list.append(extracted_answer)
            problem = response["problem"]

    extracted_answers = extracted_list
    extracted_answers, answer_list = filter_and_sort(extracted_answers, answer_list, dataset)

    print('updated_answers: ',extracted_answers)

    print('length of consideration: ', len(extracted_answers), len(answer_list))
    answer_list = '\n\n'.join(answer_list)

    # a listwise judge
    if 'gpt' in post_process_path:
        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!\n\n"""
        output_description = "Return ONLY the integer selection id. DO NOT return anything the id."
        output_fields_and_description = {key: f"Your {key}." if not 'selection' in key else f"Your {key}. {output_description}" for key in ['thinking', 'selection']}
        system_prompt = 'You are a judge to select the best answer from a list of candidate answers. ' + FORMAT_INST(output_fields_and_description)

        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": 
            f'Given a problem and a list of choices, select the best choice. In the "thinking" entry, compare the selected answer with all other unselected answer one-by-one, identify the erroneous steps in the unselected answer and give detailed explanation on why it is incorrect. In the "selection" entry, gives the best answer id \n\n Problem: \n {problem} \n\n Answer List: {answer_list}'},
        ]
    elif 'qwen' in post_process_path or 'llama' in post_process_path:
        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following XML format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object!\n\n"""
        output_description = "Return ONLY the integer selection id. DO NOT return anything the id."
        output_fields_and_description = '\n'.join([f"<{key}> [Your {key}.] </{key}>" if not 'selection' in key else f"<{key}> [Your {key}. {output_description}] </{key}>\n" for key in ['thinking', 'selection']])
        system_prompt = 'You are a judge to select the best answer from a list of candidate answers. ' + FORMAT_INST(output_fields_and_description)
        set_global("global_format_choice", 'xml')

        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": 
             f"Given a problem and a list of choices, select the best choice. In the <selection> field, gives the best answer ID. Reply EXACTLY with the following XML format.\n<thinking> [Your thinking.] </thinking>\n<selection> [Your selected answer ID.] </selection>\n\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object! \n Below is the problem and answer list. \n\n Problem: \n {problem} \n\n Answer List: {answer_list}"
            }
        ]
    else:
        raise NotImplementedError
    print('msg: ',msg)
    while True:
        try:
            response, _ = sampler(msg)
            json_dict = json.loads(response)

            if 'selection' in json_dict:
                selection = int(json_dict['selection'])
                thinking = json_dict['thinking']
                break
        except Exception as e:
            print(f'Error: {e}')

    print('selection: ',thinking, selection)
    return selection





def run_self_verifier(post_process_path, log_path, score_path, responses, sampler, post_processer, extracted_answers, dataset, max_response_per_sample, majority_vote=False, multiple_choice=False):

    if majority_vote:
        return majority_vote_funct(responses, extracted_answers, max_response_per_sample)
    if multiple_choice:
        return multiple_choice_funct(responses, extracted_answers, max_response_per_sample, dataset, post_process_path, sampler)

    if os.path.exists(post_process_path):
        with open(post_process_path, 'r') as json_file:
            datas = json.load(json_file)
    else:
        datas = []
        for response_id, response in enumerate(responses):
            
            print('post-process response_id: ',response_id)

            if response['sub_tasks_text'] is None: 
                candidate = response['response']
            else:
                candidate = response['sub_tasks_text']

            post_processed_json = post_process(post_processer, candidate)        
            post_processed = post_processed_json['post-processed']
            thinking = post_processed_json["thinking"]
            problem = response["problem"]

            datas.append({"problem": problem, 'thinking': thinking, "response": post_processed, "candidate": candidate, 'response_id': response_id})

        with open(post_process_path, 'w') as json_file:
            json.dump(datas, json_file, indent=4)

    if os.path.exists(score_path):
        with open(score_path, 'r') as json_file:
            scores = json.load(json_file)
    else:
        scores = None


    problem = datas[0]["problem"] # all problem are the same

    
    print('post_process_path: ',post_process_path)

    print(f'length datas: {len(datas)}; vs. length response: {len(responses)}; vs. length extracted_answers: {len(extracted_answers)} ')

    answer_list = []
    extracted_list = []
    for response_id, (response, extracted_answer) in enumerate(zip(responses, extracted_answers)):
        
        if response_id == max_response_per_sample: break # Do not go futher

        print('compare response_id: ',response_id)


        post_processed = datas[response_id]["response"]        
        answer_list.append(f'Answer ID: {response_id}: Answer: {post_processed}')

        extracted_list.append(extracted_answer)

        # final_answer = extracted_answers[response_id]
        # answer_list.append(f'Answer ID: {response_id}: Answer: {final_answer}')

    extracted_answers = extracted_list

    # filter and sort based on final answer, but give both thought and final answer to the self-judge

    print('extracted_answers: ',extracted_answers)

    extracted_answers, answer_list = filter_and_sort(extracted_answers, answer_list, dataset)

    #TODO: randomized?

    randomized = True
    if randomized:
        combined = list(zip(extracted_answers, answer_list))
        random.shuffle(combined)
        extracted_answers, answer_list = zip(*combined)

    print('updated_answers: ',extracted_answers)

    print('length of consideration: ', len(extracted_answers), len(answer_list))
    answer_list = '\n\n'.join(answer_list)

    # a listwise judge
    if 'gpt' in post_process_path:
        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!\n\n"""
        output_description = "Return ONLY the integer selection id. DO NOT return anything the id."
        output_fields_and_description = {key: f"Your {key}." if not 'selection' in key else f"Your {key}. {output_description}" for key in ['thinking', 'selection']}
        system_prompt = 'You are a judge to select the best answer from a list of candidate answers. ' + FORMAT_INST(output_fields_and_description)

        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": 
            f'Given the problem and a list of candidate thinking steps and the final answers, do not solve the task yourself but look carefully at the reasoning steps and final answer, select the best answer among the candidates. In the "thinking" entry, compare the selected answer with all other unselected answer one-by-one, identify the erroneous steps in the unselected answer and give detailed explanation on why it is incorrect. In the "selection" entry, gives the best answer id \n\n Problem: \n {problem} \n\n Answer List: {answer_list}'},
        ]
    elif 'qwen' in post_process_path or 'llama' in post_process_path:
        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following XML format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object!\n\n"""
        output_description = "Return ONLY the integer selection id. DO NOT return anything the id."
        output_fields_and_description = '\n'.join([f"<{key}> [Your {key}.] </{key}>" if not 'selection' in key else f"<{key}> [Your {key}. {output_description}] </{key}>\n" for key in ['thinking', 'selection']])
        system_prompt = 'You are a judge to select the best answer from a list of candidate answers. ' + FORMAT_INST(output_fields_and_description)
        set_global("global_format_choice", 'xml')

        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": 
            # f"Given a problem and a list of candidate answers (each including thinking steps and a final answer) along with their corresponding answer IDs, your task is to select the best answer based solely on individual quality.\nIMPORTANT:\n- DO NOT solve the problem yourself.\n- DO NOT consider agreement or consistency between answers.\n- Focus only on the internal reasoning quality, factual correctness, and completeness of each candidate.\n-DO NOT generate an ID that is not in the given answer IDs.\n\nFor each candidate, analyze the reasoning steps in detail. Identify any incorrect logic, invalid assumptions, or unsupported conclusions. Provide a concise assessment for each candidate. Then, select the best answer ID from the list.\nIn the <thinking> field, explain how you arrive your final selection. You must analyze each candidate answer one-by-one, identify the erroneous steps in each answer and give detailed explanation on why it is incorrect. In the <selection> field, gives the best answer ID. Reply EXACTLY with the following XML format.\n<thinking> [Your thinking.] </thinking>\n<selection> [Your selected answer ID.] </selection>\n\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object! \n Below is the problem and answer list. \n\n Problem: \n {problem} \n\n Answer List: {answer_list}" # consider agreement
            f"Given the problem and a list of candidate thinking steps and the final answers, do not solve the task yourself but look carefully at the reasoning steps and final answer, select the best answer among the candidates.\nIn the <thinking> field, compare the selected answer with all other unselected answer one-by-one, identify the erroneous steps in the unselected answer and give detailed explanation on why it is incorrect. In the <selection> field,  gives the best answer id. \n\n Problem: \n {problem} \n\n Answer List: {answer_list}'" #follow origin
            }
        ]
    else:
        raise NotImplementedError
    # print('msg: ',msg)

    scores = None # recompute
    if scores is None:
        while True:
            try:
                response, _ = sampler(msg)
                json_dict = json.loads(response)

                if 'selection' in json_dict:
                    selection = int(json_dict['selection'])
                    thinking = json_dict['thinking']
                    break
            except Exception as e:
                print(f'Error: {e}')

        print('selection: ',thinking, selection)

        with open(score_path, 'w') as json_file:
            json.dump(json_dict, json_file, indent=4)

    else:
        selection = scores

    # exit()

    return selection


