import subprocess
import json
import os
import re
import re
import subprocess
from pathlib import Path
import tempfile


def run_swebench_evaluation(judge_path: str, instance_id: str, extracted_answer: str, technique: str, solution_name, code_snippet=None):
    """
    Run SWE-Bench evaluation using the harness system.
    
    Args:
        judge_path (str): Name of the dataset (e.g., "princeton-nlp/SWE-bench_Lite")
        predictions_path (str): Path to the predictions file
        num_workers (int): Number of parallel workers for evaluation
        run_id (str): Unique identifier for this evaluation run
    """
    
    #TODO: generated number can be wrong? double chexck 04/10
    computed_header = extract_hunks_and_recalculate_headers(extracted_answer)
    print(f"computed_header: {computed_header}")
    extracted_answer = replace_hunk_headers_with_computed_counts(extracted_answer, computed_header)
    extracted_answer = normalize_diff_string(extracted_answer)
    #TODO: one might also check the starting line, but I did not do it
    print(f"updated extracted_answer: {extracted_answer}")
    # exit()

    prediction = {
    "instance_id": instance_id,
    "model_patch": extracted_answer,
    "model_name_or_path": "gpt-4o",
    }

    path_to_prediction = judge_path+f'_{instance_id}_{solution_name}.json'
    print('path_to_prediction: ', path_to_prediction)

    # Create a list with the prediction
    predictions_list = [prediction]
    
    # Write as a JSON array
    # TODO: debugged still needed
    with open(path_to_prediction, 'w') as f:
        json.dump(predictions_list, f, indent=4)

    # Construct the command
    num_workers = 1# Construct the command
    run_id = f'{instance_id}_{technique}_{solution_name}'
    run_id = run_id.replace(' ', '_').replace('-', '_').replace('(', '_').replace(')', '_')
    print('run_id: ',run_id)
    
    cmd = [
        "python", "-m", "swebench.harness.run_evaluation",
        "--dataset_name", 'princeton-nlp/SWE-bench_Lite',
        "--predictions_path", path_to_prediction,
        "--max_workers", str(num_workers),
        "--run_id", str(run_id)
    ]
    
    while True: #if error, let's rerun
        try:
            # Run the command and capture output
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print("Evaluation completed successfully")
            print("Output:", result.stdout)
            break
            # return result.stdout
        except subprocess.CalledProcessError as e:
            print("Error running evaluation:")
            print("Error output:", e.stderr)
            print('Rerun') #TODO: cannot rerun, it will just exit
            raise e

# read the report 
    result_path = f'/export/xgen-finance/meta_agent/planing/results/question/meta_agent/{technique}/swe_bench/logs/run_evaluation/{run_id}/gpt-4o/{instance_id}/report.json'
    print('result_path: ',result_path)

    total_tests = 0
    passed_tests = 0
    if os.path.exists(result_path):
        score, percentage, passed_tests, total_tests = compute_success_percentage(result_path)

    else:
        print(f"Report file not found at {result_path}")
        score = 0.0
        percentage = 0.0

    return score, percentage, passed_tests, total_tests

def compute_success_percentage(json_path):
    with open(json_path, "r") as f:
        data = json.load(f)

    for instance_id, result in data.items():
        tests_status = result.get("tests_status", {})
        resolved = result.get("resolved")
        assert type(resolved) == bool

        # Collect pass/fail lists for FAIL_TO_PASS and PASS_TO_PASS
        total_tests = 0
        passed_tests = 0

        for category in ["FAIL_TO_PASS", "PASS_TO_PASS"]:
            success = tests_status.get(category, {}).get("success", [])
            failure = tests_status.get(category, {}).get("failure", [])
            total_tests += len(success) + len(failure)
            passed_tests += len(success)

        percentage = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

        print(f"{instance_id} → {passed_tests} passed test | {total_tests} total_tests | {passed_tests}/{total_tests} passed → {percentage:.1f}% | resolved: {resolved}")

        if resolved:
            return 1.0, percentage, passed_tests, total_tests
        else:
            return 0.0, percentage, passed_tests, total_tests   


def replace_hunk_headers_with_computed_counts(diff_text, hunk_infos):
    """
    Replace all hunk headers in the diff text using computed Y and B values
    from hunk_infos (as returned by extract_all_hunks_and_recalculate_headers).
    Returns the updated diff text.
    """
    lines = diff_text.strip().splitlines()
    hunk_header_re = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

    output_lines = []
    hunk_index = 0

    for line in lines:
        match = hunk_header_re.match(line)
        if match and hunk_index < len(hunk_infos):
            # Get computed values
            info = hunk_infos[hunk_index]
            hunk_index += 1

            original_start = info['original_start']
            new_start = info['new_start']
            computed_Y = info['computed_Y']
            computed_B = info['computed_B']

            new_header = f"@@ -{original_start},{computed_Y} +{new_start},{computed_B} @@"
            output_lines.append(new_header)
        else:
            output_lines.append(line)

    return "\n".join(output_lines)

def extract_hunks_and_recalculate_headers(diff_text):
    """
    Parses a unified diff string, handles multiple hunks for a single file,
    and returns a list of dictionaries for each hunk:
    {
        'original_start': X,
        'new_start': A,
        'declared_Y': Y,
        'declared_B': B,
        'computed_Y': actual_Y,
        'computed_B': actual_B,
        'lines': [...],  # The hunk body
    }
    """
    lines = diff_text.strip().splitlines()
    hunk_header_re = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

    results = []
    current_hunk_lines = []
    current_header = None

    for line in lines:
        match = hunk_header_re.match(line)
        if match:
            # Process previous hunk
            if current_header:
                computed_Y, computed_B = compute_hunk_line_counts(current_hunk_lines)
                results.append({
                    'original_start': current_header[0],
                    'new_start': current_header[1],
                    'declared_Y': current_header[2],
                    'declared_B': current_header[3],
                    'computed_Y': computed_Y,
                    'computed_B': computed_B,
                    'lines': current_hunk_lines
                })
                current_hunk_lines = []

            # Start new hunk
            original_start = int(match.group(1))
            original_len = int(match.group(2))
            new_start = int(match.group(3))
            new_len = int(match.group(4))
            current_header = (original_start, new_start, original_len, new_len)
        elif current_header:
            current_hunk_lines.append(line)

    # Final hunk
    if current_header and current_hunk_lines:
        computed_Y, computed_B = compute_hunk_line_counts(current_hunk_lines)
        results.append({
            'original_start': current_header[0],
            'new_start': current_header[1],
            'declared_Y': current_header[2],
            'declared_B': current_header[3],
            'computed_Y': computed_Y,
            'computed_B': computed_B,
            'lines': current_hunk_lines
        })

    return results

def compute_hunk_line_counts(hunk_lines):
    """
    Given a list of lines in a diff hunk body (excluding the header),
    compute the correct number of lines from the original file (Y)
    and from the new file (B), for the hunk header format:

        @@ -X,Y +A,B @@

    Returns:
        (Y, B): tuple of integers
    """
    num_context = 0
    num_removed = 0
    num_added = 0

    for line in hunk_lines:
        if line.startswith(" "):
            num_context += 1
        elif line.startswith("-"):
            num_removed += 1
        elif line.startswith("+"):
            num_added += 1
        else:
            # Ignore lines like "\ No newline at end of file"
            continue

    y = num_context + num_removed  # lines from original file
    b = num_context + num_added    # lines from new file
    return y, b



def check_diff_file(file_path):
    errors = []
    warnings = []
    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    line_number = 0
    state = "idle"
    expected_minus = expected_plus = 0
    current_minus = current_plus = 0
    file_a = file_b = None

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line_number += 1
            stripped = line.rstrip("\n")

            if stripped.startswith("--- "):
                file_a = stripped[4:].strip()
                state = "file_header"
                continue
            elif stripped.startswith("+++ "):
                file_b = stripped[4:].strip()
                if state != "file_header":
                    errors.append((line_number, "'+++' must follow '---'"))
                if file_a and file_b and file_a[2:] != file_b[2:]:
                    warnings.append((line_number, f"File mismatch: {file_a} vs {file_b}"))
                state = "hunk_or_idle"
                continue

            match = hunk_header_re.match(stripped)
            if match:
                if state == "in_hunk" and (current_minus != expected_minus or current_plus != expected_plus):
                    errors.append((line_number, f"Hunk line count mismatch: expected -{expected_minus}/+{expected_plus}, got -{current_minus}/+{current_plus}"))
                expected_minus = int(match.group(2) or 1)
                expected_plus = int(match.group(4) or 1)
                current_minus = current_plus = 0
                state = "in_hunk"
                continue

            if state == "in_hunk":
                if stripped.startswith("-"):
                    current_minus += 1
                elif stripped.startswith("+"):
                    current_plus += 1
                    if stripped.rstrip() != stripped:
                        warnings.append((line_number, "Trailing whitespace in added line"))
                    if "\t" in stripped:
                        warnings.append((line_number, "Tab character in added line"))
                elif stripped.startswith(" "):
                    continue
                elif stripped == "" or stripped.startswith("\\"):
                    continue
                else:
                    errors.append((line_number, f"Invalid line in hunk: {stripped}"))

    if state == "in_hunk" and (current_minus != expected_minus or current_plus != expected_plus):
        errors.append((line_number, f"Final hunk line count mismatch: expected -{expected_minus}/+{expected_plus}, got -{current_minus}/+{current_plus}"))

    return errors, warnings

def dry_run_patch(file_path):
    try:
        result = subprocess.run(["patch", "--dry-run", "-p1"], input=open(file_path, "rb").read(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            return result.stderr.decode("utf-8").strip()
    except FileNotFoundError:
        return "patch command not found (cannot perform dry-run)."
    return None



def print_and_raise_error(errors, warnings, dry_run_result, diff_content, temp_path):
    # print(f"Checking: {diff_content} in {temp_path}")
    print(f"Checking: {temp_path}")
   
    if errors:
        print(f"\n[ERROR] Found {len(errors)} issues:")
        for line_num, msg in errors:
            print(f"  Line {line_num}: {msg}")
            raise Exception(f"\n[ERROR] Found {len(errors)} issues:  Line {line_num}: {msg}")

    else:
        print("\n[OK] No structural errors found.")

    if warnings:
        print(f"\n[WARNING] Found {len(warnings)} warnings:")
        for line_num, msg in warnings:
            print(f"  Line {line_num}: {msg}")

    else:
        print("\n[OK] No warnings.")

    if dry_run_result:
        print(f"\n[DRY-RUN PATCH ERROR]\n{dry_run_result}")
        raise Exception(f"\n[DRY-RUN PATCH ERROR]\n{dry_run_result}")
    else:
        print("\n[OK] Patch applies cleanly (dry-run passed).")




def normalize_diff_string(diff_content: str) -> str:
    # Normalize all line endings to \n
    content = diff_content.replace("\r\n", "\n").replace("\r", "\n")
    # Ensure a trailing newline
    if not content.endswith("\n"):
        content += "\n"
        print('added a new line')
    return content


def sanity_check(diff_content):

    # diff_content = normalize_diff_string(diff_content)


    # with tempfile.NamedTemporaryFile("w+", delete=True, suffix=".diff") as temp_file:
    temp_path_open = "/export/xgen-finance/meta_agent/planing/results/question/meta_agent/cot/swe_bench/log/sympy__sympy-24909_plan/gpt-4o/sympy__sympy-24909/patch.diff"
    temp_path = "./temp.diff"


    # temp_path_open = "./temp_open.diff"
    # with open(temp_path_open, "w") as temp_file:
    #     temp_file.write(diff_content)
        # temp_path = temp_file.name
    Path(temp_path).write_text(diff_content or "")


    with open(temp_path_open) as f1, open(temp_path) as f2:
        print(f1.read() == f2.read())  # Check if identical
        
        import difflib
        diff1 = f1.read().splitlines()
        diff2 = f2.read().splitlines()
        for line in difflib.unified_diff(diff1, diff2, fromfile=temp_path_open, tofile=temp_path):
            print(line)


    errors, warnings = check_diff_file(temp_path_open)
    dry_run_result = dry_run_patch(temp_path_open)
    print_and_raise_error(errors, warnings, dry_run_result, diff_content, temp_path_open)


        
    errors, warnings = check_diff_file(temp_path)
    dry_run_result = dry_run_patch(temp_path)
    print_and_raise_error(errors, warnings, dry_run_result, diff_content, temp_path)


