import streamlit as st
from pathlib import Path
import json

from model_infer import generate_prompt, infer_model

# from model_manager import search_models

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Capability-Aware Robot Task Planning",
    page_icon="🤖",
    layout="wide",
)

# --------------------------------------------------
# Load CSS
# --------------------------------------------------
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --------------------------------------------------
# Sample Data
# (Later these will come from JSON files)
# --------------------------------------------------

def get_json_files(folder_path: str):
    """
    Returns all JSON filenames in a folder without the .json extension.
    """

    folder = Path(folder_path)
    # print(folder_path)

    if not folder.exists():
        # print("NONE")
        return []

    return sorted(
        file.stem
        for file in folder.glob("*.json")
    )
# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("🤖 Capability-Aware Robot Task Planning Framework")

st.caption("M.Tech Dissertation Demonstration Platform")

st.divider()

# --------------------------------------------------
# INPUT SECTION (Fixed)
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    # search = st.text_input(
    #     "Search Model",
    #     placeholder="Search Hugging Face models...", 
    # )

    # filtered_models = search_models(search)

    selected_model = st.selectbox(
        "Available Models",
        ["Pick a model", "Qwen/Qwen3.5-9B", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B", "google/gemma-4-e4b", "microsoft/Phi-4-reasoning-plus", "NovaSky-AI/Sky-T1-7B-Preview" ],
        label_visibility="collapsed"
    )

Robots = get_json_files("./robots")
Robots.insert(0, "Pick a Robot")

with col2:
    robot = st.selectbox(
        "Robot",
        Robots,
        label_visibility="collapsed"
    )


Worlds = get_json_files("./worlds")
Worlds.insert(0, "Pick an Environment ")

with col3:
    world = st.selectbox(
        "World",
        Worlds,
        label_visibility="collapsed"
    )

with col4:
    workspace = st.selectbox(
        "Workspace",
        ["DEFAULT WORKSPACE"],
        label_visibility="collapsed"

    )

task = st.text_area(
    "Natural Language Task",
    placeholder="Enter a natural language instruction...",
    label_visibility="collapsed",
    height=50
)

# Generate Button

generate = st.button(
    "Generate Plan",
    use_container_width=True
)

st.divider()

# --------------------------------------------------
# RESPONSE SECTION
# --------------------------------------------------

if generate:

    if not task:
        st.warning("Please enter a natural language task.")

    else:

        # Generate only once
        prompt = generate_prompt(
            model_name=selected_model,
            robot_name=robot,
            world_name=world,
            workspace_name=workspace,
            task=task,
        )

        # --------------------------------------------------
        # Prompt
        # --------------------------------------------------
        # with st.expander("📝 Prompt", expanded=False):
        #     st.code(prompt, language="json")


        # # --------------------------------------------------
        # # Generated Plan
        # # --------------------------------------------------
        # with st.expander("🤖 Generated Plan", expanded=False):

        #     response = infer_model()
        #     st.code(response, language="json")

        prompt_placeholder = st.empty()

        with prompt_placeholder.container():
            with st.expander("📝 Prompt", expanded=True):
                st.code(prompt, language="json")

        st.spinner("Generating plan...")
        
        response = infer_model()
        with st.expander("🤖 Generated Plan", expanded=False):

            st.code(response, language="json")





        # --------------------------------------------------
        # Evaluation
        # --------------------------------------------------
        with st.expander("📊 Evaluation", expanded=True):

            st.info("Evaluation results will appear here.")

            # Example metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Task Success", "92%")

            with col2:
                st.metric("Logical Score", "9.3 / 10")

            with col3:
                st.metric("Capability Match", "95%")

            st.divider()

            # Placeholder for future graphs
            st.write("Graphs will be displayed here.")

else:

    st.markdown(
        """
### No response generated.

Enter a natural language task and click **Generate Plan**.
"""
    )

# --------------------------------------------------
# Footer
# --------------------------------------------------

st.divider()

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.link_button("📘 Docs", "#")

with c2:
    st.link_button("🏗 Architecture", "#")

with c3:
    st.link_button("📄 Report", "#")

with c4:
    st.link_button("📊 Evaluation", "#")

with c5:
    st.link_button("📈 Analytics", "#")

with c6:
    st.link_button("📂 Logs", "#")