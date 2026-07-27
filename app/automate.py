"""
automate.py
===========
Automates plan generation + evaluation for every task in inferences/tasks/*.task.

For each .task file (one world per file, ~50 tasks each):
    - Uses the Qwen/Qwen3.5-9B model and the pepper robot.
    - Generates a plan via the LLM API.
    - Evaluates it with the deterministic evaluation pipeline.
    - Saves the output to app/tmp/<task_num>_<world>_pepper.json.

Usage (run from the DISSERTATION root or from the app/ directory):
    cd /home/sjk/DISSERTATION
    ./.streamlit/bin/python app/automate.py

    # Or from inside app/:
    cd /home/sjk/DISSERTATION/app
    python automate.py
"""

import json
import logging
import re
import sys
import tempfile
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent          # .../DISSERTATION/app
_ROOT = _HERE.parent                              # .../DISSERTATION

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evaluation.evaluator import run_evaluation
from evaluation.config import EvaluationConfig

TASKS_DIR  = _ROOT / "inferences" / "tasks"
ROBOTS_DIR = _ROOT / "robots"
WORLDS_DIR = _ROOT / "worlds"
ONTOLOGY   = _ROOT / "robot_skill_ontology.json"
OUTPUT_DIR = _HERE / "tmp"

# ---------------------------------------------------------------------------
# Fixed parameters
# ---------------------------------------------------------------------------

MODEL     = "Qwen/Qwen3.5-9B"
ROBOT     = "pepper"
COLAB_URL = "https://baguette-dismount-diocese.ngrok-free.dev"

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
# Prompt templates (identical to app/model_infer.py)
# ---------------------------------------------------------------------------

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
- accomplish exactly one meaningful sub-goal
- produce a stable intermediate world state
- contain logically related actions
- minimise dependencies on future checkpoints
- be independently executable and replannable

Do NOT divide checkpoints based on the number of actions.
Instead divide them according to meaningful changes in the world state.

==========================================================
GROUNDING RULES
==========================================================

Every generated action MUST satisfy ALL of the following:
- Robot capability exists.
- Object exists.
- Location exists.
- Abstract skill exists.
- ROS2 interface exists.

Never invent capabilities, ROS2 interfaces, objects, locations, rooms, skills, or world states.

==========================================================
LOGICAL CONSTRAINTS
==========================================================

Navigate before Pick. Pick before Carry. Carry before Place.
Open before Insert. Inspect before Report.
Never violate logical ordering.

==========================================================
FAILURE HANDLING
==========================================================

If the task cannot be completed:
- explain why
- set plan_valid = false
- return an empty checkpoint list
- return an empty grounded skill list
Never fabricate a solution.

==========================================================
OUTPUT REQUIREMENTS
==========================================================

Return exactly one valid JSON object.
Do NOT return Markdown, explanations, code blocks, or internal reasoning.
Do NOT add additional fields. Populate every field.
Use empty strings or empty arrays where appropriate.
The output MUST strictly follow the provided JSON schema.
"""

OUTPUT_SCHEMA = """{
  "metadata": {"robot": "", "world": "", "task": "", "model": ""},
  "goal": "",
  "checkpoints": [
    {
      "checkpoint_id": 1,
      "checkpoint_goal": "",
      "entry_state": "",
      "exit_state": "",
      "is_replannable": true,
      "actions": [{"step": 1, "action": "", "object": "", "location": ""}],
      "grounded_skills": [{"step": 1, "abstract_skill": "", "ros2_interface": "", "reason": ""}]
    }
  ],
  "constraints": [],
  "execution_summary": {"plan_valid": true, "failure_reason": "", "expected_outcome": ""}
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prompt(robot_name: str, world_name: str, task: str) -> dict:
    """Build the LLM payload dict for a given robot/world/task."""
    robot_json  = json.loads((ROBOTS_DIR / f"{robot_name}.json").read_text())
    world_json  = json.loads((WORLDS_DIR / f"{world_name}.json").read_text())
    skills_json = json.loads(ONTOLOGY.read_text())

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"<ROBOT_CAPABILITIES>\n{robot_json}\n</ROBOT_CAPABILITIES>\n\n"
        f"<WORLD_STATE>\n{world_json}\n</WORLD_STATE>\n\n"
        f"<SKILLS_LIBRARY>\n{skills_json}\n</SKILLS_LIBRARY>\n\n"
        f"<USER_TASK>\n{task}\n</USER_TASK>\n\n"
        f"<OUTPUT_SCHEMA>\n{OUTPUT_SCHEMA}\n</OUTPUT_SCHEMA>\n\n"
        "Return exactly one valid JSON object."
    )
    return {"model_name": MODEL, "prompt": prompt}


def _call_llm(payload: dict) -> str:
    """POST to the LLM API and return the raw response text."""
    response = requests.post(COLAB_URL + "/plan", json=payload, timeout=600)
    response.raise_for_status()
    return response.text


def _repair_json(raw: str) -> dict:
    """Best-effort JSON extraction and repair from a raw LLM string."""
    if isinstance(raw, dict):
        return raw
    text = raw if isinstance(raw, str) else str(raw)

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        text = brace.group(0)

    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = re.sub(r"\bTrue\b",  "true",  text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b",  "null",  text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("Could not repair JSON: %s", exc)
        return {"error": "Could not parse LLM response as JSON", "raw": raw}


def _evaluate(plan_dict: dict, robot: str, world: str) -> dict:
    """Write plan to a temp file, run evaluation, clean up."""
    robot_path = ROBOTS_DIR / f"{robot}.json"
    world_path = WORLDS_DIR / f"{world}.json"

    missing = [str(p) for p in [robot_path, world_path, ONTOLOGY] if not p.exists()]
    if missing:
        return {"error": f"Missing files: {missing}"}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(plan_dict, tmp, indent=2)
        tmp_path = Path(tmp.name)

    try:
        report = run_evaluation(
            robot_path=robot_path,
            world_path=world_path,
            ontology_path=ONTOLOGY,
            plan_path=tmp_path,
            config=EvaluationConfig(report_capability_trace=True),
        )
    except Exception as exc:
        log.warning("Evaluation error: %s", exc)
        report = {"error": str(exc)}
    finally:
        tmp_path.unlink(missing_ok=True)

    return report


def _parse_task_file(task_file: Path) -> list:
    """Parse a .task file into [(task_num_str, task_text), ...].

    Expected line format:
        01. Pick up the TV remote from the coffee table.
    """
    tasks   = []
    pattern = re.compile(r"^(\d+)\.\s+(.+)$")
    for line in task_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            task_num  = m.group(1).zfill(2)
            task_text = m.group(2).strip()
            tasks.append((task_num, task_text))
        else:
            log.warning("Skipping unrecognised line in %s: %r", task_file.name, line)
    return tasks


def _save_output(task_num: str, world: str, robot: str, plan: dict, evaluation: dict) -> Path:
    """Save {plan, evaluation} to tmp/<task_num>_<world>_<robot>.json."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{task_num}_{world}_{robot}.json"
    out_path.write_text(
        json.dumps({"plan": plan, "evaluation": evaluation}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_automation(
    robot: str = ROBOT,
    skip_existing: bool = True,
) -> None:
    """Run plan generation + evaluation for every task across all .task files.

    Args:
        robot:         Robot name (default: pepper).
        skip_existing: If True, skip tasks whose output file already exists.
    """
    task_files = sorted(TASKS_DIR.glob("*.task"))
    if not task_files:
        log.error("No .task files found in: %s", TASKS_DIR)
        return

    log.info("Found %d task file(s): %s", len(task_files), [f.name for f in task_files])
    OUTPUT_DIR.mkdir(exist_ok=True)

    total_done    = 0
    total_skipped = 0
    total_errors  = 0

    for task_file in task_files:
        world      = task_file.stem                     # e.g. "apartment"
        world_path = WORLDS_DIR / f"{world}.json"

        if not world_path.exists():
            log.warning("No world JSON for '%s' — skipping.", world)
            continue

        tasks = _parse_task_file(task_file)
        log.info("── %s  (%d tasks)", task_file.name, len(tasks))

        for task_num, task_text in tasks:
            out_path = OUTPUT_DIR / f"{task_num}_{world}_{robot}.json"

            if skip_existing and out_path.exists():
                log.info("  [SKIP] %s already exists.", out_path.name)
                total_skipped += 1
                continue

            log.info(
                "  [%s] task %s: %s",
                world.upper(), task_num, task_text[:80],
            )

            # ── 1. Inference ───────────────────────────────────────────────
            try:
                payload = _build_prompt(robot_name=robot, world_name=world, task=task_text)
                raw     = _call_llm(payload)
                plan    = _repair_json(raw)
            except Exception as exc:
                log.error("    ✗ Inference failed: %s", exc)
                plan = {"error": str(exc)}
                total_errors += 1

            # ── 2. Evaluation ──────────────────────────────────────────────
            if isinstance(plan, dict) and "error" not in plan:
                evaluation = _evaluate(plan, robot=robot, world=world)
            else:
                log.warning("    ⚠ Skipping evaluation — invalid plan.")
                evaluation = {"error": "Plan inference did not return a valid dict"}

            # ── 3. Save ────────────────────────────────────────────────────
            saved = _save_output(task_num, world, robot, plan, evaluation)
            log.info("    ✓ Saved → %s", saved.relative_to(_HERE))
            total_done += 1

    log.info("=" * 60)
    log.info(
        "Done. Generated: %d | Skipped: %d | Errors: %d",
        total_done, total_skipped, total_errors,
    )
    log.info("Output directory: %s", OUTPUT_DIR)
    log.info("=" * 60)


if __name__ == "__main__":
    run_automation()
