
import json
from code_archive_no_decompose import util_code, wrong_implementation

# remove the decomposision.

EXAMPLE = {
    "thought": """
    **Insights:**\nProvide your reasoning for the next effective agent architecture (an architecture may contain multiple agents), along with an explanation of the overall concept behind the design. 
    **Overall Architeure to solve each subquestion:**
    You overall architcutre and explan how this architecture can solve the given
    "**Implementation:**describe the implementation step by step."
    """,
    "name": "Name of your proposed architecture",

    "code": """def forward(self, taskInfo):
    from collections import Counter # must have this and always make sure you import everything needed
    # Your code here. IMPORTANT  
    # (1) You cannot call the existing architecture from the archive but you have to implment it from the code in the Discovered architecture archive
    # for example:
    # you cannot call 'COT' but you have to implement it eactly the same as the code in the Discovered architecture archive. 
    # name an agent 'reflexion' or 'debate' or 'cot_sc' also do not implement the blocks. Make sure you ACTUALLY IMPLEMENET them
    # for example, You need to impement the for-loop in COT-SC, LLM Debate and Reflextion
    # You should only change how they connect but not the function inside (setting and instrction can be different)

    # (2) To creat an agent, call the LLMAgentBase, must have 'model=self.node_model' in the parameters
    # the return of the call is always the same as the output fields,
    # for example: 
    # reasoning_agent = LLMAgentBase(['thinking', 'answer'], 'Reasoning Agent', model=self.node_model)

    # (3) You need to keep track of agent, for each agent inside the architecture (or block or node) output, please append it to a list named `agents` (please initialize it as `agents = []` at the beining of your function) so that we can keep track of the performance of each agents. It should contain the agent name (if setting is important to identify the agent, please include as well, e.g., round, ID), agent purpose, and the thinking and output of the agent. When you do self.make_final_answer, please also add `agents` as the last parameterss 
    # Takes debate as an example: 
    # max_round = ...(the max round you determine)
    # debate_agents = [LLMAgentBase(['thinking', 'answer'], 'Debate Agent', model=self.node_model, role=role, temperature=0.5) for role in ...(the role you design)]
    # all_thinking = []
    # all_answer = []
    # for r in range(max_round):
    #     round_thinking = []
    #     round_answer = []
    #     for i, agent in enumerate(debate_agents):
    #         if r == 0:
    #             t, a = agent([taskInfo, thinking1, answer1], cot_instruction)
    #             agents.append(f'Debate agent {agent.id}, round {r}, on the purpose of..., thinking: {t.content}; answer: {a.content}')
    #         else:
    #             t, a = agent([taskInfo, thinking1, answer1] + all_thinking[r-1], debate_instruction)
    #             agents.append(f'Debate agent {agent.id}, round {r}, on the purpose of..., thinking: {t.content}; answer: {a.content}')
    #         round_thinking.append(t)
    #         round_answer.append(a)
    #     all_thinking.append(round_thinking)
    #     all_answer.append(round_answer)
    # final_decision_agent = LLMAgentBase(['thinking', 'answer'], 'Final Decision Agent', model=self.node_model, temperature=0.0)
    # thinking2, answer2 = final_decision_agent(
    #     [taskInfo] + all_thinking[-1] + all_answer[-1],
    # )
    # agents.append(f'Final Decision agent, on the purpose of..., thinking: {thinking2.content}; answer: {answer2.content}')

    # Take reflexion as another example:
    # cot_agent = LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent', model=self.node_model, temperature=0.0)

    # # Instruction for providing feedback and correcting the answer
    # critic_agent = LLMAgentBase(['feedback', 'correct'], 'Critic Agent', model=self.node_model, temperature=0.0)
    # N_max = ...(the max round you determine) # Maximum number of attempts
    # # Initial attempt
    # cot_inputs = [taskInfo]
    # thinking, answer = cot_agent(cot_inputs, cot_initial_instruction, 0)
    # agents.append(f'CoT agent {cot_agent.id}, on the purpose of..., thinking: {thinking.content}; answer: {answer.content}')

    # for i in range(N_max):
    #     # Get feedback and correct status from the critic
    #     feedback, correct = critic_agent([taskInfo, thinking, answer], critic_instruction, i)
    #     agents.append(f'Critic agent {critic_agent.id}, on the purpose of..., thinking: {feedback.content}; answer: {correct.content}')
    #     if correct.content == 'True':
    #         break
            
    #     # Add feedback to the inputs for the next iteration
    #     cot_inputs.extend([thinking, answer, feedback])

    #     # Reflect on previous attempts and refine the answer
    #     thinking, answer = cot_agent(cot_inputs, cot_reflect_instruction, i + 1)
    #     agents.append(f'CoT agent {cot_agent.id}, on the purpose of..., thinking: {thinking.content}; answer: {answer.content}')

    # Take self-consistency as another example:
    # # Initialize multiple CoT agents with a higher temperature for varied reasoning
    # cot_agents = [LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent',  model=self.node_model, temperature=0.5) for _ in range(N)]
    
    # thinking_mapping = {}
    # answer_mapping = {}
    # possible_answers = []
    # for i in range(N):
    #     thinking, answer = cot_agents[i]([taskInfo], cot_instruction)
    #     agents.append(f'CoT agent {cot_agents.id}, on the purpose of..., thinking: {thinking.content}; answer: {answer.content}')
    #     possible_answers.append(answer.content)
    #     thinking_mapping[answer.content] = thinking
    #     answer_mapping[answer.content] = answer
    # answer = majority_voting(possible_answers)

    # thinking = thinking_mapping[answer]
    # answer = answer_mapping[answer]

    # (7) Put the saved agents to the final elf.make_final_answer. and keep track of `agents`, and actually implmenet the blocks by yourself (for-loop if COT-SC, Debate and Reflextion).

    final_answer = self.make_final_answer(thinking, answer agents)
    # Return only the final answer
    return final_answer
"""
}


base = f"""# Overview
You are an expert machine learning researcher testing various agentic systems. Given a set of architectures in the archive and the question. Note that architecture can contain multiple agents, and agnet mean a LLM that use for specifical objectives by specifclaied setting (instruction, tempreture...)

Your objective is to 

(2) Given the task, design connections between existing blocks to adress each of them. 
You should structure the architecture as a multi-layered network. Each existing architecture (or blocks) serves as a node, while connections between them act as edges, forming a structured hierarchy of interactions. Additionally, you must determine the number of layers in the network.

For example, if the exising architectures are 'COT, COT_SC, Reflexion, LLM_debate' and you determine that there can be 3 layers:

Example Setup


Available architectures:
COT, COT_SC, Reflexion, LLM_debate

Network with 3 Layers:

Layer 1: COT  COT_SC  Reflexion  LLM_debate  
Layer 2: COT  COT_SC  Reflexion  LLM_debate   
Layer 3: COT  COT_SC  Reflexion  LLM_debate  

Connection Strategies:

1. Linear Connection: Directly link two block to pass information forward.
Example: [COT] -> [LLM_debate] (Single connection and exit)

2. Multi-Layer Connection: An block can appear in multiple layers, forming deeper reasoning structures.
Example: [COT] -> [LLM_debate] -> [COT -> Reflexion] (COT appears in both Layer 1 and Layer 3)

IMPORTANT:


Your aim is to design an optimal block connection that can performe well on the given task. Your code should implment the exising blocks given in the archive (the 'code' entry of blocks) as it-is without modication: Do not propose new blocks or modify existing ones and only change the connections between the given blocks, but block setting like instruction, tempreture are allowed to modify


{util_code}

# Output Instruction and Example:
The first key should be ("thought"), and it should capture your thought process for and it should capture your thought process for reconnecting the exisitng blocks in achived. 

In the "(thought)" section, include the following:

(1) **Overall Architecture**: 

Given the task, design connections between existing blocks to adress each of them. describe your reasoning and the overall concept behind the connection design and finally detail the implementation steps. All connection must betweene exising blocks in the archive and no new blocks can be made. The format must strickly follow: 

(a) Use '->' for connection. for example, 'CoT (exisitng block name) -> LLM debate (another exising block name)' means connect the CoT block and the LLM debate block to address the given correspondingly.

The second key ("name") corresponds to the name of your block connection architecture. 
Finally, the last key ("code") corresponds to the exact “forward()” function in Python code that you would like to try. You must write a COMPLETE CODE in "code": Your code will be part of the entire project (so do not implement any other part), so please implement complete, reliable, reusable code snippets. You cannot call the exising blocks (e.g., COT, COT-SC) by its name, but must implement them as it is in the achive.

Here is an example of the output format for the new connected block architecture:

[EXAMPLE]

You must use the exact function interface used above. You need to specify the instruction, input information, and the required output fields for various LLM agents to do their specific part of the architecture. DON'T try to use some function that doesn't exisit.
Also, it could be helpful to set the LLM’s role and temperature to further control the LLM’s response. Note that the LLMAgentBase() will automatically parse the output and return a list of “Infos”. You can get the content by Infos.content. 
DO NOT FORGET the taskInfo input to LLM if you think it is needed, otherwise LLM will not know about the task.

{wrong_implementation}


# Your task
You are deeply familiar with LLM prompting techniques and LLM agent works from the literature. Your goal is to maximize the specified performance metrics by reconnecting the exisitng block in archived. Do not try to propose new block or modify the exising block, and only change the connection but block setting like instruction, tempreture are allowed to modify
Observe the discovered blocka carefully and think about what insights, lessons, or stepping stones can be learned from them.
You are encouraged to draw inspiration from related agent papers or academic papers from other research areas.
Use the knowledge from the archive and inspiration from academic literature to propose the new connection.

Below is the question to solve:\n\n[QUESTION]
"""