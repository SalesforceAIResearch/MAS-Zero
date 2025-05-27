MATH_PROMPT = """
    Your task is to review a given question and the student's proposed answer. You must determine whether the answer is correct by strictly following these seven steps:

    1. Identify All Equations and Conditions/Constraints
    - Extract all mathematical equations used in the student's answer. Ignore the question in this step, only extract from the student's answer
    - Extract all Conditions/Constraints (both explicit in the problem statement and implicit from the problem’s context or geometry). Ignore the student's answser in this step, only extract from the student's answer. 
        Guidance for Extracting Implicit Conditions/Constraints:
            - Read the problem carefully and consider the overall context. For example, in geometry problems, implicit conditions might include assumptions like points lying on a circle, lines being parallel, or angles having specific relationships.
            - Rely on well-known theorems or properties related to the problem's subject matter. For instance, if a shape is inscribed in a circle, recall that the inscribed angle theorem or the properties of cyclic quadrilaterals might imply certain angle or side conditions.
            - Compare the problem with standard methods. Ask: "What conditions must a correct solution include?" Common implicit conditions include collinearity, symmetry, or a fixed geometric relation.

        Example:
        Extracted Equations:
            - Equation 1: E1(x, y, …) = 0
            - Equation 2: E2(x, y, …) = F(x, y, …)
        Extracted Conditions/Constraints:
            - Condition 1: Variables satisfy specific relations (e.g., x > 0, y ∈ ℤ).
            - Condition 2: A geometric configuration (e.g., a triangle is inscribed in a circle, or a point lies on a particular line).
            - Condition 3 (Implicit): In a cyclic quadrilateral, the sum of opposite angles must equal 180°, which must be verified even if not explicitly stated.

    2. Verify the Applicability of Each Equation to the Problem by writing equqations
    - For each extracted equation, verify that it accurately models the problem’s Conditions/Constraints and the geometric or algebraic configuration.
    - Use a checklist for modeling:
        - Does the equation or ratio apply only under specific Conditions/Constraints (e.g., when a point lies on side BC)?
        - Does the problem define the point (or variable) in the same way as assumed by the equation?
        - If the equation applies only in a particular scenario (e.g., using BP/PC = AB²/AC² when the point is on BC) but the problem defines the point differently (e.g., on the circumcircle), then flag it as a misapplied equation.
    - Be rigorous. Do not accept an equation as valid unless you have clear evidence that it matches the problem’s setup. If in doubt, note the potential misapplication. Pay extra attention to the following examples and common errors

    - Examples:
        - Angle Bisector Theorem:  
            If a student uses the equation  
            BD\DC = AB\AC,
            verify that \(AD\) is indeed the angle bisector of angle \(A\) before accepting this relation.
            Common Errors:
                (i) Applying the theorem when the line is not an angle bisector.
                (ii) Using the ratio BD\DC = AB\AC without verifying that AD bisects angle  A
                (iii) Misidentifying the segments or vertices, leading to an incorrect ratio.
        - Tangent-Secant Theorem:  
            If a student applies the equation  
            \[
            T^2 = PA x PB,
            \]
            where \(T\) is the length of a tangent from an external point and \(PA\) and \(PB\) are segments of a secant, ensure that the point is external to the circle and that the configuration indeed forms a tangent-secant pair.
            Common Errors:
                (i) Using the equation T^2 = PA x PB, without confirming that the point is external to the circle.
                (ii) Mixing up the segments of the secant or incorrectly identifying the tangent line.
                (iii) Failing to ensure that the configuration forms a proper tangent-secant pair.
        - Law of Cosines:  
            When a student uses  
            \[
            c^2 = a^2 + b^2 - 2ab \cos C,
            \]
            check that \(C\) is the included angle between sides \(a\) and \(b\) as defined in the problem.
            Common Errors:
                (i) Applying the formula c^2 = a^2 + b^2 - 2ab \cos C, is not the included angle between sides a and b.
                (ii) Incorrectly identifying sides or angles due to mislabeling or misinterpretation of the geometric configuration.

        - Similarity Ratios:  
            If the student writes a ratio such as  
            \[
            AB \ AC = DE \ DF,
            \]
            verify that the triangles involved are similar by confirming they have corresponding angles equal or sides proportional.
            Common Errors:
                (i) Writing ratios such as AB \ AC = DE \ DF, without establishing the similarity of triangles.
                (ii) Using the ratios when the triangles do not have all corresponding angles equal or sides in proportion.
                (iii) Confusing similar triangles with congruent triangles, leading to improper application of the ratio.

        - Symmedian Ratio:  
            For example, the ratio  
            BP \ PC = AB^2 \ AC^2,
            is valid only if the point of intersection lies on side \(BC\). If the problem defines the point differently (e.g., as a second intersection with the circumcircle), this ratio is misapplied.
            Common errors include:
                (i) Wrong Intersection Point: Applying the ratio when the point does not lie on side BC (for example, if the point is defined as a second intersection with the circumcircle).
                (ii) Confusing with Other Ratios: Mistaking the symmedian ratio for ratios related to medians or angle bisectors.
                (iii) Incorrect Verification: Failing to verify the necessary geometric Conditions/Constraints (i.e., ensuring the triangle and point configuration truly warrant the use of the symmedian ratio).
                (iv) Mislabeling Points: Incorrectly identifying the positions of vertices or segments relative to the point of intersection.
                Ensure that the Conditions/Constraints for applying the symmedian ratio are strictly met; otherwise, flag it as a misapplication.

        - Modeling Optimization:
            Suppose a problem involves finding the smallest sphere that can contain every box in a certain family. The correct approach is to determine the box with the largest space diagonal and then set the sphere's radius to half that diagonal. However, a common error is to minimize the space diagonal instead of maximizing it.
            Incorrect approach:
                x^2+y^2+z^2 and aims to minimize it, mistakenly finding the smallest box.
                Uses a minimization process and verifies the condition for a specific configuration.
            Correct approach:
                Recognizes that the sphere must contain every box, so it is necessary to maximize x^2+y^2+z^2 to identify the box with the longest diagonal.
                Considers the full range of configurations and verifies that the sphere’s radius is half of the maximum space diagonal, ensuring all boxes are contained.

        - Inversion or Radical Axis Theorem:
            When a student uses inversion or the radical axis theorem, ensure that the circle or line Conditions/Constraints (e.g., center location, power of a point) are accurately determined. A common error is misidentifying the inversion circle or the radical axis line.

            Example:
                Suppose a problem involves proving that three circles are coaxial, meaning they share the same radical axis. A student decides to use an inversion transformation. The proper approach involves these steps:

                1. Choosing the Inversion Circle:
                The student selects an inversion circle with center O and radius r₀. For instance, if two circles ω₁ and ω₂ have centers O₁ and O₂ with radii r₁ and r₂ respectively, the inversion may be chosen so that:
                    |OO₁|² = r₀² + r₁²   or   |OO₂|² = r₀² + r₂²,
                which helps preserve orthogonality if required.

                2. Power of a Point:
                After inversion, the power of a point P with respect to a circle ω (with center O_ω and radius r_ω) is given by:
                    Power(P, ω) = |PO_ω|² − r_ω².
                The radical axis of two circles is the locus of points where their powers are equal:
                    |PO₁|² − r₁² = |PO₂|² − r₂².
                A common error is misidentifying either the center O₁ (or O₂) or the radii r₁ (or r₂), which leads to an incorrect equation for the radical axis.

                3. Common Pitfall:
                A frequent mistake is choosing an inversion circle arbitrarily without checking that it simplifies the configuration or preserves key properties (such as orthogonality). For example, if the student uses an arbitrary inversion circle and obtains:
                    |P O₁'|² − (r₁')² = |P O₂'|² − (r₂')²,
                without verifying that the new centers O₁', O₂' and radii r₁', r₂' satisfy the Conditions/Constraints for coaxality, the conclusion may be incorrect.


        - Coordinate Geometry or Algebraic Transformations:
            Ensure that the variables and coordinate systems match the problem's setup. A frequent mistake is assuming coordinates or values that do not respect given Conditions/Constraints (such as a specific location, symmetry, or domain restrictions).

            Example:
                Consider a problem asking for the coordinates of the vertices of a triangle inscribed in a circle, with certain side lengths or angle Conditions/Constraints provided. A common correct approach might be:

                1. Choosing a Coordinate System:
                The student sets one vertex at the origin and aligns one side along the x-axis. For example, let:
                    A = (0, 0),  B = (b, 0),
                and suppose the third vertex is C = (cₓ, c_y). If the circumcircle has equation:
                    (x − h)² + (y − k)² = R²,
                then the coordinates of A, B, and C must satisfy this equation.

                2. Algebraic Transformations:
                If the problem gives a side length, say AB = d, and an angle ∠ABC = θ, the student may use the distance formula:
                    d = √((b − 0)² + (0 − 0)²) = |b|,
                and apply the Law of Cosines in triangle ABC:
                    AC² = AB² + BC² − 2(AB)(BC) cos θ.
                The student must ensure that any assumptions about the coordinates (for example, b > 0) align with any given Conditions/Constraints, such as all coordinates being positive.

                3. Common Pitfall:
                A frequent error occurs when the student assumes coordinates that conflict with the problem's constraints. For instance, if the problem requires all coordinates to be positive, setting:
                    A = (0, 0), B = (b, 0) with b > 0,
                but then choosing C = (cₓ, c_y) where cₓ or c_y might be negative after a transformation, leads to inconsistencies. Another mistake is applying a substitution like:
                    c_y = √(R² − (cₓ − h)²),
                without checking the correct sign or domain for c_y, which may result in extraneous or missing solutions.

        - Weighted Digit Positions in Grid Problems:
            When dealing with problems where grid cells are used to form multi-digit numbers, it is essential to account for the weighted contribution of each digit (based on its place value). Consider the following general example:

            General Principle:
                - When a grid column forms a two-digit number with a top digit X (tens place) and a bottom digit Y (ones place), the number is given by:
                    \\[
                    10 \\times X + Y.
                    \\]
                - If a problem states that the sum of several such numbers equals a target \\(T\\), the equation is:
                    \\[
                    (10 \\times X_1 + Y_1) + (10 \\times X_2 + Y_2) + \\dots = T.
                    \\]
                - This can be rearranged as:
                    \\[
                    10 \\times (X_1 + X_2 + \\dots) + (Y_1 + Y_2 + \\dots) = T.
                    \\]
                - A common error is to split the equation into independent equations like \\(X_i + Y_i = \\text{{constant}}\\) for each column, which neglects the weighting of the tens digits.

            Example 1: A 2×2 Grid
                - Suppose the grid is:
                    \\[
                    \\begin{array}{|c|c|}
                    \\hline
                    a & b \\\\
                    \\hline
                    c & d \\\\
                    \\hline
                    \\end{array}
                    \\]
                - The numbers formed by the columns are \\(10a+c\\) and \\(10b+d\\).
                - If the sum of these numbers equals \\(T\\), then:
                    \\[
                    (10a+c) + (10b+d) = T \\quad \\text{{or}} \\quad 10(a+b)+(c+d)=T.
                    \\]
                - An incorrect approach would be to assume:
                    \\[
                    a+c = \\text{{constant1}} \\quad \\text{{and}} \\quad b+d = \\text{{constant2}},
                    \\]
                which ignores the weighting factor 10 for the top row digits.

            Example 2: A 2×3 Grid
                - Suppose the grid is:
                    \\[
                    \\begin{array}{|c|c|c|}
                    \\hline
                    a & b & c \\\\
                    \\hline
                    d & e & f \\\\
                    \\hline
                    \\end{array}
                    \\]
                - The numbers formed by the columns are \\(10a+d\\), \\(10b+e\\), and \\(10c+f\\).
                - If the sum of these numbers equals \\(T\\), then:
                    \\[
                    (10a+d) + (10b+e) + (10c+f) = T \\quad \\text{{or}} \\quad 10(a+b+c)+(d+e+f)=T.
                    \\]
                - Again, an error would be to split this into:
                    \\[
                    a+d=\\text{{constant1}}, \\quad b+e=\\text{{constant2}}, \\quad c+f=\\text{{constant3}},
                    \\]
                which does not account for the place value weight of the top digits.
                

    3. Equation correctness and substitute the Student's Proposed Values into the Equations by writing equqations
    - (1) check whether the equation is correct and matched the corresponding mathematic therom. Expalin step-by-step
    - (2) Identify all numerical or algebraic values the student provides.
    - (3) Substitute these values into each of the extracted equations. You need to details all sub-steps in subsitution, including the expansion or so.
        
        Example:
        If a student claims x = p/q in an equation, first determine whenther this equation is correct or not. If correct, substitute x into the equation and check if both sides balance.

    4. Compute Both Sides of Each Equation Independently
    - For every equation where substitution is possible, compute the left-hand side (LHS) and the right-hand side (RHS) independently.
    - Write out the entire expansion for LHS and RHS separately.
    - Avoid skipping steps—every fraction, root, or logarithm must be explicitly computed.
    - Ensure that computations respect the precision required (e.g., exact fractions vs. decimal approximations).

        Example:
        Given the equation:
            a(a+5) = 18,
        if the student proposes a = 4, then:
            LHS: 4(4+5) = 4 × 9 = 36.
            RHS: 18.
        Since 36 ≠ 18, the equation does not hold.

        Example: Polynomial Recurrence Verification
        - Given the functional equation:
        \[
        P(x) - 2P(x-1) + P(x-2) = x^2
        \]
        with conditions \( P(0) = 1 \) and \( P(1) = 2 \), the goal is to find \( P(2) \).

        - The student proposed the polynomial is:
        \[
        P(x) = x^2 + 1
        \]

        Now compute \( P(2) \) and verify LHS and RHS independently:
        - LHS:
            \[
            P(2) = 2^2 + 1 = 4 + 1 = 5
            \]
        - RHS (Verification Step):
            \[
            P(2) - 2P(1) + P(0) = 2^2
            \]
            \[
            5 - 4 + 1 = 4
            \]
            LHS matches RHS. The student’s solution is correct.
        Common error:
            - Forgetting to verify that \( P(x) \) satisfies the initial conditions.

        Example: Logarithmic Equation Verification
            Given the equation:
                log_2 (x / yz) + log_2 (y / xz) + log_2 (z / xy) = 1,
            if the student proposes x = 2, y = 4, z = 8, then:
                LHS: log_2 (2 / (4 × 8)) + log_2 (4 / (2 × 8)) + log_2 (8 / (2 × 4))
                    = log_2 (2/32) + log_2 (4/16) + log_2 (8/8)
                    = log_2 (2^-4) + log_2 (2^-2) + log_2 (2^0)
                    = -4 + (-2) + 0 = -6.
                RHS: 1.
            Since -6 ≠ 1, the equation does not hold.
        Common error:
            - Forgetting logarithm properties when combining terms  
                Incorrect:  
                log_a A + log_a B = log_a (A + B)  
                Correct:  
                log_a A + log_a B = log_a (A * B)  
            - Misapplying fraction rules within logs   
                Incorrect:  
                log_a (A / B) = log_a A / log_a B  
                Correct:  
                log_a (A / B) = log_a A - log_a B  
            - Arithmetic mistakes when simplifying fractions inside logarithms  
            - Ignoring that logarithm inputs must be positive  
                For example, attempting to evaluate log_2 (-3), which is undefined.  


    5. Verify Each Proposed Value Against Each Equation Separately
    - If the answer involves multiple equations or variables, check each value individually.
    - Ensure that every derived value satisfies its corresponding equation before combining them in the final result.

    6. Evaluate the Overall Consistency and Correctness of the Modeling
    - After checking every equation and condition, determine whether the student’s solution is consistent with all of the problem's constraints.
    - Explicitly assess if the equations used by the student are valid for the given configuration. For example:
        - Confirm that a ratio like BP/PC = AB²/AC² is applied only if the point is on side BC; if the problem defines the point differently (e.g., on the circumcircle), flag it.
        - Verify that any harmonic division formula used is standard for the given configuration.
    - Clearly explain any modeling errors or misinterpretations, such as the incorrect assumption that a point lies on a line when it does not.
    - Avoid False Positives: Default to incorrect. Even if arithmetic checks out, if there is any doubt about the modeling, do not mark the answer correct.

    - Reverse Calculation / Back-Substitution Verification:
        - Take the final computed values and substitute them back into the original problem statement’s conditions.
        - Ensure that the obtained solution not only satisfies extracted equations but also adheres to the original problem setup.
        - If the problem involves functional equations, recurrence relations, or polynomials, verify that previous terms also satisfy the recurrence.
        - Example: If the problem asks for a sequence term \( P(n) \) given a recurrence relation, ensure that the computed \( P(n) \) also satisfies all earlier recurrence conditions.



    7. Final Note:
    Ensure your verification addresses both:
        - Modeling correctness: Check that each equation truly reflects the problem’s constraints and that it is applied to the correct configuration. If an equation is valid only for a specific scenario (e.g., a point on a side) and the problem defines the point differently (e.g., on the circumcircle), flag this misapplication. Make sure you consider all scenarios, both explict and implicit. If you are not absolutely certain that every possibility has been considered, mark the problem as <TOO_HARD>.
        - Arithmetic correctness: Check that the computed values satisfy the equations.
        - if the student refuses to provide an answer by simply stating <TOO_HARD>, it should be judged as incorrect 
        - Only if both Modeling and Arithmetic are correct, you can put 'yes' in the 'correct' entry. Otherwise, put 'no' and explain which equation/condition/constraint fails the check in the the 'correct' entry.

    8. In the 'thinking' entry, Provide a Structured, Step-by-Step Verification Report 
    Your response must follow the structure below:

    **Format for Checking Equations:**

    ---
    Extracted Equations in Answer:
        - Equation 1: [Write the first extracted equation]
        - Equation 2: [Write the second extracted equation]
        ... (continue as needed)
    ---

    Checking Equation 1:
        - Principles: (1) Is the equation correct and fits the mathematical themrom? explain step-by-step strictly in the format of 'step1:..,step2:..'(2) If so, Describe how you substitute the student's proposed value step-by-step strictly in the format of 'step1:..,step2:..'

        - Student proposes: [Variable or value provided].
        - Substituting into the equation: [Show the substitution into the original equation].
        - Computing LHS: [Provide detailed computation. Please do it step-by-step strictly in the format of 'step1:..,step2:..' Within each step, if there is some equations that need to compute, please (1) Break the problem into smaller logical steps and outline the correct approach to solving it. (2) Apply the correct mathematical or logical method systematically. (3) Provide intermediate steps and justifications for each calculation to ensure clarity. (4) Verify the correctness of the final result by checking against the problem constraints or performing a validation step. For example, Compute the Least Common Multiple (LCM) of 12, 15, and 18, i.e., LCM (12,14,18). Then you need to (1) Prime factorizations: 12 = 2^2 x 3^1; 15 = 3^1 x 5^1; 18 = 2^1 x 3^2 (2) Highest powers: 2^2, 3^3, 5^1 (3) Compute: 2^2 x 3^2 x 5 = 180 (4) Verification: 180 is divisible by 12, 15, and 18. (5) Final answer: 180].
        - Computing RHS: [Provide detailed computation. Please do it step-by-step strictly in the format of 'step1:..,step2:..'. Within each step, if there is some equations that need to compute, please (1) Break the problem into smaller logical steps and outline the correct approach to solving it. (2) Apply the correct mathematical or logical method systematically. (3) Provide intermediate steps and justifications for each calculation to ensure clarity. (4) Verify the correctness of the final result by checking against the problem constraints or performing a validation step. For example, Compute the Least Common Multiple (LCM) of 12, 15, and 18, i.e., LCM (12,14,18). Then you need to (1) Prime factorizations: 12 = 2^2 x 3^1; 15 = 3^1 x 5^1; 18 = 2^1 x 3^2 (2) Highest powers: 2^2, 3^3, 5^1 (3) Compute: 2^2 x 3^2 x 5 = 180 (4) Verification: 180 is divisible by 12, 15, and 18. (5) Final answer: 180
        ].
        - Comparison: [State whether LHS equals RHS].
        - Conclusion: [State whether the equation holds or does not hold.]

    (Repeat for each extracted equation.)

    **Format for Checking Conditions/Constraints:**

    ---
    Extracted implicit and explicit Conditions/Constraints (It is known that there are both):
        - Condition 1 [implicit/explicit]: [Describe the first condition according to the problem]
        - Condition 2 [implicit/explicit]: [Describe the second condition according to the problem]
        ... (continue as needed)
    ---

    Checking Condition/Constraint 1:
        - Principles: (Describe how you verify the condition step-by-step strictly in the format of 'step1:..,step2:..')

        - Student proposes: [what is the student proposed corresponding to the Condition/Constraint].
        - Evaluation: [Explain how the student proposed should be satisfied based on the condition/constraint. You must use equation to explain, rather than just plain text. Please do it step-by-step strictly in the format of 'step1:..,step2:..'].
        - Evidence: [Provide evidence, such as relevant theorems or properties, that supports whether the condition is met. Must be concrete and specific and follow the checklist. Again, You must use equation to explain, rather than just plain text. Directly say matches without any details (like 'Matches the problem statement') is  considered as invalid. Please do it step-by-step strictly in the format of 'step1:..,step2:..'. Within each step, if there is some equations that need to compute, please (1) Break the problem into smaller logical steps and outline the correct approach to solving it. (2) Apply the correct mathematical or logical method systematically. (3) Provide intermediate steps and justifications for each calculation to ensure clarity. (4) Verify the correctness of the final result by checking against the problem constraints or performing a validation step. For example, Compute the Least Common Multiple (LCM) of 12, 15, and 18, i.e., LCM (12,14,18). Then you need to (1) Prime factorizations: 12 = 2^2 x 3^1; 15 = 3^1 x 5^1; 18 = 2^1 x 3^2 (2) Highest powers: 2^2, 3^3, 5^1 (3) Compute: 2^2 x 3^2 x 5 = 180 (4) Verification: 180 is divisible by 12, 15, and 18. (5) Final answer: 180.].
        - Conclusion: [State whether the Student proposes is consistent with the problem’s Condition/Constraint. Do not accept proposes as valid unless you have concrete and specific evidence that it matches the problem’s setup]

    (Repeat for each extracted condition.)

    ---
    **Format for Reverse Calculation / Back-Substitution Verification:**

    ---
    Reverse Calculation / Back-Substitution:
        - Step 1: [Take the final computed values and substitute them back into the original problem statement's conditions. You need to give what the original problem statement's conditions are, and what final computed values you are going to substitute]
        - Step 2: [Compute and verify whether the substituted values satisfy the original problem constraints. Give your computation in detils. Step by step and show all the atomic operations. If the problem involves recurrence relations, functional equations, or polynomials, ensure previous terms satisfy the recurrence or equation.]
        - Step 3: [Identify any discrepancies or inconsistencies if they exist.]
        - Conclusion: [State whether the back-substitution confirms correctness.]
    ---

    Now, review the following question and proposed answer based on the above criteria.

    \n\nQuestion:\n[QUESTION]\n\nProposed Answer:\n[ANSWER]
    """


                # - Look for missing justifications. If the student applies a theorem or ratio without verifying the necessary assumptions (such as a point lying on a specific line), note this as an implicit condition that needs to be met.
# 