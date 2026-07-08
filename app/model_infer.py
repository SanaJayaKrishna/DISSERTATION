import requests
import json

def generate_plan(
    model_name: str,
    robot_name: str,
    world_name: str,
    workspace_name: str,
    task: str,
):
    SYSTEM_PROMPT = """
You are an intelligent Robot Task Planning Agent.

Your responsibility is to generate a capability-aware task execution plan for a robot.

You are provided with:

1. Robot Capabilities
   - The robot's physical capabilities, constraints and available ROS2 interfaces.

2. Environment Definition
   - The complete world state including rooms, objects and their locations.

3. Skills Library
   - The mapping between abstract skills and executable ROS2 functions.

4. Natural Language Task
   - A task requested by the user.

Your objective is to:

- Understand the user's intent.
- Analyse the robot capabilities.
- Analyse the environment.
- Select only executable skills.
- Produce a logical sequence of high-level actions.
- Never assume capabilities that are not defined.
- Never hallucinate objects or locations.
- Never invent ROS2 actions.
- Respect all robot and environment constraints.

Return ONLY a valid JSON object.

Do not return Markdown.

Do not wrap the JSON inside code blocks.

Do not include explanations outside the JSON.
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

    "reasoning": {
        "task_understanding": "",
        "capability_analysis": "",
        "environment_analysis": "",
        "planning_decision": ""
    },

    "abstract_plan": [
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
    ],

    "constraints": [
        ""
    ],

    "execution_summary": {
        "estimated_steps": 0,
        "expected_outcome": "",
        "plan_valid": true
    }
}
"""

    with open(f"./outputs/{robot_name}.json") as f:
        robot_json = json.load(f)

    with open(f"./worlds/{world_name}.json") as f:
        world_json = json.load(f)
    
    with open(f"./robot_skill_ontology.json") as f:
        skills_json = json.load(f)


    prompt = f"""
{SYSTEM_PROMPT}

======================================================================
ROBOT CAPABILITIES
======================================================================

{robot_json}

======================================================================
ENVIRONMENT
======================================================================

{world_json}

======================================================================
SKILLS LIBRARY
======================================================================

{skills_json}

======================================================================
NATURAL LANGUAGE TASK
======================================================================

{task}

======================================================================
OUTPUT FORMAT
======================================================================

Return the response using EXACTLY the following JSON schema.

{OUTPUT_SCHEMA}

Generate ONLY valid JSON.
"""
    

    payload = {
        "model_name": model_name,
        "prompt": prompt,
        "max_new_tokens": 3072,
        "temperature": 0.3
    }

    COLAB_URL = "https://baguette-dismount-diocese.ngrok-free.dev"

    print(f"******** CALLING LLM API: {payload}")
    
    response = requests.post(
        COLAB_URL + "/plan",
        json=payload,
        # timeout=600
    )

    result = response.json()

    return result["response"]