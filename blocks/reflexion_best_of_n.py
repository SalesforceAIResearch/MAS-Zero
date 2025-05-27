import inspect
from utils import extract_xml
# REFLECTION BEST OF N




# %%%%%%%%%%%%%%%%%%%% relexion (generator-evaluator) %%%%%%%%%%%%%%%%%%%%
def forward(self, taskInfo):

    
    def check_exist(instance_id, technique, N_max):
        for i in range(N_max):
            run_id = f'{instance_id}_{technique}_{i}'
            run_id = run_id.replace(' ', '_').replace('-', '_').replace('(', '_').replace(')', '_')
            result_folder = f'{os.getenv("RUN_EVALUATION_LOG_DIR")}/{run_id}/gpt-4o/{instance_id}'
            if not os.path.isdir(result_folder):
                return False
        return True

    def evaluate_swebench(response_text, instance_id, round_i, N_max):
        extracted_answer = response_text.split('\n\nAnswer:', 1)[-1].strip()
        if '<patch>' in extracted_answer:
            extracted_answer = extract_xml(extracted_answer, 'patch').strip()   
        
        judge_path = os.getenv("PREDICTION_PATH")
        technique = 'reflexion_best_of_n'
            
        run_id = f'{instance_id}_{technique}_{round_i}'
        run_id = run_id.replace(' ', '_').replace('-', '_').replace('(', '_').replace(')', '_')
        result_folder = f'{os.getenv("RUN_EVALUATION_LOG_DIR")}/{run_id}/gpt-4o/{instance_id}'
        # print('result_folder: ',result_folder)



        if check_exist(instance_id, technique, N_max): # for new generation, each time the code is different, we cannot look at the previous results
            from swe_utils import compute_success_percentage
            print(f'already run {result_folder}. Loading')
            result_path = f'{os.getenv("RUN_EVALUATION_LOG_DIR")}/{run_id}/gpt-4o/{instance_id}/report.json'
            print('result_path: ',result_path)
            total_tests = 0
            passed_tests = 0
            if os.path.exists(result_path):
                score, percentage, passed_tests, total_tests = compute_success_percentage(result_path)
            else:
                print(f"Report file not found at {result_path}")
                score = 0.0
                percentage = 0.0
        else:
            from swe_utils import run_swebench_evaluation
            score, percentage, passed_tests, total_tests = run_swebench_evaluation(judge_path, instance_id, extracted_answer, technique, round_i)

    # read reponse file
    
    response_path = f'/export/xgen-finance/meta_agent/planing/results/question/meta_agent/{self.dataset}/{self.example_id}/gpt-4o_chatgpt_gpt-4o_chatgpt_gpt-4o_chatgpt_0_plan_reponse'.replace('_final_result','') # final_result is for the last round, dataset is for all rounds

    with open(response_path, 'r') as json_file:
        response_dict = json.load(json_file)

    # Instruction for initial reasoning
    cot_initial_instruction = self.cot_instruction

    # Instruction for reflecting on previous attempts and feedback to improve
    cot_reflect_instruction = "Given previous attempts and feedback, carefully consider where you could go wrong in your latest attempt. Using insights from previous attempts, try to solve the task better."
    # May add "clearly explain how you using the previous insight"
    cot_agent = LLMAgentBase(['thinking', 'answer'], 'Chain-of-Thought Agent', model=self.node_model, temperature=0.0)

    # Instruction for providing feedback and correcting the answer
    critic_instruction = "The answer is wrong. Please review the answer above and criticize on where might be wrong."
    critic_agent = LLMAgentBase(['feedback'], 'Critic Agent', model=self.node_model, temperature=0.0)
    
    N_max = self.max_round # Maximum number of attempts
    
    # Initial attempt
    cot_inputs = [taskInfo]
    thinking, answer = cot_agent(cot_inputs, cot_initial_instruction, 0)

    for i in range(N_max):

        response_dict[i]['n'] = i


        # Get feedback and correct status from the critic
        feedback = critic_agent([taskInfo, thinking, answer], critic_instruction, i)
        
        feedback = feedback[0] # always output a list. Take the first and only one
        # Add feedback to the inputs for the next iteration
        cot_inputs.extend([thinking, answer, feedback])

        # Reflect on previous attempts and refine the answer
        thinking, answer = cot_agent(cot_inputs, cot_reflect_instruction, i + 1)

        
        response_dict[i]['response'] = f'{thinking.content}\n\nAnswer:{answer.content}' # save each steps

        if 'swe_bench' in self.dataset:
            evaluate_swebench(response_dict[i]['response'], self.instance_id, i, N_max)
            #You don't need to save anything here


    # we need to save each answer generated and judge later

    with open(response_path, 'w') as json_file:
        json.dump(response_dict, json_file, indent=4)
        print(f"Writing new reponse to {response_path}")

    final_answer = self.make_final_answer(thinking, answer)

    return final_answer


func_string = inspect.getsource(forward)


Reflexion_Best_of_N = {
    "thought": "To enhance its performance, an LLM can iteratively improve its answer based on feedback. By reflecting on its previous attempts and incorporating feedback, the model can refine its reasoning and provide a more accurate solution.",
    "name": "Self-Refine (Reflexion)",
    "code": """{func_string}""".format(func_string=func_string)
}



