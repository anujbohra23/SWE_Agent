# fetch_swebench_instance.py
from datasets import load_dataset
import subprocess, os, json

# Load SWE-bench Lite (300 real bugs from popular Python repos)
dataset = load_dataset("SWE-bench/SWE-bench_Lite", split="test")

# Pick a simple single-file Flask instance
instance = next(
    i for i in dataset
    if i["repo"] == "pallets/flask"
)

print("=" * 60)
print(f"Instance ID : {instance['instance_id']}")
print(f"Repo        : {instance['repo']}")
print(f"Base commit : {instance['base_commit']}")
print(f"Failing tests: {instance['FAIL_TO_PASS']}")
print("=" * 60)
print("\nISSUE TEXT:")
print(instance["problem_statement"])
print("=" * 60)

# Clone the repo and check out the exact buggy commit
repo_dir = os.path.expanduser("~/Desktop/agent/flask_bug")
if not os.path.exists(repo_dir):
    subprocess.run(
        ["git", "clone", f"https://github.com/{instance['repo']}.git", repo_dir],
        check=True
    )

subprocess.run(["git", "checkout", instance["base_commit"]], cwd=repo_dir, check=True)

# Install dependencies
subprocess.run(["pip", "install", "-e", ".[dev]"], cwd=repo_dir)

# Print the exact command to run the agent
fail_tests = json.loads(instance["FAIL_TO_PASS"])
print("\n\nRUN THIS COMMAND:")
print(f"""
python main.py \\
  --repo {repo_dir} \\
  --issue "{instance['problem_statement'][:300].replace(chr(10), ' ')}" \\
  --test-cmd "pytest {' '.join(fail_tests)} -v"
""")