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
from model_utils.io_utils import prepare_input, derive_step_rewards_vllm
import numpy as np

from common import ANSWER_PATTERN
from llm_judge.common import post_process, filter_and_sort
import re


from collections import Counter, defaultdict
from typing import List

from common import EQUALITY_TEMPLATE





def run_judge(prm_model_path, result_path, post_process_path, responses, sampler, post_processer, extracted_answers, dataset):

    if os.path.exists(post_process_path):
        with open(post_process_path, 'r') as json_file:
            datas = json.load(json_file)

    else:
        datas = []
        for response_id, response in enumerate(responses):
            
            print('response_id: ',response_id)
            candidate = response['response']

            # if response['sub_tasks_text'] is None: 
            #     candidate = response['response']
            # else:
            #     candidate = response['sub_tasks_text']

            post_processed = post_process(post_processer, candidate)        
            post_processed = post_processed['post-processed']
            problem = response["problem"]

            if type(problem) == list: # GPQA may results in list #TODO:
                problem = problem[0]
 
            datas.append({"problem": problem, "response": post_processed, "candidate": candidate})

        with open(post_process_path, 'w') as json_file:
            json.dump(datas, json_file, indent=4)

    # print('length of datas: ',len(datas))
        

    tokenizer = AutoTokenizer.from_pretrained(prm_model_path, trust_remote_code=True)


    answer_list = [d["response"] for d in datas]
    problem_list = [d["problem"] for d in datas]

    extracted_answers, answer_list = filter_and_sort(extracted_answers, answer_list, dataset)
    problem_list = problem_list[:len(answer_list)] # problem is the same

    print('updated answer: ',extracted_answers)
    print('problem_list: ',len(problem_list), len(answer_list))

    # print('updated answer: ',extracted_answers, answer_list, problem_list)

    # data preprocessing
    processed_data = [prepare_input(problem_list[d_id], answer_list[d_id], tokenizer=tokenizer, step_token="\n") for d_id, d in enumerate(answer_list)]
    input_ids, steps, reward_flags = zip(*processed_data)

    openai_api_key = "EMPTY"
    openai_api_base = "http://localhost:8081/v1"
    client = OpenAI(
        # defaults to os.environ.get("OPENAI_API_KEY")
        api_key=openai_api_key,
        base_url=openai_api_base,
    )
    models = client.models.list()
    model = models.data[0].id
    rewards = client.embeddings.create(
        input=input_ids,
        model=model,
    )

    step_rewards = derive_step_rewards_vllm(rewards, reward_flags)

    avg_rewards = []
    last_rewards = []

    for reward_id, reward in enumerate(step_rewards):
        avg_rewards.append(np.mean(step_rewards[reward_id]))
        last_rewards.append(step_rewards[reward_id][-1])

        # print(f'post_processed: {datas[reward_id]["response"][:10]}; reward: {step_rewards[reward_id]}')

    #     print("step_rewards:",step_rewards[reward_id], np.mean(step_rewards[reward_id]))

    # print('avg_rewards: ',avg_rewards)
    # print('last_rewards: ',last_rewards)

    # chosen_id = avg_rewards.index(max(avg_rewards))
    # print(f'avg_rewards chosen_id: {chosen_id}; chosen reponse: {datas[chosen_id]}')

    chosen_id = last_rewards.index(max(last_rewards))
    # print(f'last_rewards chosen_id: {chosen_id}; chosen reponse: {datas[chosen_id]}')

    return chosen_id



    # def _agg_orm_vote(x_list: List[str], v_list: List[float], return_reward_idx=False):
    #     assert len(x_list) == len(v_list)
    #     x_dict = defaultdict(lambda: 0.0)
    #     for x, v in zip(x_list, v_list):
    #         x_dict[x] += v

    #     print('x_list: ',x_list)           
    #     print('x_dict: ',x_dict)

    #     highest_x = max(x_dict, key=x_dict.get)
    #     if return_reward_idx:
    #         idx_list = [i for i, x in enumerate(x_list) if x == highest_x]
    #         print('idx_list: ',idx_list)
    #         corresponding_v_list = [v_list[idx] for idx in idx_list]
    #         print('corresponding_v_list: ',corresponding_v_list)
    #         idx = corresponding_v_list.index(max(corresponding_v_list))
    #         return highest_x, idx_list[0]
    #     return highest_x
        

    # highest_x, idx = _agg_orm_vote(data_extracted_answers, avg_rewards, return_reward_idx=True)
    # print(f'avg_rewards chosen_id: {idx}; chosen reponse: {datas[idx]}')

    # highest_x, idx = _agg_orm_vote(data_extracted_answers, last_rewards, return_reward_idx=True)
    # print(f'last_rewards chosen_id: {idx}; chosen reponse: {datas[idx]}')


