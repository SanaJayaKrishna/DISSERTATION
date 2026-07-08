import json
import torch

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM
)

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
    
    # Load the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
                    model_name
                )
    
    # Load the model
    model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16,
                device_map="cpu"
            )
    
    messages = [
        {
            "role": "user",
            "content": "Tell me a technical joke."
        }
    ]

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt"
    )

    outputs = model.generate(
        inputs,
        max_new_tokens=200,
        do_sample=True,
        temperature=0.7
    )

    response = tokenizer.decode(
        outputs[0][inputs.shape[-1]:],
        skip_special_tokens=True
    )

    return response + "\n"*3 + "="*80 + prompt + "="*80