import inspect


# %%%%%%%%%%%%%%%%%%%% LLM-Debate (collabrative) %%%%%%%%%%%%%%%%%%%%


def forward(self, taskInfo):
    # Instruction for initial reasoning
    debate_initial_instruction = self.cot_instruction

    # Instruction for debating and updating the solution based on other agents' solutions
    debate_instruction = "Given solutions to the problem from other agents, consider their opinions as additional advice. Please think carefully and provide an updated answer. Put your thinking process in the 'thinking' field and the updated answer in the 'answer' field. "
    
    # Initialize debate agents with different roles and a moderate temperature for varied reasoning
    debate_agents = [LLMAgentBase(['thinking', 'answer'], 'Debate Agent',  model=self.node_model, role=role, temperature=0.5) for role in self.debate_role]

    # Instruction for final decision-making based on all debates and solutions
    final_decision_instruction = "Given all the above thinking and answers, reason over them carefully and provide a final answer. Put your thinking process in the 'thinking' field and the final answer in the 'answer' field."
    final_decision_agent = LLMAgentBase(['thinking', 'answer'], 'Final Decision Agent',  model=self.node_model, temperature=0.0)

    max_round = self.max_round # Maximum number of debate rounds
    all_thinking = [[] for _ in range(max_round)]
    all_answer = [[] for _ in range(max_round)]

    # Perform debate rounds
    for r in range(max_round):
        for i in range(len(debate_agents)):
            if r == 0:
                thinking, answer = debate_agents[i]([taskInfo], debate_initial_instruction)
            else:
                input_infos = [taskInfo] + [all_thinking[r-1][i]] + all_thinking[r-1][:i] + all_thinking[r-1][i+1:]
                thinking, answer = debate_agents[i](input_infos, debate_instruction)
            all_thinking[r].append(thinking)
            all_answer[r].append(answer)
    
    # Make the final decision based on all debate results and solutions
    thinking, answer = final_decision_agent([taskInfo] + all_thinking[max_round-1] + all_answer[max_round-1], final_decision_instruction)
    final_answer = self.make_final_answer(thinking, answer)

    return final_answer

func_string = inspect.getsource(forward)

LLM_debate = {
    "thought": "By letting different LLMs debate with each other, we can leverage their diverse perspectives to find better solutions for tasks.",
    "name": "LLM Debate",
    "code": """{func_string}""".format(func_string=func_string)

}

