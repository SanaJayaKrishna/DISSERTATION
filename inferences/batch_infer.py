"""
batch_infer.py
==============
Batch inference + evaluation loop.

Iterates over:
    5 models × 4 robots × 500 tasks (11 worlds × ~45 tasks each)
    = 10,000 rows total

For each row it:
    1. Calls generate_prompt() + infer_model()  (app/model_infer.py)
    2. Writes the plan JSON to a temp file
    3. Runs run_evaluation()  (evaluation/evaluator.py)
    4. Stores plan + evaluation dicts in the output DataFrame
    5. Saves outputs_full.pkl after every row  (checkpoint safety)

Usage
-----
Run from the DISSERTATION root directory:

    cd /home/sjk/DISSERTATION
    ./.streamlit/bin/python inferences/batch_infer.py

Or import and call run_batch() from a notebook:

    import sys
    sys.path.insert(0, "/home/sjk/DISSERTATION")
    from inferences.batch_infer import run_batch
    run_batch()
"""

import json
import logging
import requests
import sys
import tempfile
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Ensure the DISSERTATION root is on the path so imports work
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent   # .../DISSERTATION
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.evaluator import run_evaluation

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODELS = [
    "Qwen/Qwen3.5-9B",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    "google/gemma-4-e4b",
    "microsoft/Phi-4-reasoning-plus",
    "NovaSky-AI/Sky-T1-7B-Preview",
]

ROBOTS = ["pepper", "g1", "h1", "nao"]

WORKSPACE_NAME = "DEFAULT WORKSPACE"   # matches the Streamlit app

# Paths (relative to ROOT)
TASKS_PKL       = ROOT / "inferences" / "tasks.pkl"       # source: TaskNum, World, Task
OUTPUT_PKL      = ROOT / "inferences" / "outputs.pkl"  # destination: all columns
ROBOTS_DIR      = ROOT / "robots"
WORLDS_DIR      = ROOT / "worlds"
ONTOLOGY_PATH   = ROOT / "robot_skill_ontology.json"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_plan_to_tempfile(plan_dict: dict) -> Path:
    """Write a plan dict to a named temp JSON file and return its Path.

    The caller is responsible for deleting the file afterwards.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )
    json.dump(plan_dict, tmp)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def _evaluate_plan(plan_dict: dict, robot: str, world: str) -> dict:
    """Evaluate a plan dict using the evaluation framework.

    Writes plan_dict to a temp file, runs run_evaluation(), then cleans up.

    Returns:
        Evaluation report dict, or an error dict if evaluation fails.
    """
    robot_path    = ROBOTS_DIR / f"{robot}.json"
    world_path    = WORLDS_DIR / f"{world}.json"
    plan_tmp_path = _write_plan_to_tempfile(plan_dict)

    try:
        report = run_evaluation(
            robot_path=robot_path,
            world_path=world_path,
            ontology_path=ONTOLOGY_PATH,
            plan_path=plan_tmp_path,
        )
    except Exception as exc:
        log.warning("Evaluation failed: %s", exc)
        report = {"error": str(exc)}
    finally:
        plan_tmp_path.unlink(missing_ok=True)   # always clean up temp file

    return report


def _load_or_build_output_df(tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Load existing outputs_full.pkl if it exists, otherwise build a fresh one.

    The full DataFrame has one row per (model, robot, task) combination.
    New rows are initialised with plan=None and evaluation=None.
    """
    if OUTPUT_PKL.exists():
        log.info("Loading existing output file: %s", OUTPUT_PKL)
        return pd.read_pickle(OUTPUT_PKL)

    log.info(
        "Building fresh output DataFrame (%d models × %d robots × %d tasks)...",
        len(MODELS), len(ROBOTS), len(tasks_df),
    )

    records = []
    for model in MODELS:
        for robot in ROBOTS:
            for _, row in tasks_df.iterrows():
                records.append({
                    "Model":      model,
                    "Robot":      robot,
                    "TaskNum":    row["TaskNum"],
                    "World":      row["World"],
                    "Task":       row["Task"],
                    "Prompt":     None,
                    "plan":       None,
                    "evaluation": None,
                })

    df = pd.DataFrame(records)
    df.to_pickle(OUTPUT_PKL)
    log.info("Output DataFrame created: %d rows → %s", len(df), OUTPUT_PKL)
    return df


PAYLOAD = None

def generate_prompt(
    model_name: str,
    robot_name: str,
    world_name: str,
    workspace_name: str,
    task: str,
):
    
    SYSTEM_PROMPT = """
You are an intelligent Capability-Aware Robot Task Planning Agent.

Your objective is to generate a complete, executable, and capability-aware task execution plan for a robot operating in a known environment.

The generated plan must be logically correct, executable using the provided Skills Library, and fully grounded in the supplied Robot Capabilities and World State.

==========================================================
INPUTS
==========================================================

You are provided with the following information.

1. ROBOT CAPABILITIES
   - Physical capabilities
   - Mobility constraints
   - Manipulation capabilities
   - Sensor capabilities
   - Available ROS2 interfaces
   - Robot limitations

2. WORLD STATE
   - Rooms
   - Objects
   - Object locations
   - Environment topology
   - Initial world configuration

3. SKILLS LIBRARY
   - Abstract skills
   - Corresponding executable ROS2 interfaces
   - Skill descriptions
   - Skill preconditions

4. USER TASK
   - Natural language instruction describing the desired goal.

==========================================================
OBJECTIVE
==========================================================

Generate a complete hierarchical task execution plan.

The plan must be divided into logical execution checkpoints.

Each checkpoint represents a stable intermediate world state that can be independently verified and independently replanned without modifying completed checkpoints.

Mission

↓

Checkpoint 1

↓

Checkpoint 2

↓

Checkpoint N

↓

Mission Complete

==========================================================
PLANNING STRATEGY
==========================================================

Before generating the final response, internally perform the following reasoning.

1. Understand the user's intent.

2. Determine the desired final world state.

3. Analyse robot capabilities.

4. Analyse the world state.

5. Verify every required object exists.

6. Verify every required location exists.

7. Verify every required capability exists.

8. Verify every abstract action has an executable ROS2 interface.

9. Construct the complete execution plan.

10. Divide the plan into meaningful checkpoints.

11. Verify every checkpoint can be independently replanned.

Do NOT reveal your internal reasoning.

Only return the final JSON.

==========================================================
CHECKPOINT DESIGN
==========================================================

Each checkpoint must:

• accomplish exactly one meaningful sub-goal

• produce a stable intermediate world state

• contain logically related actions

• minimise dependencies on future checkpoints

• be independently executable

• be independently replannable

Do NOT divide checkpoints based on the number of actions.

Instead divide them according to meaningful changes in the world state.

==========================================================
GROUNDING RULES
==========================================================

Every generated action MUST satisfy ALL of the following.

✓ Robot capability exists.

✓ Object exists.

✓ Location exists.

✓ Abstract skill exists.

✓ ROS2 interface exists.

Never invent:

• capabilities

• ROS2 interfaces

• objects

• locations

• rooms

• skills

• world states

==========================================================
LOGICAL CONSTRAINTS
==========================================================

The generated plan must respect action dependencies.

Examples:

Navigate before Pick.

Pick before Carry.

Carry before Place.

Open before Insert.

Inspect before Report.

Never violate logical ordering.

==========================================================
VALIDATION
==========================================================

Before returning the final JSON verify:

✓ Every action is executable.

✓ Every object exists.

✓ Every location exists.

✓ Every ROS2 interface exists.

✓ Every checkpoint is logically complete.

✓ The final goal is achievable.

==========================================================
FAILURE HANDLING
==========================================================

If the task cannot be completed:

• explain why

• set plan_valid = false

• return an empty checkpoint list

• return an empty grounded skill list

Never fabricate a solution.

==========================================================
OUTPUT REQUIREMENTS
==========================================================

Return exactly one valid JSON object.

Do NOT return Markdown.

Do NOT return explanations.

Do NOT return code blocks.

Do NOT reveal internal reasoning.

Do NOT add additional fields.

Populate every field.

Use empty strings or empty arrays where appropriate.

The output MUST strictly follow the provided JSON schema.
"""

    OUTPUT_SCHEMA = """
{
  "metadata": {
    "robot": "",
    "world": "",
    "task": "",
    "model": ""
  },

  "goal": "",

  "checkpoints": [

    {
      "checkpoint_id": 1,

      "checkpoint_goal": "",

      "entry_state": "",

      "exit_state": "",

      "is_replannable": true,

      "actions": [

        {
          "step": 1,
          "action": "",
          "object": "",
          "location": ""
        }

      ],

      "grounded_skills": [

        {
          "step": 1,
          "abstract_skill": "",
          "ros2_interface": "",
          "reason": ""
        }

      ]
    }

  ],

  "constraints": [

  ],

  "execution_summary": {

    "plan_valid": true,

    "failure_reason": "",

    "expected_outcome": ""
  }
}
"""

    with open(ROOT / "robots" / f"{robot_name}.json") as f:
        robot_json = json.load(f)

    with open(ROOT / "worlds" / f"{world_name}.json") as f:
        world_json = json.load(f)

    with open(ROOT / "robot_skill_ontology.json") as f:
        skills_json = json.load(f)

    prompt = f"""
{SYSTEM_PROMPT}

<ROBOT_CAPABILITIES>

{robot_json}

</ROBOT_CAPABILITIES>

<WORLD_STATE>

{world_json}

</WORLD_STATE>

<SKILLS_LIBRARY>

{skills_json}

</SKILLS_LIBRARY>

<USER_TASK>

{task}

</USER_TASK>

<OUTPUT_SCHEMA>

{OUTPUT_SCHEMA}

</OUTPUT_SCHEMA>

Return exactly one valid JSON object.
"""

    global PAYLOAD
    PAYLOAD = {
        "model_name": model_name,
        "prompt": prompt,
    }
    
    return prompt

def infer_model():
    
    global PAYLOAD

    print(f"******** CALLING LLM API")
    
    COLAB_URL = "https://baguette-dismount-diocese.ngrok-free.dev"

    response = requests.post(
        COLAB_URL + "/plan",
        json=PAYLOAD,
        timeout=600
    )

    result = response.json()    

    return result


def repair_json_response(raw) -> dict:
    """Attempt to extract and repair a valid JSON dict from a raw LLM response.

    Handles the most common failure modes:
    - Response is already a valid dict  → returned as-is
    - JSON wrapped in markdown code fences (```json ... ```)
    - Extra prose text before/after the JSON object
    - Trailing commas before } or ]
    - Python bool/None literals (True, False, None) instead of JSON
    - Single-quoted strings

    Args:
        raw: The raw API response — can be a dict, list, or string.

    Returns:
        Parsed dict, or an error dict if repair fails.
    """
    import re

    # ── Already a dict: nothing to do ─────────────────────────────────────
    if isinstance(raw, dict):
        return raw

    # ── Convert non-string types to string ────────────────────────────────
    if not isinstance(raw, str):
        text = json.dumps(raw) if isinstance(raw, (list, int, float, bool)) else str(raw)
    else:
        text = raw

    # ── Step 1: Strip markdown code fences ────────────────────────────────
    # Handles ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # ── Step 2: Extract the first {...} JSON object from the text ──────────
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        text = brace_match.group(0)

    # ── Step 3: Fix trailing commas before } or ] ──────────────────────────
    # e.g.  {"key": "value",}  →  {"key": "value"}
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # ── Step 4: Replace Python literals with JSON equivalents ─────────────
    text = re.sub(r"\bTrue\b",  "true",  text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b",  "null",  text)

    # ── Step 5: Try to parse ───────────────────────────────────────────────
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("repair_json_response: could not repair JSON — %s", exc)
        return {"error": "Could not parse LLM response as JSON", "raw": raw}




# ---------------------------------------------------------------------------
# Main batch loop
# ---------------------------------------------------------------------------

def run_batch():
    """Run the full model × robot × task inference + evaluation loop."""

    # 1. Load task list
    log.info("Loading task list from: %s", TASKS_PKL)
    tasks_df = pd.read_pickle(str(TASKS_PKL))
    log.info("Tasks loaded: %d rows", len(tasks_df))

    # 2. Load or build the output DataFrame
    df = _load_or_build_output_df(tasks_df)

    # 3. Identify pending rows (plan is None → not yet processed)
    pending_mask = df["plan"].isna()
    total   = len(df)
    pending = pending_mask.sum()
    done    = total - pending
    log.info(
        "Total rows: %d  |  Already done: %d  |  Pending: %d",
        total, done, pending,
    )

    pending_indices = df[pending_mask].index.tolist()

    # 4. Iterate over pending rows
    for count, idx in enumerate(pending_indices, start=1):
        row   = df.loc[idx]
        model = row["Model"]
        robot = row["Robot"]
        world = row["World"]
        task  = row["Task"]
        tnum  = row["TaskNum"]

        log.info(
            "[%d/%d]  model=%-45s  robot=%-8s  world=%-12s  task=%d",
            count, pending, model, robot, world, tnum,
        )

        # ── Inference ──────────────────────────────────────────────────────
        plan_result = None
        try:
            prompt_text = generate_prompt(
                model_name=model,
                robot_name=robot,
                world_name=world,
                workspace_name=WORKSPACE_NAME,
                task=task,
            )
            df.at[idx, "Prompt"] = prompt_text
            raw_result  = infer_model()
            plan_result = repair_json_response(raw_result)
        except Exception as exc:
            log.error("Inference failed for idx=%d: %s", idx, exc)
            df.at[idx, "plan"]       = {"error": str(exc)}
            df.at[idx, "evaluation"] = None
            df.to_pickle(OUTPUT_PKL)
            continue

        # ── Evaluation ─────────────────────────────────────────────────────
        eval_result = None
        if isinstance(plan_result, dict) and "error" not in plan_result:
            eval_result = _evaluate_plan(plan_result, robot=robot, world=world)
        else:
            log.warning("Skipping evaluation — invalid plan at idx=%d", idx)
            eval_result = {"error": "Plan inference did not return a valid dict"}

        # ── Store results ──────────────────────────────────────────────────
        df.at[idx, "plan"]       = plan_result
        df.at[idx, "evaluation"] = eval_result

        # ── Checkpoint save after every row ────────────────────────────────
        df.to_pickle(OUTPUT_PKL)
        log.info("  ✓ Saved checkpoint  [%d/%d]", count, pending)

    log.info("=" * 60)
    log.info("Batch complete. Output saved to: %s", OUTPUT_PKL)
    log.info("=" * 60)
    return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = run_batch()
    print(df[["Model", "Robot", "World", "TaskNum", "plan", "evaluation"]].head(10))
