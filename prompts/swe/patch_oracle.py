# TODO: prompt for SWE Bench

# Copyright (c) Meta Platforms, Inc. and affiliates. All rights reserved.

AGENTLESS_REPAIR = """Please think step by step and then solve the task.

You must make sure 
(1) the patch is correct and can be applied to the code. 
(2) Please note that the patch REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
(3) Wrap each patch in a code block as shown in the example above. If you have multiple patchs, use a separate code block for each one. For example,
(5) Your patch must be significant enough to change the PASS or FAIL status of potential test cases. DO NOT include trivial patch like change the doc string, add empty lines, add comments or change the vairable names as these trivial patches cannot change a failed test cases to passed.
(6) The patch must be COMPLETE CODE and without any syntax error. Please implement complete, reliable, reusable code snippets.
(7) A user will run unix's path program directly to apply the patch, so please make sure the patch is correct and directly runnable by the unix's path program.

Examples:

This is CORRECT patch:
 "diff --git a/src/_pytest/python_api.py b/src/_pytest/python_api.py\nindex a3d0b90..b1a7c6a 100644\n--- a/src/_pytest/python_api.py\n+++ b/src/_pytest/python_api.py\n@@ -711,8 +711,15 @@ def raises(  # noqa: F811\n         except expected_exception as e:\n             # We just caught the exception - there is a traceback.\n             assert e.__traceback__ is not None\n-            return _pytest._code.ExceptionInfo.from_exc_info(\n-                (type(e), e, e.__traceback__)\n+            exc_info = (type(e), e, e.__traceback__)\n+            \n+            # Walk the traceback chain to get the full exception chain\n+            while exc_info[2].tb_next is not None:\n+                exc_info = (\n+                    type(exc_info[1]), \n+                    exc_info[1], \n+                    exc_info[2].tb_next\n+                )\n+            return _pytest._code.ExceptionInfo.from_exc_info(exc_info\n             )\n     fail(message)\n"

This is CORRECT patch:
 "--- a/django/db/models/deletion.py\n+++ b/django/db/models/deletion.py\n@@ -329,7 +329,13 @@\n             for model, instances in self.data.items():\n                 query = sql.DeleteQuery(model)\n                 pk_list = [obj.pk for obj in instances]\n-                count = query.delete_batch(pk_list, self.using)\n+                # Combine delete queries by table\n+                by_table = {}\n+                for pk in pk_list:\n+                    by_table.setdefault(model._meta.db_table, []).append(pk)\n+                for table, pks in by_table.items():\n+                    query.table = table\n+                    count = query.delete_batch(pks, self.using)\n                 deleted_counter[model._meta.label] += count\n \n                 if not model._meta.auto_created:\n"}

This is CORRECT patch:
"--- a/src/_pytest/python.py\n+++ b/src/_pytest/python.py\n@@ -271,7 +271,7 @@ class Function(PyobjMixin, Node):\n         except KeyboardInterrupt:\n             raise\n         except: # noqa\n-            return s.replace(\".[\", \"[\")\n+            return s\n \n         if name == \"__init__\":\n             cls = getattr(self.obj, \"__qualname__\", None)\n"


This is CORRECT patch:
"--- a/sympy/combinatorics/homomorphisms.py\n+++ b/sympy/combinatorics/homomorphisms.py\n@@ -333,7 +333,7 @@\n             if r[i] in gens:\n                 s = domain.generators[gens.index(r[i])]\n             else:\n-                s = r[i]\n+                s = r[i] ** -1\n             if s in images:\n                 w = w*images[s]**power\n             elif s**-1 in images:\n"


This is CORRECT patch:
"diff --git a/src/_pytest/logging.py b/src/_pytest/logging.py\nindex 4d7c65e..2b60f1d 100644\n--- a/src/_pytest/logging.py\n+++ b/src/_pytest/logging.py\n@@ -458,6 +458,7 @@ class LogCaptureFixture:\n             self.handler.setLevel(handler_orig_level)\n \n     def _finalize(self) -> None:\n+        self.handler.reset()\n         \"\"\"Finalizes the fixture.\n \n         This restores the log levels changed by :meth:`set_level`.\n"

"""



# ✅ CORRECT DIFF EXAMPLE
# correct_diff = \"\"\"\
# --- a/example.py
# +++ b/example.py
# @@ -1,3 +1,3 @@
#  def greet():
# -    print("Hello")
# +    print("Hi")
#  print("!")
# \"\"\"

# # Explanation:
# The hunk header says:
#   - Take 3 lines from the original file starting at line 1
#   - Take 3 lines for the new file starting at line 1
#
# Hunk body analysis:
#   - 1 context line: ' def greet()'      → counts for both old and new
#   - 1 removed line: '- print("Hello")'  → counts only for original
#   - 1 added line:   '+ print("Hi")'     → counts only for new
#   - 1 context line: ' print("!")'       → counts for both old and new
#
# Total:
#   - Original: 2 context + 1 removed = 3 lines → matches -1,3
#   - New:      2 context + 1 added   = 3 lines → matches +1,3
#
# ✅ This patch is correct.

# ❌ INCORRECT DIFF EXAMPLE

# incorrect_diff = \"\"\"\
# --- a/example.py
# +++ b/example.py
# @@ -1,3 +1,3 @@
#  def greet():
# -    print("Hello")
# +    print("Hi")
# +    print("How are you?")
# \"\"\"

# Explanation:
# The hunk header says:
#   - Take 3 lines from the original file starting at line 1
#   - Take 3 lines for the new file starting at line 1
#
# Hunk body analysis:
#   - 1 context line: ' def greet()'              → counts for both
#   - 1 removed line: '- print("Hello")'          → counts for original
#   - 2 added lines:   '+ print("Hi")', '+ ...'   → counts for new
#
# Total:
#   - Original: 1 context + 1 removed = 2 lines → ❌ expected 3
#   - New:      1 context + 2 added   = 3 lines → ✅ matches
#
# ❌ This patch is incorrect and will fail sanity checks with:
# "Hunk line count mismatch: expected -3/+3, got -2/+3"


# Deatils patch format requirements:

# A valid patch.diff file (unified diff format) must follow this structure:

# 1. File Headers:
#    Each file being modified must start with:
#    - '--- a/<filepath>' : The original file.
#    - '+++ b/<filepath>' : The new (target) file.

#    These must be the first two lines of the patch for a given file.
#    <filepath> must be consistent and usually relative to the project root.
#    The 'a/' and 'b/' prefixes are conventional and required for many tools.

# 2. Hunk Header:
#     "When generating a unified diff (.diff) file (final patch), each hunk must include a header in the form "
#     "'@@ -X,Y +A,B @@', where:\n"
#     "  - X is the starting line number in the original file\n"
#     "  - Y is the number of lines included from the original file\n"
#     "  - A is the starting line number in the new file\n"
#     "  - B is the number of lines included in the new file\n\n"

#     "To generate a correct hunk body that matches this header:\n"
#     "1. The hunk body must contain exactly Y lines representing the original file. These lines include:\n"
#     "   - Unchanged context lines (starting with a space ' ')\n"
#     "   - Lines to be removed (starting with '-')\n"
#     "   The total number of these lines must equal Y.\n\n"

#     "2. The hunk body must also contain exactly B lines representing the new file. These lines include:\n"
#     "   - Unchanged context lines (starting with a space ' ')\n"
#     "   - Lines to be added (starting with '+')\n"
#     "   The total number of these lines must equal B.\n\n"

#     "3. A single context line (starting with ' ') counts toward both Y and B.\n"
#     "4. Removed lines (starting with '-') count only toward Y.\n"
#     "5. Added lines (starting with '+') count only toward B.\n\n"

#     "To validate the hunk before writing it:\n"
#     "  - Count all lines starting with ' ' as context lines\n"
#     "  - Count all lines starting with '-' as removed lines\n"
#     "  - Count all lines starting with '+' as added lines\n"
#     "Then compute:\n"
#     "  actual_Y = number of context lines + number of removed lines\n"
#     "  actual_B = number of context lines + number of added lines\n"
#     "Ensure:\n"
#     "  actual_Y == Y and actual_B == B\n"
#     "If these conditions are not met, the diff is malformed and may be rejected by tools like 'patch'."


# 3. Hunk Body:
#    Each line in a hunk must begin with one of the following:
#    - ' ' (space): line is unchanged (context line).
#    - '-'         : line is removed from the original file.
#    - '+'         : line is added to the new file.

#    There must be no trailing whitespace after these symbols. Lines are treated as raw text following these characters. 

# 4. Line Endings and Characters:
#    - All lines must be Unix-style line endings (LF only, not CRLF).
#    - Tabs and spaces must be preserved exactly as in source code.
#    - Backslashes, quotes, or parentheses within code are interpreted literally, not escaped unless required by syntax of the programming language, not the diff format.
#    - Lines in the hunk body should not exceed the original line length, and multiline strings must be broken across multiple lines.

# 8. Additional Rules:
#    - All hunks for the same file must be grouped together.
#    - A patch file may contain changes to multiple files, each separated by their respective '---' and '+++' headers and hunks.


#    A patch is made of one or more "hunks", each starting with:
#    - '@@ -<start_line_orig>,<line_count_orig> +<start_line_new>,<line_count_new> @@'

#    Examples:
#    - '@@ -10,7 +10,7 @@' (changing 7 lines starting at line 10)
#    - '@@ -66,7 +66,8 @@' (7 lines in original replaced by 8 lines in new)

#     More details:
#     @@ -old_line,number_of_lines +new_line,number_of_lines @@ context

#     Breaking it down:
#     @@ - Start of hunk header
#     -old_line,number_of_lines - Original file info:
#     old_line: Starting line number in original file
#     number_of_lines: How many lines to show (including context and changes)
#     +new_line,number_of_lines - New file info:
#     new_line: Starting line number in new file
#     number_of_lines: How many lines to add
#     @@ - End of hunk header
#     context - First line of context (optional)

#     For example:
#     @@ -290,7 +290,15 @@ def _separable(transform):
#     Means:
#     Original file: Start at line 290, show 7 lines
#     New file: Start at line 290, add 15 lines
#     Context: The function definition line

#     Make sure your -old_line,number_of_lines +new_line,number_of_lines matches exactly the given code snippets wraped by '<code>' and '</code>'. You can refer the line number from the code snippets.
