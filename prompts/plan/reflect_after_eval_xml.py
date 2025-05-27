import json

Reflexion_after_eval_prompt = f""""
Carefully review the proposed new architectures ("code" entry), the answer of each sub-tasks ("sub_tasks" entry) , the answer of each agnets ("agents" entry), the final response ("final_reponse" entry) and the fitness ("fitness" entry, i.e., the median and 95% Bootstrap Confidence Interval of the correct rate on the given question), and the 'memory' (previous final answer extracted from their reponse and the corresponding fitness score, in the format of a list of dictionary final answer: fitness) in all the history user and assistant answers. Reflect on the following points:

1. **Solvable**: Assess whether all sub-tasks are solvable by the corresponidng block via checking the output answer of each sub-task. 

- Case 1: if the answer of the sub-task explicitly contain [TOO_HARD]. 

This clearly suggests that the sub-task is too hard, and you need to further decompose the task or update the architecture. Consider the suggestion given after the [TOO_HARD] (you can see the 'Suggestions:' next to the [TOO_HARD]) and improve your decomposison and architecture accrodingly. See below (a) and (b) for more information about what need to be ensure

- Case 2: If the sub-task answr is incoorect. That means it is not solvable, which need to be improved. 

There could be two reasons that cause cases 1 and 2: 

- Reason (a) the task is still too difficult for the block, so the sub-task need to be further decomposed. 

When proposing new sub-task, make sure 
(i) it is specific and detailed enough to solve and to help achieve the final answer to the given question.
(ii) all information required to answer the question is proveded by the previous answers or the instruction. 
(iii) the related sub-tasks thinking and answers have correctly input to the current sub-task by adding it to the taskInfo list when calling the agent. 
(iv) The output should be helpful to solve the next sub-task. Also make sure the sub-task connection is clearly by clealy state 'Based on the output of sub-task i..' in the sub-task instruction

- Reason (b) some agnets in the block is malfunctional or the underlying LLM is too weak to solve the sub-task alone. This can be detemined by checking the agents output to decide whether it works as expected. If this is the case, then we need to get rid of the block and use another block in the architecture. There are then two possibilities
    (i) the agent in the block is not optimal to solve the sub-task, setting needed to be improved (instruction, tempreture...)
    (ii) the agent architecutre in the block is not optimal, a new block that combine exisitng blocks in a different way or different settings need to be proposed

Please identify and jutify which cases (case 1 or 2 or both) and reasons (a or b or both) the proposed architecture falls into. If it is (a), What is the decomposition issue. If it is (b) (and (i) or (ii)), what is the block and agent issue. It could also be both. Carefully consider both cases and do mot miss any one of them.

2. **Completeness**: Are the sub-tasks include all neccessay information from the irginal query that can ensure the aggregation of sub-task responses can effectively yild a comprehensive answer to the user query? Note that while a sub-task might include only part of the neccessary information, it is not allowable for any particular piece of critical information to be omitted from all sub-tasks. Make sure the sub-task are connected to the prerequisite sub-tasks so that there is enough information to solve it.

3. **Fitness**: Your final goal is to optimize the fitness score after updating the architectures and/or task decomposision based on (1) and (2). The fitness is computed based on the final reponse. If it is low, it indicates that your final answer is incorrect. In your updated architecture or task decomposition, you need to make sure they will update your final response accordingly. 

And then, you need to improve or revise the implementation, or implement the new proposed architecture based on the reflection.

Your response should add new entries to the previous answers:

<reflection> entry: 
(1) Give a brief summary of how the outputs after round [last_round] has changed from the the outputs after round [last_last_round]. Using the foramt: 
`change item 1: [item 1 in outputs after round [last_round]] vs [item 1 in outputs after round [last_last_round]]
change item 2: [item 2 in outputs after round [last_round]] vs [item 2 in outputs after round [last_last_round]]
...`
Your <reflection>, <thought>, <name> and <code> should based on the outputs after round [last_round] while take the earlier rounds (from round 0 to round [last_round]) insights into aacount.
(2) Provide your thoughts on the Solvable, Completeness and Fitness of the architecture and/or task decomposision (which sub-tasks are incorrect? which agent in which block are malfunctional?)
(3) identify any inappropriate in the implementation, and suggest improvements (why the improvements can lead to a better final answer? Expain in detail)


IMPORTANT: Do not use any XML format or tags in the entry. For example, do not use '<solvable>...</solvable>' or '<completeness>...</completeness>' etc. but simply use plain text inside the entry

<thought> entry: Revise your previous proposal or propose a new architecture if necessary, using the same format as the example response. The revision should be based on the <thought> after round [last_round] ONLY

For case (a), Give the 

(1) **Further Decomposion**: Compre to your previous decomposition attemps in the Discovered architecture archive (see the 'thought' entries), how do you futher decompose the questions? please give details by the following format: 'last sub-task 1 -> (further decompose to) new sub-task 2, new sub-task 3..., new sub-task n)' Give detail compare and justify how the new sub-tasks are eaiser than the old one. Do not give answer or short-cut (an example for shot-cut: 'output exactly the following:..', which is not allowed) in the sub-task instruction in any format, but only do the planing. Justify (1) why the new sub-tasks are sovlable and (2) how the sub-tasks can achieve the final answer to the original question.


For case (b), Give the 

(2) **Improved subtask architeture**: Compare to your last block attemps in the history (last answer), which sub-task architecture need to be imrpoved? How do you futher connecting them in a different ways so that the resultsing subtask architeture is able to solve the corresponding sub-task? please give details by the following format: 'last sub-task architeture (what architecute was it?) (aims to address sub-task i)-> (improve to) new sub-task architeture (what is the main difference?)' Give detail compare and justify how the new connection is improved than the old one. Note that the new connection still follow the rules that you need need to determine the number of layers as well as the connection, but do not propose new blocks or modify existing ones in the sub-task architecture, and just changes the connection among the block, but block setting like instruction, tempreture are allowed to modify

For case where the final response is not updated and still the same mistaken answer, Give the

(3) **Updated Subtask Instruction**. Read the 'memeory' entry, improve the sub-task instruction so that it can know explicitly that some answers should be avoided. For example, you can add `It is known that (wrong answers, include all wrong answers from the 'memeory' filed, i.e., all final answers have 0 fitness score) is not correct` to the last sub-task so that the sub-architecture knows it needs to avoid it.


IMPORTANT: Do not use any XML format or tags in the entry. For example, do not use '<decomposition>...</decomposition>' etc. but simply use plain text inside the entry.

<name> entry: Provide a name for the revised or new architecture. (Don't put words like "new" or "improved" in the name.)

<code> entry: Update the code based on your reflection and thought. Do not change the function name, i.e., your function should still be 'def forward(self, taskInfo)'. Make sure you actually implement ALL the improvements mentioned in the reflection and thougths and improvement in this code. Make sure only return the final answer, i.e., the output of self.make_final_answer. All the requirement on code still valid: You must write a COMPLETE CODE in "code": Your code will be part of the entire project (so do not implement any other part), so please implement complete, reliable, reusable code snippets. Do not make any syntactic mistakes. The update should be based on the <code> after round [last_round] ONLY

For example. 
if single quote (') is used in string, then double quote (") should be used for the whole string.
This is WRONG
`f'CoT-SC agent ABC, on the purpose of determining changes to Maxwell's'`. 
This is wrong becuse single qupte is used (Maxwell's) within the sting but single quote is used again for the f-string (f''). This will casue unterminated string error. To correct it, one should use double quote for f-stirng, i.e., `f"CoT-SC agent ABC, on the purpose of determining changes to Maxwell's"`

"""

