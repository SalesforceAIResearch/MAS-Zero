from prompts.judge.post_process import POST_PROCESS
import json 
from collections import Counter



def filter_and_sort(a, b, dataset): #aime24
    # some we know for sure incorrect can be removed
    
    a = [_.strip() if type(_)==str else _ for _ in a]

    if 'aime24' in dataset:
        filtered = [(ai, bi) for ai, bi in zip(a, b) if isinstance(ai, str) and ai.isdigit()]
    elif 'gpqa' in dataset:
        filtered = [(ai, bi) for ai, bi in zip(a, b) if isinstance(ai, str) and ai in ['A','B','C','D']]

    # Step 2: Sort by frequency of a
    counter = Counter(ai for ai, _ in filtered)
    filtered.sort(key=lambda x: -counter[x[0]])

    # Step 3: Unzip back
    a_sorted, b_sorted = zip(*filtered) if filtered else ([], [])
    a_sorted = list(a_sorted)
    b_sorted = list(b_sorted)

    return a_sorted, b_sorted


def post_process(sampler, candidate):

    FORMAT_INST = lambda request_keys: f"""Reply EXACTLY with the following JSON format.\n{str(request_keys)}\nDO NOT MISS ANY REQUEST FIELDS and ensure that your response is a well-formed JSON object!\n\n"""
    output_fields_and_description = {key: f"Your {key}." for key in ['thinking', 'post-processed']}
    system_prompt = 'You are a helpful assistant. ' + FORMAT_INST(output_fields_and_description)


    msg = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": POST_PROCESS.replace('[REASONING_PROCESS]',candidate)},
    ]        
    # print('msg: ',msg)


    json_dict = sample(sampler, msg, must_have_key=None, write_to_file=False)
    # response = response['post-processed']

    # print('json_dict: ',json_dict)

    return json_dict

def sample(sampler, msg, must_have_key=None, write_to_file=False, file_path=None):
    while True:
        try:
            response, _ = sampler(msg)
            json_dict = json.loads(response)

            if must_have_key is None:
                all_keys_present = True
            else:
                all_keys_present = all(key in json_dict for key in must_have_key)

            if all_keys_present:
                if write_to_file:
                    # print('verifier response: ')
                    with open(file_path, 'a+') as judge_file:
                        for key, item in json_dict.items():
                            judge_file.write(f'key: {key}\nitem: {item}\n')
                            # print(f'{key}: {item}')
                break
        except Exception as e:
            print(f'Error: {e}')    

    return json_dict


