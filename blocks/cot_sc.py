import inspect


# %%%%%%%%%%%%%%%%%%%% COT-SC %%%%%%%%%%%%%%%%%%%%

def forward(self, taskInfo):
    # Instruction for step-by-step reasoning
    cot_instruction = self.cot_instruction
    N = self.max_sc # Number of CoT agents

    # Initialize multiple CoT agents with a higher temperature for varied reasoning
    cot_agents = [LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent',  model=self.node_model, temperature=0.5) for _ in range(N)]

    # Majority voting function to select the most common answer
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
    print('possible_answers: ',possible_answers)

    thinking = thinking_mapping[answer]
    answer = answer_mapping[answer]

    final_answer = self.make_final_answer(thinking, answer)

    return final_answer  

func_string = inspect.getsource(forward)

COT_SC = {"thought": "While an LLM can arrive at the correct answer, its reasoning may vary. By repeatedly asking the same question with high temperature settings, we can generate different reasoning paths. We then combine multiple answers from these Chain-of-Thought (CoT) agents to produce a more accurate final answer through ensembling.",
          "name": "Self-Consistency with Chain-of-Thought",
            "code": """{func_string}""".format(func_string=func_string)
              }
