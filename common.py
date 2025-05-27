import os
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import io
import jinja2
import numpy as np
import requests
from tqdm import tqdm

from dataclasses import dataclass, field
from typing import Any

import json
from sampler.o_chat_completion_sampler import OChatCompletionSampler
from sampler.claude_sampler import ClaudeCompletionSampler, CLAUDE_SYSTEM_MESSAGE_LMSYS
from sampler.chat_completion_sampler import (
    OPENAI_SYSTEM_MESSAGE_API,
    OPENAI_SYSTEM_MESSAGE_CHATGPT,
    ChatCompletionSampler,
)
from human_eval.execution import check_correctness  # , unsafe_execute
import re
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
import json

import os
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from typing import Any

import io
import jinja2
import numpy as np
import requests
from tqdm import tqdm

from dataclasses import dataclass, field
from typing import Any
from blocks.cot import COT
from blocks.cot_sc import COT_SC
from blocks.llm_debate import LLM_debate
from blocks.reflexion_best_of_n import Reflexion_Best_of_N
import json
from sampler.chat_completion_sampler import ChatCompletionSampler
from sampler.together_completion_sampler import ChatCompletionSampler as ToChatCompletionSampler
from sampler.vllm_completion_sampler import ChatCompletionSampler as VllmChatCompletionSampler

import copy
from shared_vars import set_global, get_global, add_to_global_cost


Message = dict[str, Any]  # keys role, content
MessageList = list[Message]

# as of 02/25 https://platform.openai.com/docs/pricing
# note that o3 mini is cheaper
model_price_map = {

    "gpt-4o_chatgpt": {
        'prompt': 0.005,
        'completion': 0.015
    },
    # follow aflow: "gpt-4o": {"prompt": 0.005, "completion": 0.015}
    # in https://github.com/geekan/MetaGPT/blob/main/metagpt/utils/token_counter.py


    "o3-mini": {
        'prompt': 0.55,
        'completion': 4.40
    },
    "gpt-4o-mini-2024-07-18": {
        'prompt': 1.25,
        'completion': 10.00
    },
    "qwen-2.5-32b-instr": {
        'prompt': 0,
        'completion': 0
    },
    "llama-3.3-70b-instr": {
        'prompt': 0,
        'completion': 0
    },
}



class SamplerBase:
    """
    Base class for defining a sampling model, which can be evaluated,
    or used as part of the grading process.
    """

    def __call__(self, message_list: MessageList) -> str:
        raise NotImplementedError


@dataclass
class EvalResult:
    """
    Result of running an evaluation (usually consisting of many samples)
    """

    score: float | None  # top-line metric
    metrics: dict[str, float] | None  # other metrics
    htmls: list[str]  # strings of valid HTML
    convos: list[MessageList]  # sampled conversations


class Eval:
    """
    Base class for defining an evaluation.
    """

    def __call__(self, sampler: SamplerBase) -> EvalResult:
        raise NotImplementedError


@dataclass
class SingleEvalResult:
    """
    Result of evaluating a single sample
    """

    score: float | None
    metrics: dict[str, float] = field(default_factory=dict)
    html: str | None = None
    convo: MessageList | None = None  # sampled conversation



HTML_JINJA = """
<h3>Prompt conversation</h3>
{% for message in prompt_messages %}
{{ message_to_html(message) | safe }}
{% endfor %}
<h3>Sampled message</h3>
{{ message_to_html(next_message) | safe }}
<h3>Results</h3>
<p>Correct Answer: {{ correct_answer }}</p>
<p>Extracted Answer: {{ extracted_answer }}</p>
<p>Score: {{ score }}</p>
"""



#TODO: GPT-4o judge is bad and suffer a lot from false postive

def merge_context(msg_list_reflect):
    #TODO: can be incorrect
    system_msg = None
    user_parts = []

    for i, msg in enumerate(msg_list_reflect):
        if msg["role"] == "system":
            system_msg = msg
        elif msg["role"] == "user":
            user_parts.append(f"{msg['role'].capitalize()}: \n\n {msg['content']}")
        elif msg["role"] == "assistant":
            user_parts.append(f"Corresponding Outputs: \n\n {msg['content']}")

    # Use the last user message as the end
    final_user_content = user_parts[-1] if user_parts else ""
    merged_user_content = "\n\n".join(user_parts[:-1]) + "\n\nNow please do the following:\n\n" + final_user_content + "\n\nIMPORTANT: You must NOT copy any reflection, code or thought from the previous assistant message in the history above. You goal is to improve over them to achieve higher fitness score by updating the reflection, thought and code. Your new reflection, thought and code should be significantly different from those in the history so that it can change output of the code.\nDO NOT do trivial modifications like change the variable or sub-task names or paraphrase the same instruction, as these trivial changes cannot change the final output of your code.\nMake sure your code reflect all the improvements mentioned in your reflection and thought and it is COMPLETE." if len(user_parts) > 1 else final_user_content

    # TODO: can we make it a more pretty single turn?

    return [
        system_msg,
        {"role": "user", "content": merged_user_content}
    ]


def shorten_context(msg_list):
    msg_list_reflect = []

    assistant_indices = [i for i, msg in enumerate(msg_list) if msg['role'] == 'assistant']
    print('assistant_indices: ',assistant_indices)

    for msg_id, msg in enumerate(msg_list):

        # print('msg_id: ',msg_id)

        if msg['role'] == 'system': 
            msg_list_reflect.append(msg)
        elif msg['role'] == 'assistant':
            if msg_id != assistant_indices[-1]: # if not the last one, remove 2 keys and items to save some context length
                print(f'remove {msg_id}:  {msg['content'].keys()}')
                msg_list_reflect.append(
                    {**msg,
                    # "content": 
                    #     {
                    #     k: (v if k not in {"sub_tasks", "agents", "code", "acc", "total_cost"} else "[...] cut off due to context length limit")
                    #     for k, v in msg["content"].items()                            
                    #     }
                    # }
                    "content": {k: v for k, v in msg["content"].items() if k not in {"sub_tasks", "agents", "code", "acc", "total_cost"}}
                    }
                    )
            else: # for the last, just appen
                msg_list_reflect.append(msg)
        elif msg['role'] == 'user':
            msg_list_reflect.append(msg)
        else:
            raise NotImplementedError
    
    print('length of msg_list_reflect: ',len(msg_list_reflect))
    # for msg_id, msg in enumerate(msg_list_reflect):
    #     print(f'msg in reflect {msg_id}: {msg}')
    # exit()
    return msg_list_reflect


# def shorten_context(msg_list):
#     msg_list_reflect = []

#     assistant_indices = [i for i, msg in enumerate(msg_list) if msg['role'] == 'assistant']
#     assistant_indices_to_keep = set(assistant_indices[-1:]) #limitted by the mxium length

#     user_indices = [i for i, msg in enumerate(msg_list) if msg['role'] == 'user']
#     user_indices_to_keep = set(user_indices[-1:]) #limitted by the mxium length

#     for msg_id, msg in enumerate(msg_list):
#         if msg['role'] == 'system': 
#                 msg_list_reflect.append(msg)
#         elif msg['role'] == 'assistant':
#             if msg_id in assistant_indices_to_keep:
#                 msg_list_reflect.append(msg)
#             else:
#                 print(f'remove assistant context: {msg}')

#         elif msg['role'] == 'user':
#             if msg_id == len(msg_list)-1 or msg_id == 1: 
#                 msg_list_reflect.append(msg) #for user round, we only need the first and the last
#             else: 
#                 print(f'remove user context: {msg}') 
#         else:
#             raise NotImplementedError
    
#     print('msg_list_reflect: ',len(msg_list_reflect))
#     for msg_id, msg in enumerate(msg_list_reflect):
#         print(f'msg in reflect {msg_id}: {msg}')
#     # exit()
#     return msg_list_reflect


def check_equality(sampler: SamplerBase, expr1: str, expr2: str, use_oracle_verifier=False, judge_path=None):


    if use_oracle_verifier: # directly use oracle
        prompt = EQUALITY_TEMPLATE % {"expression1": expr1, "expression2": expr2}
        response, _ = sampler([dict(content=prompt, role="user")], response_format='normal')
        print('response oracle verifier: ',response)

    else: # use model verifier 
        raise NotImplementedError

    return response.lower().strip() == "yes"


def _pack_message(role: str, content: Any):
    return {"role": str(role), "content": content}


@backoff.on_exception(backoff.expo, openai.RateLimitError)
def get_json_response_from_gpt(
        msg,
        model,
        output_fields,
        tempreture
):
    # We do not do anything with system prompt

    # print('msg: ',msg)
    # print('model: ',model)
    model_sampler_map = get_global("global_model_sampler_map")
    sampler = model_sampler_map[model]

    debug_count = 0 
    while True:
        debug_count += 1
        try:
            sampler_return = sampler(msg, tempreture)

            #TODO: we do not want to break here. If it is just excution, it must be runnable by keep retrying
            # if sampler_return == "" or debug_count > 5: #bad request
            #     json_dict = "bad_request"
            #     return json_dict

            response_text, usage = sampler_return
            json_dict = json.loads(response_text)
            keys = json_dict.keys()

            is_valid_answer = True
            if 'answer' in keys and len(json_dict['answer'].strip())==0:
                is_valid_answer = False

            if set(keys) == set(output_fields) and is_valid_answer:
            # if set(json_dict.keys()) == {'thinking', 'answer'} or set(json_dict.keys()) == {'feedback', 'correct'}:
                break
            else:
                print(f'require output_fields: {output_fields}, json_dict: {keys}; is_valid_answer: {is_valid_answer}')

        except Exception as e:
            print(f'Excute Error: {e}; response_text: {response_text}')

    # print('json_dict: ',json_dict)
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    cost = (
    prompt_tokens * model_price_map[model]['prompt']
    + completion_tokens * model_price_map[model]['completion']
    ) / 1000
    add_to_global_cost(cost)
    # print('COST_TOTAL: ',COST_TOTAL)

    return json_dict


@backoff.on_exception(backoff.expo, openai.RateLimitError)
def get_json_response_from_gpt_reflect(
        msg,
        model
):
        # "thought":  # "name": "Chain-of-Thought", # "code": 
    # print('model: ',model)
    model_sampler_map = get_global("global_model_sampler_map")
   
    sampler = model_sampler_map[model]
    # print('meta msg: ',msg)

    debug_count = 0 
    while True:
        debug_count += 1
        try:
            sampler_return = sampler(msg)
            if sampler_return == "" or debug_count > 5: #bad request
                json_dict = "bad_request"
                return json_dict

            response_text, usage = sampler_return
            json_dict = json.loads(response_text)

            # print('json_dict: ',json_dict)
            keys = json_dict.keys()
            #TODO: consider constraint the json like above
            if 'name' in keys and 'thought' in keys and 'code' in keys and 'def forward(self, taskInfo):' in json_dict['code']:
                try:
                    compile(json_dict['code'], "<string>", "exec")
                except SyntaxError as e:
                    print(f"Syntax error: {e}. Rerun")
                    continue
                break
            else: #inocrrect
                if not 'def forward(self, taskInfo):' in json_dict['code']:
                    print(f"code: {json_dict['code']}; reflection: {json_dict['reflection']}")
                print(f"missing key: {keys}",)
        except Exception as e:
            print(f'Reflect Error: {e}; response_text: {response_text}')

    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    cost = (
    prompt_tokens * model_price_map[model]['prompt']
    + completion_tokens * model_price_map[model]['completion']
    ) / 1000
    add_to_global_cost(cost)


    return json_dict



def get_init_archive(blocks):

    global_format_choice = get_global("global_format_choice")
    if global_format_choice == 'json':
        from blocks.reflexion import Reflexion
    elif global_format_choice == 'xml':
        from blocks.reflexion_xml import Reflexion
    else:
        raise NotImplementedError

    block_map = {
        'COT': COT,
        'COT_SC': COT_SC,
        'Reflexion': Reflexion,
        'LLM_debate': LLM_debate,
        'Reflexion_BEST_OF_N': Reflexion_Best_of_N
    }    
    return [copy.deepcopy(block_map[block]) for block in blocks] # it may be the same architecture, copy to avpod cross modification


def import_based_on_option(option):
    if option == 'edge':
        from prompts.edge.init_propose import base, EXAMPLE
        from prompts.edge.reflect_before_eval import  Reflexion_prompt_1, Reflexion_prompt_2

    elif option == 'adas':
        from prompts.adas.init_propose import base, EXAMPLE
        from prompts.adas.reflect_before_eval import  Reflexion_prompt_1, Reflexion_prompt_2

    elif option == 'node':
        from prompts.node.init_propose import base, EXAMPLE
        from prompts.node.reflect_before_eval import  Reflexion_prompt_1, Reflexion_prompt_2

    elif option == 'cot_sc':
        from prompts.cot_sc.init_propose import base, EXAMPLE
        from prompts.cot_sc.reflect_before_eval import  Reflexion_prompt_1, Reflexion_prompt_2

    elif option == 'plan':
        global_no_decompose = get_global("global_no_decompose")
        global_no_meta_reward = get_global("global_no_meta_reward")

        if global_no_decompose:
            from prompts.plan.propose_no_decompose import base, EXAMPLE
        elif global_no_meta_reward:
            from prompts.plan.propose_no_meta_reward import base, EXAMPLE
        else:
            from prompts.plan.propose import base, EXAMPLE
        from prompts.plan.reflect_before_eval import Reflexion_prompt_1, Reflexion_prompt_2

    else:
        raise NotImplementedError

    return  base, EXAMPLE, Reflexion_prompt_1, Reflexion_prompt_2 

def get_prompt(current_archive, option='', task_queue=None): # this is for search method
    archive_str = ",\n".join([json.dumps(sol) for sol in current_archive])
    archive_str = f"[{archive_str}]"

    base, EXAMPLE, Reflexion_prompt_1, Reflexion_prompt_2 = import_based_on_option(option)

    prompt = base.replace("[ARCHIVE]", archive_str)
    prompt = prompt.replace("[EXAMPLE]", json.dumps(EXAMPLE))

    if 'Below is the question to solve:\n\n[QUESTION]' in prompt:
        prompt = prompt.replace("[QUESTION]", task_queue[0][2])

    global_format_choice = get_global("global_format_choice")

    if global_format_choice == 'json':
        system_prompt = """You are a helpful assistant.\n\nReply EXACTLY with the following JSON format.\n{"reflection": "Your reflection (if applicable).", "thought": "Your thought.", "name": "Your name.", "code": "Your code."}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!
        """
    elif global_format_choice == 'xml':
        system_prompt = """You are a helpful assistant.\n\nReply EXACTLY with the following XML format.\n<reflection> [Your reflection, if applicable] </reflection>\n<thought> [Your thought.] </thought>\n<name> [Your name.] </name>\n<code> [Your code.] </code>\n\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed XML object!"""
    else:
        raise NotImplementedError

    return system_prompt, prompt


def get_reflexion_after_eval(option):
    global_format_choice = get_global("global_format_choice")

    if option == 'plan':

        global_no_decompose = get_global("global_no_decompose")
        global_no_meta_reward = get_global("global_no_meta_reward")

        if global_no_meta_reward: # only consider GPT-4o
            from prompts.plan.reflect_after_eval_no_meta_reward import Reflexion_after_eval_prompt
        elif global_no_decompose:
            from prompts.plan.reflect_after_eval_no_decompose import Reflexion_after_eval_prompt
        else:
            if global_format_choice == 'json':
                from prompts.plan.reflect_after_eval import Reflexion_after_eval_prompt
            elif global_format_choice == 'xml':
                from prompts.plan.reflect_after_eval_xml import Reflexion_after_eval_prompt
            else:
                raise NotImplementedError

    else:
        raise NotImplementedError

    return Reflexion_after_eval_prompt 




def get_reflexion_prompt(prev_example, option):

    base, EXAMPLE, Reflexion_prompt_1, Reflexion_prompt_2  = import_based_on_option(option)

    prev_example_str = "Here is the previous agent you tried:\n" + json.dumps(prev_example) + "\n\n"
    r1 = Reflexion_prompt_1.replace("[EXAMPLE]", prev_example_str) if prev_example else Reflexion_prompt_1.replace("[EXAMPLE]", "")
    return r1, Reflexion_prompt_2






def aggregate_results(
    single_eval_results: list[SingleEvalResult],
    default_stats: tuple[str] = ("mean", "std"),
    name2stats: dict[str, tuple[str]] | None = None,
) -> EvalResult:
    """
    Aggregate results from multiple evaluations into a single EvalResult.
    """
    name2stats = name2stats or {}
    name2values = defaultdict(list)
    htmls = []
    convos = []
    for single_eval_result in single_eval_results:
        for name, value in single_eval_result.metrics.items():
            name2values[name].append(value)
        if single_eval_result.score is not None:
            name2values["score"].append(single_eval_result.score)
        htmls.append(single_eval_result.html)
        convos.append(single_eval_result.convo)
    final_metrics = {}
    for name, values in name2values.items():
        stats = name2stats.get(name, default_stats)
        for stat in stats:
            key = name if stat == "mean" else f"{name}:{stat}"
            final_metrics[key] = _compute_stat(values, stat)
    return EvalResult(
        score=final_metrics.pop("score", None), metrics=final_metrics, htmls=htmls, convos=convos
    )


def map_with_progress(f: callable, xs: list[Any], num_threads: int = 50):
    """
    Apply f to each element of xs, using a ThreadPool, and show progress.
    """
    if os.getenv("debug"):
        return list(map(f, tqdm(xs, total=len(xs))))
    else:
        with ThreadPool(min(num_threads, len(xs))) as pool:
            return list(tqdm(pool.imap(f, xs), total=len(xs)))


jinja_env = jinja2.Environment(
    loader=jinja2.BaseLoader(),
    undefined=jinja2.StrictUndefined,
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)
_message_template = """
<div class="message {{ role }}">
    <div class="role">
    {{ role }}
    {% if variant %}<span class="variant">({{ variant }})</span>{% endif %}
    </div>
    <div class="content">
    <pre>{{ content }}</pre>
    </div>
</div>
"""


def message_to_html(message: Message) -> str:
    """
    Generate HTML snippet (inside a <div>) for a message.
    """
    return jinja_env.from_string(_message_template).render(
        role=message["role"], content=message["content"], variant=message.get("variant", None)
    )


jinja_env.globals["message_to_html"] = message_to_html


_report_template = """<!DOCTYPE html>
<html>
    <head>
        <style>
            .message {
                padding: 8px 16px;
                margin-bottom: 8px;
                border-radius: 4px;
            }
            .message.user {
                background-color: #B2DFDB;
                color: #00695C;
            }
            .message.assistant {
                background-color: #B39DDB;
                color: #4527A0;
            }
            .message.system {
                background-color: #EEEEEE;
                color: #212121;
            }
            .role {
                font-weight: bold;
                margin-bottom: 4px;
            }
            .variant {
                color: #795548;
            }
            table, th, td {
                border: 1px solid black;
            }
            pre {
                white-space: pre-wrap;
            }
        </style>
    </head>
    <body>
    {% if metrics %}
    <h1>Metrics</h1>
    <table>
    <tr>
        <th>Metric</th>
        <th>Value</th>
    </tr>
    <tr>
        <td><b>Score</b></td>
        <td>{{ score | float | round(3) }}</td>
    </tr>
    {% for name, value in metrics.items() %}
    <tr>
        <td>{{ name }}</td>
        <td>{{ value }}</td>
    </tr>
    {% endfor %}
    </table>
    {% endif %}
    <h1>Examples</h1>
    {% for html in htmls %}
    {{ html | safe }}
    <hr>
    {% endfor %}
    </body>
</html>
"""


def make_report(eval_result: EvalResult) -> str:
    """
    Create a standalone HTML report from an EvalResult.
    """
    return jinja_env.from_string(_report_template).render(
        score=eval_result.score,
        metrics=eval_result.metrics,
        htmls=eval_result.htmls,
    )


def make_report_from_example_htmls(htmls: list[str]):
    """
    Create a standalone HTML report from a list of example htmls
    """
    return jinja_env.from_string(_report_template).render(score=None, metrics={}, htmls=htmls)

def normalize_response(response: str) -> str:
    """
    Normalize the response by removing markdown and LaTeX formatting that may prevent a match.
    """

    return (
        response.replace("**", "")
        .replace("$\\boxed{", "")
        .replace("}$", "")
        .replace("\\$", "")
        .replace("$\\text{", "")
        .replace("$", "")
        .replace("\\mathrm{", "")
        .replace("\\{", "")
        .replace("\\text", "")
        .replace("\\(", "")
        .replace("\\mathbf{", "")
        .replace("{", "")
        .replace("\\boxed", "")
    )

def normalize_extracted_answer(extracted_answer: str) -> str:
    return (
        # In arabic these are the letters used for A-D in multiple choice questions
        extracted_answer.replace("أ", " A")
        .replace("ب", " B")
        .replace("ج", " C")
        .replace("د", " D")
        # In Bengali these are the letters used for A-D in multiple choice questions
        .replace("অ", " A")
        .replace("ব", " B")
        .replace("ড", " C")
        .replace("ঢ", " D")
        # In Japanese these are the letters sometimes used for A-D in multiple choice questions
        .replace("Ａ", " A")
        .replace("Ｂ", " B")
        .replace("Ｃ", " C")
        .replace("Ｄ", " D")
        .strip()
    )


def url_to_fileobj(url: str, binary=False) -> Any:
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content) if binary else io.StringIO(response.text)

def _compute_stat(values: list, stat: str):
    if stat == "mean":
        return np.mean(values)
    elif stat == "std":
        return np.std(values)
    elif stat == "min":
        return np.min(values)
    elif stat == "max":
        return np.max(values)
    else:
        raise ValueError(f"Unknown {stat =}")



ANSWER_PATTERN = r"(?i)Answer\s*:\s*([^\n]+)"


EQUALITY_TEMPLATE = r"""
Look at the following two expressions (answers to a math problem) and judge whether they are equivalent. Only perform trivial simplifications

Examples:

    Expression 1: $2x+3$
    Expression 2: $3+2x$

Yes

    Expression 1: 3/2
    Expression 2: 1.5

Yes

    Expression 1: $x^2+2x+1$
    Expression 2: $y^2+2y+1$

No

    Expression 1: $x^2+2x+1$
    Expression 2: $(x+1)^2$

Yes

    Expression 1: 3245/5
    Expression 2: 649

No
(these are actually equal, don't mark them equivalent if you need to do nontrivial simplifications)

    Expression 1: 2/(-3)
    Expression 2: -2/3

Yes
(trivial simplifications are allowed)

    Expression 1: 72 degrees
    Expression 2: 72

Yes
(give benefit of the doubt to units)

    Expression 1: 64
    Expression 2: 64 square feet

Yes
(give benefit of the doubt to units)

---

YOUR TASK


Respond with only "Yes" or "No" (without quotes). Do not include a rationale.

    Expression 1: %(expression1)s
    Expression 2: %(expression2)s
""".strip()



MCQ_EQUALITY_TEMPLATE = r"""
Look at the and questions and following two expressions (answers to a multiple-choice problem) and judge whether they are equivalent. Only perform trivial simplifications

Examples:

Question:
What is the correct answer to this question: The reaction of an electron pair donor, nucleophile (Nu) with an electron pair acceptor is called nucleophilic substitution reaction. An sp3-hybridized electrophile needs to have a leaving group to proceed with the reaction. Substitution reactions have the following two types. One is SN1 and the other is the SN2 reaction. In contrast to the substitution reaction, the elimination reaction involves the removal of a pair or groups of atoms from a molecule. These are chemical reactions in which single carbon-carbon bonded organic compounds are converted to compounds containing double/triple bonds (unsaturated compounds).\nArrange the following nucleophiles more reactive to the poorest reactive in the aqueous solution.\n\n1. 4-methylcyclohexan-1-olate\n2. Hydroxide\n3. Propionate\n4. Methanol\n5. Ethanethiolate\n\nChoices:\n(A) 5, 2, 1, 3 and 4\n(B) 2, 5, 1, 4 and 3\n(C) 5, 2, 3, 1 and 4\n(D) 2, 5, 3, 4 and 3


    Expression 1: A
    Expression 2: A

Yes
(It is allowed to give the value of the option instead of option A,B,C,D itself)
    Expression 1: A
    Expression 2: 5, 2, 1, 3 and 4 

Yes

    Expression 1: A
    Expression 2: 5, 2, 1, 3, 4

Yes

    Expression 1: A
    Expression 2: B

No

    Expression 1: A
    Expression 2: 2, 5, 1, 4 and 3

No
(these are actually equal, don't mark them equivalent if you need to do nontrivial simplifications)

    Expression 1: 2/(-3)
    Expression 2: -2/3

Yes
(trivial simplifications are allowed)

    Expression 1: 72 degrees
    Expression 2: 72

Yes
(give benefit of the doubt to units)

    Expression 1: 64
    Expression 2: 64 square feet

Yes
(give benefit of the doubt to units)

---

YOUR TASK


Respond with only "Yes" or "No" (without quotes). Do not include a rationale.
    Expression 1: %(question)s
    Expression 1: %(expression1)s
    Expression 2: %(expression2)s
""".strip()



def format_multichoice_question(row):
    return QUERY_TEMPLATE_MULTICHOICE.format(**row)


def _compute_stat(values: list, stat: str):
    if stat == "mean":
        return np.mean(values)
    elif stat == "std":
        return np.std(values)
    elif stat == "min":
        return np.min(values)
    elif stat == "max":
        return np.max(values)
    else:
        raise ValueError(f"Unknown {stat =}")


def aggregate_results(
    single_eval_results: list[SingleEvalResult],
    default_stats: tuple[str] = ("mean", "std"),
    name2stats: dict[str, tuple[str]] | None = None,
) -> EvalResult:
    """
    Aggregate results from multiple evaluations into a single EvalResult.
    """
    name2stats = name2stats or {}
    name2values = defaultdict(list)
    htmls = []
    convos = []
    for single_eval_result in single_eval_results:
        for name, value in single_eval_result.metrics.items():
            name2values[name].append(value)
        if single_eval_result.score is not None:
            name2values["score"].append(single_eval_result.score)
        htmls.append(single_eval_result.html)
        convos.append(single_eval_result.convo)
    final_metrics = {}
    for name, values in name2values.items():
        stats = name2stats.get(name, default_stats)
        for stat in stats:
            key = name if stat == "mean" else f"{name}:{stat}"
            final_metrics[key] = _compute_stat(values, stat)
    return EvalResult(
        score=final_metrics.pop("score", None), metrics=final_metrics, htmls=htmls, convos=convos
    )


def map_with_progress(f: callable, xs: list[Any], num_threads: int = 50):
    """
    Apply f to each element of xs, using a ThreadPool, and show progress.
    """
    if os.getenv("debug"):
        return list(map(f, tqdm(xs, total=len(xs))))
    else:
        with ThreadPool(min(num_threads, len(xs))) as pool:
            return list(tqdm(pool.imap(f, xs), total=len(xs)))


jinja_env = jinja2.Environment(
    loader=jinja2.BaseLoader(),
    undefined=jinja2.StrictUndefined,
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)
_message_template = """
<div class="message {{ role }}">
    <div class="role">
    {{ role }}
    {% if variant %}<span class="variant">({{ variant }})</span>{% endif %}
    </div>
    <div class="content">
    <pre>{{ content }}</pre>
    </div>
</div>
"""


def message_to_html(message: Message) -> str:
    """
    Generate HTML snippet (inside a <div>) for a message.
    """
    return jinja_env.from_string(_message_template).render(
        role=message["role"], content=message["content"], variant=message.get("variant", None)
    )


jinja_env.globals["message_to_html"] = message_to_html


_report_template = """<!DOCTYPE html>
<html>
    <head>
        <style>
            .message {
                padding: 8px 16px;
                margin-bottom: 8px;
                border-radius: 4px;
            }
            .message.user {
                background-color: #B2DFDB;
                color: #00695C;
            }
            .message.assistant {
                background-color: #B39DDB;
                color: #4527A0;
            }
            .message.system {
                background-color: #EEEEEE;
                color: #212121;
            }
            .role {
                font-weight: bold;
                margin-bottom: 4px;
            }
            .variant {
                color: #795548;
            }
            table, th, td {
                border: 1px solid black;
            }
            pre {
                white-space: pre-wrap;
            }
        </style>
    </head>
    <body>
    {% if metrics %}
    <h1>Metrics</h1>
    <table>
    <tr>
        <th>Metric</th>
        <th>Value</th>
    </tr>
    <tr>
        <td><b>Score</b></td>
        <td>{{ score | float | round(3) }}</td>
    </tr>
    {% for name, value in metrics.items() %}
    <tr>
        <td>{{ name }}</td>
        <td>{{ value }}</td>
    </tr>
    {% endfor %}
    </table>
    {% endif %}
    <h1>Examples</h1>
    {% for html in htmls %}
    {{ html | safe }}
    <hr>
    {% endfor %}
    </body>
</html>
"""


def make_report(eval_result: EvalResult) -> str:
    """
    Create a standalone HTML report from an EvalResult.
    """
    return jinja_env.from_string(_report_template).render(
        score=eval_result.score,
        metrics=eval_result.metrics,
        htmls=eval_result.htmls,
    )


def make_report_from_example_htmls(htmls: list[str]):
    """
    Create a standalone HTML report from a list of example htmls
    """
    return jinja_env.from_string(_report_template).render(score=None, metrics={}, htmls=htmls)

def normalize_response(response: str) -> str:
    """
    Normalize the response by removing markdown and LaTeX formatting that may prevent a match.
    """

    return (
        response.replace("**", "")
        .replace("$\\boxed{", "")
        .replace("}$", "")
        .replace("\\$", "")
        .replace("$\\text{", "")
        .replace("$", "")
        .replace("\\mathrm{", "")
        .replace("\\{", "")
        .replace("\\text", "")
        .replace("\\(", "")
        .replace("\\mathbf{", "")
        .replace("{", "")
        .replace("\\boxed", "")
    )

def normalize_extracted_answer(extracted_answer: str) -> str:
    return (
        # In arabic these are the letters used for A-D in multiple choice questions
        extracted_answer.replace("أ", " A")
        .replace("ب", " B")
        .replace("ج", " C")
        .replace("د", " D")
        # In Bengali these are the letters used for A-D in multiple choice questions
        .replace("অ", " A")
        .replace("ব", " B")
        .replace("ড", " C")
        .replace("ঢ", " D")
        # In Japanese these are the letters sometimes used for A-D in multiple choice questions
        .replace("Ａ", " A")
        .replace("Ｂ", " B")
        .replace("Ｃ", " C")
        .replace("Ｄ", " D")
        .strip()
    )


def url_to_fileobj(url: str, binary=False) -> Any:
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content) if binary else io.StringIO(response.text)
