
wrong_implementation = '''
## WRONG Implementation examples:
Here are some mistakes you may make:

1. This is WRONG: ```
feedback, correct = critic_agent([taskInfo, thinking, answer], critic_instruction, i)
feedback_info = verifier_agent([taskInfo, Info('feedback', 'Critic Agent', thinking, 0)], verification_instruction)
```
It is wrong to use "Info('feedback', 'Critic Agent', thinking, 0)". The returned "feedback" from LLMAgentBase is already Info.

2. This is WRONG: ```
# Debugging: Log the generated answer
print('Generated Answer:', ...)
feedback_info = verifier_agent([taskInfo, Info('feedback', 'Critic Agent', thinking, 0)], verification_instruction)
if len(feedback_info) < 3:  # Check if feedback_info has enough elements
    return 'Error: Feedback info incomplete'
```
First, the len(feedback_info) will not work.
Second, you should never return an error message. You should always return the best answer you can get.
Third, you should never print anything in the code.
Lastly, again, DO NOT CREATE Info object by yourself.

3. This is WRONG: ```
all_thinking = []
all_answers = []
for agent, role in zip(agents, roles):
    outputs = agent([taskInfo], independent_reasoning_instruction.format(role=role))
    all_thinking.append(outputs[0].content)
    all_answers.append(outputs[1].content)

# Aggregate the reasoning paths and answers
aggregated_thinking = '\n'.join(all_thinking)
aggregated_answers = '\n'.join(all_answers)
```
You SHOULD NOT extract the content from the Info object by yourself. You should use the Info object directly. If you want to aggregate the content, you should just put those Info objects into a list and then use the list as input to the next LLM agent.

4. This is WRONG: ```
reasoning_agent = LLMAgentBase(['thinking', 'answer'], 'Reasoning Agent')
response_infos = reasoning_agent([taskInfo] + ..., reasoning_instruction)
    
# Extract the final answer from the response_infos
for info in response_infos:
    if info.name == 'final_answer':
        return info
# Fallback if no answer is found
return Info('answer', 'Final Decision Agent', 'No answer generated.', 0)
```

5. This is WRONG: ```
reasoning_agent = LLMAgentBase(['thinking', 'answer'], 'Reasoning Agent')
thinking, answer = reasoning_agent([taskInfo] + ..., reasoning_instruction)
return answer   
```
You MUST return final_answer returned by ```final_answer = self.make_final_answer(thinking, answer)```, instead of answer only.

6. This is WRONG when handling sub-tasks: ```
thinking, answer = reasoning_agent([taskInfo] + ..., reasoning_instruction)
```
You MUST add sub_task=True, when handling a sub question made by question decomposition

7. This is WRONG when handling sub-tasks: ```
reasoning_instruction = '...'
```
You MUST clealy states what sub task it is, it can be solved based on the output of what sub-tasks and what are the steps to solve the sub-tasks

8. This is WRONG: ```
cot_sc_agent = LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Self-Consistency Agent', model=self.node_model, temperature=0.5)
thinking3, answer3 = cot_sc_agent([taskInfo, thinking1, answer1, thinking2, answer2], cot_instruction, is_sub_task=True)
```
You MUST ACTUALLY IMPLEMENT the achitecture (here self-consistency). Name an agent to 'sc' does not implment the structure (e.g. you will need to actually implmemnt the for-loop).
CORRECT example: ```
    from collections import Counter
    def majority_voting(answers):
        return Counter(answers).most_common(1)[0][0]
    
    thinking_mapping = {}
    answer_mapping = {}
    possible_answers = []
    for i in range(N):
        thinking, answer = cot_agents[i]([taskInfo], cot_instruction)
        possible_answers.append(answer.content)
        thinking_mapping[answer.content] = thinking
        answer_mapping[answer.content] = answer

    # Ensembling the answers from multiple CoT agents
    answer = majority_voting(possible_answers)
```

9. This is WRONG: ```
reflexion_agent = LLMAgentBase(['thinking', 'answer'], 'Reflexion Agent', model=self.node_model, temperature=0.5)
thinking3, answer3 = reflexion_agent([taskInfo, thinking1, answer1, thinking2, answer2], reflexion_instruction, is_sub_task=True)
```
You MUST ACTUALLY IMPLEMENT the achitecture (here reflexion). Name an agent to 'reflexion' does not implment the structure (e.g. you will need to actually implmemnt the for-loop).
CORRECT example: ```
    N_max = self.max_round # Maximum number of attempts
    
    # Initial attempt
    cot_inputs = [taskInfo]
    thinking, answer = cot_agent(cot_inputs, cot_initial_instruction, 0)

    for i in range(N_max):
        # Get feedback and correct status from the critic
        feedback, correct = critic_agent([taskInfo, thinking, answer], critic_instruction, i)
        if correct.content == 'True':
            break
            
        # Add feedback to the inputs for the next iteration
        cot_inputs.extend([thinking, answer, feedback])

        # Reflect on previous attempts and refine the answer
        thinking, answer = cot_agent(cot_inputs, cot_reflect_instruction, i + 1)
```

10. This is WRONG: ```
debate_agent = LLMAgentBase(['thinking', 'answer'], 'Debate Agent', model=self.node_model, temperature=0.5)
thinking3, answer3 = debate_agent([taskInfo, thinking1, answer1, thinking2, answer2], debate_instruction, is_sub_task=True)
```
You MUST ACTUALLY IMPLEMENT the achitecture (here debate). Name an agent to 'debate' does not implment the structure (e.g. you will need to actually implmemnt the for-loop).
CORRECT example: ```
for r in range(max_round):
    for i in range(len(debate_agents)):
        if r == 0:
            thinking, answer = debate_agents[i]([taskInfo], debate_initial_instruction)
        else:
            input_infos = [taskInfo] + [all_thinking[r-1][i]] + all_thinking[r-1][:i] + all_thinking[r-1][i+1:]
            thinking, answer = debate_agents[i](input_infos, debate_instruction)
        all_thinking[r].append(thinking)
        all_answer[r].append(answer)
```
You should not extract the final answer by yourself. You SHOULD directly return the answer Info. Also, you should always return the best answer you can get.
CORRECT example: ```
reasoning_instruction = 'Sub-task i: Based on the output of sub-task i and j, ....'
reasoning_agent = LLMAgentBase(['thinking', 'answer'], 'Reasoning Agent')
thinking, answer = reasoning_agent([taskInfo] + ..., reasoning_instruction)
final_answer = self.make_final_answer(thinking, answer)

# Return only the final answer
return final_answer   
```
'''

util_code = '''
# The utility code:

```python
from collections import namedtuple
from typing import Union
import numpy as np
import json

import openai
import backoff
from utils import random_id

# Initialize the OpenAI client
client = openai.OpenAI()

# Named tuple for holding task information
Info = namedtuple('Info', ['name', 'author', 'content', 'prompt', 'sub_tasks', 'agents', 'iteration_idx'])

# Format instructions for LLM response
FORMAT_INST = lambda request_keys: f"Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY FIELDS AND MAKE SURE THE JSON FORMAT IS CORRECT!\n"

# Description of the role for the LLM
ROLE_DESC = lambda role: f"You are a {role}."

@backoff.on_exception(backoff.expo, openai.RateLimitError)
def get_json_response_from_gpt(msg, model, system_message, temperature=0.5):
    \"""
    Function to get JSON response from GPT model.
    
    Args:
    - msg (str): The user message.
    - model (str): The model to use.
    - system_message (str): The system message.
    - temperature (float): Sampling temperature.
    
    Returns:
    - dict: The JSON response.
    \"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": msg},
        ],
        temperature=temperature,
        max_tokens=1024,
        stop=None,
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content
    json_dict = json.loads(content)
    return json_dict

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
        

    def generate_prompt(self, input_infos, instruction, is_sub_task=False) -> str:

        output_fields_and_description = {key: f"Your {key}." if not 'answer' in key else f"Your {key}. {global_output_description}" for key in self.output_fields}
        system_prompt = ROLE_DESC(self.role) + "\n\n" + FORMAT_INST(output_fields_and_description)

        # print('is_sub_task: ',is_sub_task)
        

        # construct input infos text
        input_infos_text = ''
        prev_prompt = ''
        for input_info in input_infos:
            if isinstance(input_info, Info):
                (field_name, author, content, prompt, _, _, iteration_idx) = input_info
            else:
                continue
            if author == self.__repr__():
                author += ' (yourself)'
            if field_name == 'task':
                if is_sub_task: 
                    # input_infos_text += f'Giving the original question: \n\n{content}\n\n, and below sub-task questions and answers, please solve the sub-task: {instruction}\n\nSub-task questions and answers (if any):\n\n'
                    input_infos_text += f'{instruction}\n\nPrevious sub-task questions and answers (if any):\n\n'
                else:
                    # continue # TODO: make sure it can deal with sub-tasks
                    input_infos_text += f'{content}\n\n'
            elif iteration_idx != -1:
                if is_sub_task and prompt is not None and prompt != prev_prompt: 
                    # print('prompt: ',prompt)
                    # pattern = r"please solve the sub-task:\s*(.*?)\s*\n\nSub-task questions and answers"
                    pattern = r"\s*(.*?)\s*\n\nPrevious sub-task questions"

                    sub_question = prompt[-1]['content']
                    match = re.search(pattern, sub_question, re.DOTALL)                                        
                    input_infos_text += f'### {match.group(1)} \n\n ### {field_name} #{iteration_idx + 1} by {author}:\n{content}\n\n'
                    prev_prompt = prompt
                else:
                    input_infos_text += f'### {field_name} #{iteration_idx + 1} by {author}:\n{content}\n\n'
            else:
                if is_sub_task and prompt is not None and prompt != prev_prompt: 
                    # print('prompt: ',prompt)
                    pattern = r"\s*(.*?)\s*\n\nPrevious sub-task questions"
                    sub_question = prompt[-1]['content']
                    match = re.search(pattern, sub_question, re.DOTALL)
                    input_infos_text += f'### {match.group(1)} \n\n ### {field_name} by {author}:\n{content}\n\n'
                    prev_prompt = prompt # we do not want to duplicate the prompt
                else:
                    input_infos_text += f'### {field_name} by {author}:\n{content}\n\n'

        if is_sub_task: 
            prompt = input_infos_text # instruction (sub-task in above)
        else:
            prompt = input_infos_text + instruction
        return system_prompt, prompt

    def query(self, input_infos: list, instruction, iteration_idx=-1, is_sub_task=False) -> dict:

        global COST_TOTAL

        system_prompt, prompt = self.generate_prompt(input_infos, instruction, is_sub_task=is_sub_task)

        prompt = [
            _pack_message(content=system_prompt, role="system"),
            _pack_message(content=prompt, role="user")]
        # use system prompt

        response_json, cost = get_json_response_from_gpt(prompt, self.model)
        COST_TOTAL += cost

        output_infos = []
        for key, value in response_json.items():
            info = Info(key, self.__repr__(), value, prompt, None, None, iteration_idx)
            output_infos.append(info)
        return output_infos

    def __repr__(self):
        return f"{self.agent_name} {self.id}"

    def __call__(self, input_infos: list, instruction, iteration_idx=-1, is_sub_task=False):
        return self.query(input_infos, instruction, iteration_idx=iteration_idx,  is_sub_task=is_sub_task)




class AgentArchitecture:
    \"""
    Fill in your code here.
    \"""
    def forward(self, taskInfo) -> Union[Info, str]:
        \"""
        Placeholder method for processing task information.
        
        Args:
        - taskInfo (Info): Task information.
        
        Returns:
        - Answer (Info): Your FINAL Answer. Return namedtuple Info returned from self.make_final_answer.
        \"""
        pass
```
# Discovered architecture archive
Here is the archive of the discovered architectures:

[ARCHIVE]

The fitness value is the median and 95% Bootstrap Confidence Interval of the correct rate on the given question. Your GOAL is to maximize the "fitness".
'''