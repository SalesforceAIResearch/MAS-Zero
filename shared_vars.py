global global_output_description 
global global_max_workers
global global_task_queue
global global_score_compute
global global_max_round
global global_max_sc
global global_debate_role
global global_cot_instruction
global global_node_model
global global_answers
global global_questions
global global_use_oracle_verifier
global global_judge_path
global global_reponse_path
global global_example_id
global global_n
global global_response_dict
global global_dataset
global global_instance_id
global global_code_snippet
global global_shorten_context
global global_format_choice
global global_merge_context
global global_COST_TOTAL
global global_no_decompose
global global_no_meta_reward

# Declare your globals here (optional initial values)
global_vars = [
    "global_output_description",
    "global_max_workers",
    "global_task_queue",
    "global_score_compute",
    "global_max_round",
    "global_max_sc",
    "global_debate_role",
    "global_cot_instruction",
    "global_node_model",
    "global_answers",
    "global_questions",
    "global_use_oracle_verifier",
    "global_judge_path",
    "global_reponse_path",
    "global_example_id",
    "global_n",
    "global_response_dict",
    "global_dataset",
    "global_instance_id",
    "global_code_snippet",
    "global_FORMAT_INST",
    "global_model_sampler_map",
    "global_shorten_context",
    "global_merge_context",
    "global_format_choice",
    "global_COST_TOTAL",
    "global_no_decompose",
    "global_no_meta_reward"

]

# Optionally initialize to None
for var in global_vars:
    globals()[var] = None

def set_global(name, value):
    if name in global_vars:
        globals()[name] = value
    else:
        raise NameError(f"{name} is not a recognized global variable.")

def get_global(name):
    if name in global_vars:
        return globals()[name]
    else:
        raise NameError(f"{name} is not a recognized global variable.")
        
def add_to_global_cost(value):
    set_global("global_COST_TOTAL", get_global("global_COST_TOTAL") + value)