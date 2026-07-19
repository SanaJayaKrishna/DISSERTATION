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

    with open(f"./robots/{robot_name}.json") as f:
        robot_json = json.load(f)

    with open(f"./worlds/{world_name}.json") as f:
        world_json = json.load(f)
    
    with open(f"./robot_skill_ontology.json") as f:
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

    payload = {
        "model_name": model_name,
        "prompt": prompt,
        "max_new_tokens": 3072,
        "temperature": 0.3
    }

    print(f"******** CALLING LLM API: {payload}")




    # COLAB_URL = "https://baguette-dismount-diocese.ngrok-free.dev"

    
    # response = requests.post(
    #     COLAB_URL + "/plan",
    #     json=payload,
    #     timeout=600
    # )

    # result = response.json()

    # print("========== RESPONSE: \n" + str(result))

    # return result["response"]

    # response = requests.post(
    #     COLAB_URL + "/plan",
    #     json=payload,
    #     timeout=600
    # )

    # print("Status Code:", response.status_code)
    # print("Content-Type:", response.headers.get("Content-Type"))
    # print("Response Text:")
    # print(response.text)

    # response.raise_for_status()   # Raises an exception for HTTP errors (4xx/5xx)

    # try:
    #     result = response.json()
    # except ValueError:
    #     raise RuntimeError(
    #         f"Server did not return valid JSON.\n\n"
    #         f"Status Code: {response.status_code}\n"
    #         f"Response:\n{response.text}"
    #     )
    

    # print("========== RESULT: \n" + str(result))

    # return result["response"]
    
    return prompt