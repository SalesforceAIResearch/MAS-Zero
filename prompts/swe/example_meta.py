import inspect

def forward(self, taskInfo):
    from collections import Counter
    sub_tasks = []
    agents = []

    # Sub-task 1.1: Analyze the _cstack function specifically for its handling of identity matrices in nested CompoundModels
    cot_instruction = "Sub-task 1.1: Analyze the _cstack function for its handling of identity matrices in nested CompoundModels."
    cot_agent = LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent', model=global_node_model, temperature=0.0)
    thinking1_1, answer1_1 = cot_agent([taskInfo], cot_instruction, is_sub_task=True)
    sub_tasks.append(f'Sub-task 1.1 output: thinking - {thinking1_1.content}; answer - {answer1_1.content}')
    agents.append(f'CoT agent {cot_agent.id}, on the purpose of analyzing _cstack, thinking: {thinking1_1.content}; answer: {answer1_1.content}')

    # Sub-task 1.2: Propose a solution for correctly using identity matrices in the _cstack function
    reflexion_instruction = "Sub-task 1.2: Based on the output of sub-task 1.1, propose a solution for correctly using identity matrices in the _cstack function."
    reflexion_agent = LLMAgentBase(['thinking', 'answer'], 'Self-Refine Agent', model=global_node_model, temperature=0.5)
    thinking1_2, answer1_2 = reflexion_agent([taskInfo, thinking1_1, answer1_1], reflexion_instruction, is_sub_task=True)
    sub_tasks.append(f'Sub-task 1.2 output: thinking - {thinking1_2.content}; answer - {answer1_2.content}')
    agents.append(f'Reflexion agent {reflexion_agent.id}, on the purpose of proposing a solution, thinking: {thinking1_2.content}; answer: {answer1_2.content}')

    # Sub-task 1.3: Implement the proposed solution and verify its correctness
    cot_instruction = "Sub-task 1.3: Based on the output of sub-task 1.2, implement the proposed solution and verify its correctness."
    cot_agent = LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent', model=global_node_model, temperature=0.0)
    thinking1_3, answer1_3 = cot_agent([taskInfo, thinking1_2, answer1_2], cot_instruction, is_sub_task=True)
    sub_tasks.append(f'Sub-task 1.3 output: thinking - {thinking1_3.content}; answer - {answer1_3.content}')
    agents.append(f'CoT agent {cot_agent.id}, on the purpose of implementation, thinking: {thinking1_3.content}; answer: {answer1_3.content}')

    # Sub-task 1.4: Write a patch file to apply the changes
    cot_instruction = "Sub-task 1.4: Based on the output of sub-task 1.3, write a patch file to apply the changes. It is known that the previous patches were incorrect."
    cot_agents = [LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent', model=global_node_model, temperature=0.5) for _ in range(global_max_sc)]
    thinking_mapping = {}
    answer_mapping = {}
    possible_answers = []
    for i, agent in enumerate(cot_agents):
        thinking, answer = agent([taskInfo, thinking1_3, answer1_3], cot_instruction, is_sub_task=True)
        agents.append(f'CoT agent {agent.id}, on the purpose of writing a patch file, thinking: {thinking.content}; answer: {answer.content}')
        possible_answers.append(answer.content)
        thinking_mapping[answer.content] = thinking
        answer_mapping[answer.content] = answer
    final_patch = Counter(possible_answers).most_common(1)[0][0]
    thinking1_4 = thinking_mapping[final_patch]
    answer1_4 = answer_mapping[final_patch]
    sub_tasks.append(f'Sub-task 1.4 output: thinking - {thinking1_4.content}; answer - {answer1_4.content}')

    final_answer = self.make_final_answer(thinking1_4, answer1_4, sub_tasks, agents)
    return final_answer   

EXAMPLE_META = inspect.getsource(forward)