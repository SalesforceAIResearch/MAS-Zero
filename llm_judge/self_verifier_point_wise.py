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
from llm_judge.common import post_process

import copy

from prompts.judge.math_code import MATH_PROMPT





def verify(sampler, msg, log_path):
    while True:
        try:
            response, _ = sampler(msg)
            json_dict = json.loads(response)

            if 'code' in json_dict and 'correct' in json_dict:
                # print('verifier response: ')
                with open(log_path, 'a+') as log_file:
                    for key, item in json_dict.items():
                        log_file.write(f'key: {key}\nitem: {item}\n')
                        print(f'{key}: {item}')
                break
        except Exception as e:
            print(f'Error: {e}')

    # look at code
    forward_str = json_dict['code']
    text_judge = json_dict['correct']


    # print(f'take text_judge: {text_judge}')
    # json_dict['correct'] = text_judge


    #TODO: tunnable.
    debug_list = copy.deepcopy(msg) #deep copy

    max_debug = 5 
    for debug in range(max_debug):
        try:
            if forward_str.count('tolerate_value') <= 1:
                raise AssertionError("Must include a tolerate_value when comparison, to allow for small floating-point discrepancies when comparison. Please add this to your code.")

            code_judge = run_verifier(forward_str)

            if code_judge not in ['yes','no']:
                raise AssertionError("As a verify function, must output 'yes' or 'no' to indicate the correctness")

            if forward_str.count('sp.solve') != forward_str.count('is_trivial'):
                raise AssertionError(
                    """Must check if 'self.is_trivial(eq, eq_string)' is True before calling the 'sp.solver' to make sure that the solve is not trivial. Please add such checks by 'if self.is_trivial(eq, eq_string)' before each 'sp.solver'. Also, make sure the input to is_trivial() is the entire equation of sp.solver, not only one side. For example:
                    if self.is_trivial(sp.Eq(eq3, z), '(eq3, z)'):
                        sol_z = sp.solve(eq3, z)[0]
                """)

            break
        except Exception as e:
            print(f'Error: {e}')

            if 'relational' in str(e).lower():
                print('unknown error. just rerun')
            else:
                debug_list.append({"role": "assistant", "content": forward_str})
                debug_list.append({"role": "user", "content": 
                f"""Error during checking:\n{e}\nCarefully consider where you went wrong in your latest implementation. Using insights from previous attempts, try to debug the current code to implement the same thought.  Put the updated code in 'code', Repeat your previous thought in 'thought', and put your thinking for debugging in 'debug_thought'

                IMPORTANT:
                    - All the requirements in the original user content still valid.
                    - Must not change the checking and of the original code.  Only fix the grammar issue.
                    - Do not Call the function you wrote as the bigger project will do so. You just need to write down the function. 
                    - You need to make it clear which verification step it corresponds to for each part of your code. 
                    - The code must return 'yes' or 'no' indicate the checking results. 
                    - Do not add any additional assumption to checking above. Do exactly what the checking performs. You should be consistent with the conclusion of the checking.
                    - You must use ``tolerate_value`` when comparison
                """})
            # print('debug_list: ',debug_list)
            while True:
                try:
                    response, _ = sampler(debug_list)
                    json_dict = json.loads(response)
                    if 'code' in json_dict: # must have
                        break
                except Exception as e:
                    print(f'Error: {e}')
            forward_str = json_dict['code']
            print('debug updated forward_str: ',forward_str)

    # cannot write good verifier code. Then we can make the verifier code more strict
    if debug == max_debug - 1: 

        with open(log_path, 'a+') as log_file:
            log_file.write(f'take text_judge: {text_judge}\n')

        print(f'take text_judge: {text_judge}')
        json_dict['correct'] = text_judge
    else:
        with open(log_path, 'a+') as log_file:
            log_file.write(f'take code_judge: {code_judge}\n')

        print(f'take code_judge: {code_judge}')
        json_dict['correct'] = code_judge

    return json_dict


def score_verify(sampler, msg, log_path, response_id, post_processed):
    # Instruction for step-by-step reasoning
    #TODO: make it scoring, so that we can do ranking

    N = 10 # Number of CoT agents
    scores = []
    answer_mapping = {}
    possible_answers = []
    for i in range(N):
        # print('msg sc: ',msg)
        response = verify(sampler, msg, log_path)
        answer = response['correct']
        if answer == 'yes':
            score = float(1)
        else:
            score = float(0)

        scores.append(score)

        print(f'score: {score}; next round {i}')

    print(f'response_id: {response_id}; scores: {scores}; proposed answer: {post_processed}')
    score = float(sum(scores) / len(scores))

    with open(log_path, 'a+') as log_file:
        log_file.write(f'response_id: {response_id}; score: {score}; proposed answer: {post_processed}\n\n')
            

    return score  


def run_verifier(forward_str):

    class Verifier():
        def __init__(self) -> None:
            pass

        def is_trivial(self, eq, eq_string, tol=1e-5):
            import sympy as sp
            # Ensure eq is an equation object with .lhs and .rhs attributes
            try:
                diff = sp.simplify(eq.lhs - eq.rhs)
            except AttributeError:
                raise ValueError(f" {eq_string} is incorrect! The equation to solve must be an equation (sp.Eq object) with lhs and rhs.")
            
            # Attempt to get a numerical value; if that fails, check symbolically.
            try:
                diff_val = float(diff)
                if abs(diff_val) < tol:
                    raise ValueError(f"{eq_string} is incorrect! the difference of left-hand side and right-hand side  is 0!")
                return True
            except (TypeError, ValueError) as e:
                # If diff is symbolic, check if it simplifies to zero.
                if diff == 0 or diff.is_zero:
                    raise ValueError(f"{eq_string} is incorrect! the difference of left-hand side and right-hand side of is 0!")
                return True


    # print('forward_str: ',forward_str)

    namespace = {}
    exec(forward_str, globals(), namespace)
    names = list(namespace.keys())
    if len(names) != 1:
        raise AssertionError(f"{len(names)} things in namespace. Please only provide 1")
    func = namespace[names[0]]
    if not callable(func):
        raise AssertionError(f"{func} is not callable")
    setattr(Verifier, "forward", func)


    verifierSystem = Verifier()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(verifierSystem.forward)  # Submit the function for execution
        result = future.result()  # Get the result after execution
    

    print('result: ',result)
    return result




def run_self_verifier(post_process_path, log_path, score_path, responses, sampler):

    if os.path.exists(post_process_path):
        with open(post_process_path, 'r') as json_file:
            datas = json.load(json_file)

    else:
        datas = []
        for response_id, response in enumerate(responses):
            
            print('response_id: ',response_id)

            if response['sub_tasks_text'] is None: 
                candidate = response['response']
            else:
                candidate = response['sub_tasks_text']

            post_processed = post_process(sampler, candidate)        
            post_processed = post_processed['post-processed']
            problem = response["problem"]

            datas.append({"problem": problem, "response": post_processed, "candidate": candidate})

        with open(post_process_path, 'w') as json_file:
            json.dump(datas, json_file, indent=4)

    if os.path.exists(score_path):
        with open(score_path, 'r') as json_file:
            scores = json.load(json_file)
    else:
        scores = []

    for response_id, response in enumerate(responses):
        
        if response_id < len(scores): 
            print(f'skip: {response_id}')
            continue 
        # already exisit
        
        post_processed = datas[response_id]["response"]
        problem = datas[response_id]["problem"]

        FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!\n\n"""
        output_description = "Return ONLY 'yes' or 'no'. DO NOT return anything other than these two options."
        output_fields_and_description = {key: f"Your {key}." if not 'correct' in key else f"Your {key}. {output_description}" for key in ['thinking', 'correct', 'code']}
        system_prompt = 'You are a a graduate math professor to correct mistakes of your student home work. ' + FORMAT_INST(output_fields_and_description)

        # system_prompt = """You are a helpful assistant. Make sure to return in a WELL-FORMED JSON object."""


        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": MATH_PROMPT.replace('[QUESTION]',problem).replace('[ANSWER]',post_processed)},
        ]
        
        score = score_verify(sampler, msg, log_path, response_id, post_processed) # TODO: should be taken into account in the total cost
        scores.append(score)

        with open(score_path, 'w') as json_file:
            json.dump(scores, json_file, indent=4)

    chosen_id = scores.index(max(scores))

    return chosen_id, scores