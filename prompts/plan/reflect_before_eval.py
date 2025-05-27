import json

Reflexion_prompt_1 = f""""[EXAMPLE]Carefully review the proposed new architecture and reflect on the following points:"

1. **optimalness**: Assess whether your proposed architecture is optimal for the benchmark. If you determine that the proposed architecture is not optimal, suggest a new architecture that addresses these shortcomings. 
- Make sure to check the difference between the proposed architecture and previous attempts.
- Compare the proposal and the architectures in the archive CAREFULLY, including their actual differences in the implementation.
- Decide whether the current architecture is optimal.
- USE CRITICAL THINKING!

2. **Implementation Mistakes**: Identify any mistakes you may have made in the implementation. Review the code carefully, debug any issues you find, and provide a corrected version. REMEMBER checking "## WRONG Implementation examples" in the prompt.

3. **Improvement**: Based on the proposed architecture, suggest improvements in the detailed implementation that could increase its performance or effectiveness. In this step, focus on refining and optimizing the existing implementation without altering the overall design framework, except if you want to propose a different architecture if the current is not interesting.
- Observe carefully about whether the implementation is actually doing what it is supposed to do.
- Check if there is redundant code or unnecessary steps in the implementation. Replace them with effective implementation.
- Try to avoid the implementation being too similar to the previous agent.

And then, you need to improve or revise the implementation, or implement the new proposed architecture based on the reflection.

Your response should be organized as follows:

"reflection": Provide your thoughts on the optimalness of the architecture, identify any mistakes in the implementation, and suggest improvements.

"thought": Revise your previous proposal or propose a new architecture if necessary, using the same format as the example response.

"name": Provide a name for the revised or new architecture. (Don't put words like "new" or "improved" in the name.)

"code": Provide the corrected code or an improved implementation. Make sure you actually implement your fix and improvement in this code. Make sure only return the final answer, i.e., the output of self.make_final_answer
"""

Reflexion_prompt_2 = """Using the tips in "## WRONG Implementation examples" section, revise the code further.
Your response should be organized as follows:
Put your new reflection thinking in "reflection". Repeat the previous "thought" and "name", and update the corrected version of the code in "code". Make sure only return the final answer, i.e., the output of self.make_final_answer
"""


