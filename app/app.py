import streamlit as st
from pathlib import Path

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
        ["Pick a model", "Meta-Llama-3.1-8B-Instruct", "Meta-Llama-3.2-3B-Instruct", "Gemma 3 4B Instruct", "Gemma 4 E4B", "Gemma 4 12B", "Qwen 3 8B Instruct" ],
        label_visibility="collapsed"
    )
Robots = get_json_files("./outputs")
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
    height=120,
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

# st.subheader("LLM Response")

response_container = st.container(height=450)

with response_container:

    if generate and task:

        st.info("🚧 LLM integration coming soon...")

        st.code(
"""
{
    "metadata": {},
    "goal": "",
    "reasoning": "",
    "abstract_plan": [],
    "grounded_skills": [],
    "constraints": [],
    "execution_summary": {}
}
""",
            language="json",
        )

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