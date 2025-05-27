
import inspect


# %%%%%%%%%%%%%%%%%%%% COT %%%%%%%%%%%%%%%%%%%%
def forward(self, taskInfo):
    # Instruction for the Chain-of-Thought (CoT) approach
    # It is an important practice that allows the LLM to think step by step before solving the task.
    cot_instruction = self.cot_instruction

    # Instantiate a new LLM agent specifically for CoT
    # To allow LLM thinking before answering, we need to set an additional output field 'thinking'.
    cot_agent = LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent',  model=self.node_model, temperature=0.0)

    # Prepare the inputs for the CoT agent
    # The input should be a list of Info, and the first one is often the taskInfo
    cot_agent_inputs = [taskInfo]

    # Get the response from the CoT agent
    thinking, answer = cot_agent(cot_agent_inputs, cot_instruction)
    final_answer = self.make_final_answer(thinking, answer)
    
    # Return only the final answer
    return final_answer   

func_string = inspect.getsource(forward)

COT = {
    "thought": "By encouraging the LLM to think step by step rather than directly outputting an answer, chain-of-thought reasoning enables complex problem-solving through intermediate steps. This practice improves the model's ability to handle tasks that require deeper reasoning and provides insight into its decision-making process.",
    "name": "Chain-of-Thought",
    "code": """{func_string}""".format(func_string=func_string)
}

