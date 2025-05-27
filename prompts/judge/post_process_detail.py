POST_PROCESS = """
Your task is to post-process a student's answer. Any post-processing you make should not change the correctness or incorrectness of the answer. 
Do not add judgments or corrections. Your goal is to remove parts that could confuse a teacher when grading. Retain as much of the original reasoning as needed by copying the relevant parts exactly from the student's answer. To facilte the grading in later stage, you also need to use '\n' to split each reasoning step in your final post-processed result.

Specific Instructions:

(1) Handle Backtracking in Reasoning - The student's explanation may include changes in their thought process. When a later statement revises an earlier one, keep only the most recent statement.

(2) Handle Multiple Possibilities - The student's reasoning might show several alternative solution paths, only one of which is correct. In such cases, keep only the final correct solution and its corresponding explanation. Remove the incorrect or abandoned alternatives.

(3) Handle Normal Flow - If the student's answer presents sequential sub-tasks that build upon one another to arrive at the final solution, and these sub-tasks are not alternative (mutually exclusive) solution paths, then they are considered normal flow. In these cases, retain all intermediate steps, even if they seem redundant.

Important:
- When a student's answer involves multiple sub-tasks, do not automatically assume that the existence of more than one sub-task implies multiple alternative solution paths. If the sub-tasks represent sequential reasoning steps that cumulatively lead to the final answer (i.e., a normal flow), then keep all of these steps.
- Only remove earlier sub-task outputs if they represent alternative, incorrect paths (as in backtracking or multiple possibilities) that are later replaced by a final correct solution.
- Must not change the final answer. Do not try to fix anything as it will affect the judge in a bigger project. You MUST INCLUDE the student's final answer in the 'post-processd' field, it could be an integer, or a choice in A, B, C or D.
- Do not include the '[TOO_HARD]' or 'Suggestions', but only include the real reasoning steps.
- In all cases, you need to add '\n' to split each reasoning step 

Give your output in two entries: one labeled 'post-processed' with the revised answer and one labeled 'thinking' with your explanation of the process.


For example:

1. 
    Student's answer:
    Sub-task 1 output: thinking - The hexagon ABCDEF is equilateral and each pair of opposite sides are parallel. This means that the hexagon is symmetric and each side of the hexagon is equal in length. The extensions of segments AB, CD, and EF form a triangle with given side lengths. Since the hexagon is equilateral and opposite sides are parallel, the triangle formed by the extensions of these sides will have sides equal to the differences of the lengths of the hexagon's sides. The properties of parallel lines imply that the angles between the extensions and the sides of the hexagon are consistent, leading to a symmetric triangle with respect to the hexagon's sides.; answer - The side length of the hexagon is 80.
    Sub-task 2 output: thinking - The hexagon ABCDEF is equilateral and has opposite sides parallel. The triangle formed by the extensions of AB, CD, and EF has side lengths 200, 240, and 300. This forms a relationship where the side of the hexagon is equal to the difference between the semi-perimeter of the triangle and each of the triangle's sides. The semi-perimeter of the triangle is (200 + 240 + 300) / 2 = 370. Using the formula for the side of the hexagon, we have: x = 370 - 300 = 70, x = 370 - 240 = 130, and x = 370 - 200 = 170. For the hexagon to be equilateral, all these must be equal, which is not possible. Therefore, there is likely an error in the sub-task 1 answer or the provided logic. Re-evaluating based on the properties, the correct side length of the hexagon should be 80.; answer - 80

    Your output:
    'thinking': The student's answer contains two sub-task outputs that represent sequential reasoning. The final answer is taken from sub-task 1, and sub-task 2 is an alternative exploration that is not consistent with the final result. Since sub-task 2 does not contribute to the final correct answer, it is removed. I also need to add '\n' to split each step.

    'post-processed': The hexagon ABCDEF is equilateral and each pair of opposite sides are parallel. \n This means that the hexagon is symmetric and each side of the hexagon is equal in length. \n The extensions of segments AB, CD, and EF form a triangle with given side lengths. \n Since the hexagon is equilateral and opposite sides are parallel, the triangle formed by the extensions of these sides will have sides equal to the differences of the lengths of the hexagon's sides. \n The properties of parallel lines imply that the angles between the extensions and the sides of the hexagon are consistent, leading to a symmetric triangle with respect to the hexagon's sides.; \n answer - The side length of the hexagon is 80.

2.
    Student's answer:
    Sub-task 1 output: thinking - Initially, we find that the area of the circle is calculated as A = πr^2. However, I realize that the provided radius might be inaccurate. Correcting that, we use the new radius to get A = π(5)^2 = 25π.; answer - 25π.
    Sub-task 2 output: thinking - Although the first sub-task used r = 5, the second sub-task explores r = 4. Using r = 4, we would have A = 16π. Since the student later decides that the correct radius is indeed 5, we must ignore the calculation with r = 4.; answer - 25π.

    Your output:
    'thinking': The student's final answer is taken from sub-task 1 after correcting the radius. The calculation in sub-task 2 is an alternative that was rejected. Since only the final correct solution is needed, we remove the alternative. I also need to add '\n' to split each step.
    'post-processed': We use the new radius to get A = π(5)^2 = 25π.; \n answer - 25π.

3. 
    Student's answer:
    Sub-task 1 output: thinking - To solve the equation, we first try factoring. Factoring gives the solutions x = 2 and x = -3.
    Sub-task 2 output: thinking - Re-examining the equation, we note that a sign error was made in sub-task 1. The correct factoring yields x = 2 and x = 3.
    Sub-task 3 output: thinking - Among the possibilities, x = 2 is consistent with the problem constraints, while x = 3 does not satisfy the conditions. Therefore, we choose x = 2.; answer - 2.

    Your output:
    'thinking': The student explored different factoring methods. The final solution is chosen in sub-task 3 after evaluating the constraints. The earlier alternatives are removed. I also need to add '\n' to split each step.
    'post-processed': Factoring gives the solutions x = 2

4.
    Student's answer (Normal Flow Example):
    Sub-task 1 output: thinking - To solve for x in the equation 2x + 3 = 13, we first subtract 3 from both sides to get 2x = 10, and then divide both sides by 2 to find x = 5. answer - x = 5
    
    Sub-task 2 output: We then verify the solution by substituting x = 5 back into the equation: 2(5) + 3 = 10 + 3 = 13, which satisfies the equation.; answer - x = 5.

    Your output:
    'thinking': The student's answer follows a normal flow with no backtracking or alternative solution paths. All intermediate steps are maintained. I also need to add '\n' to split each step.
    'post-processed': To solve for x in the equation 2x + 3 = 13, we first subtract 3 from both sides to get 2x = 10, \n and then divide both sides by 2 to find x = 5. \n We then verify the solution by substituting x = 5 back into the equation: 2(5) + 3 = 13, \n which satisfies the equation.; \n answer - x = 5.

5. 
    Student's answer (Normal Flow Example):
    Sub-task 1 output: thinking - To solve for x in the equation 2x + 3 = 13, we first subtract 3 from both sides to get 2x = 10, and then divide both sides by 2 to find x = 5. answer: A
    
    Sub-task 2 output: We then verify the solution by substituting x = 5 back into the equation: 2(5) + 3 = 10 + 3 = 13, which satisfies the equation.; answer: A

    Your output:
    'thinking': The student's answer follows a normal flow with no backtracking or alternative solution paths. All intermediate steps are maintained. I also need to add '\n' to split each step.
    'post-processed': To solve for x in the equation 2x + 3 = 13, we first subtract 3 from both sides to get 2x = 10, \n and then divide both sides by 2 to find x = 5. \n We then verify the solution by substituting x = 5 back into the equation: 2(5) + 3 = 13, \n which satisfies the equation.; \n answer: A

5. 
    Student's answer (Normal Flow Example):
    Sub-task 1 output: thinking - To solve for x in the equation 2x + 3 = 13, we first subtract 3 from both sides to get 2x = 10, and then divide both sides by 2 to find x = 5. answer: A
    
    Sub-task 2 output: We then verify the solution by substituting x = 5 back into the equation: 2(5) + 3 = 10 + 3 = 13, which satisfies the equation.; answer: A

    Your output:
    'thinking': The student's answer follows a normal flow with no backtracking or alternative solution paths. All intermediate steps are maintained. I also need to add '\n' to split each step.
    'post-processed': To solve for x in the equation 2x + 3 = 13, we first subtract 3 from both sides to get 2x = 10, \n and then divide both sides by 2 to find x = 5. \n We then verify the solution by substituting x = 5 back into the equation: 2(5) + 3 = 13, \n which satisfies the equation.; \n answer: A


Now, review the following proposed answer based on the above rule.

[REASONING_PROCESS]

"""
