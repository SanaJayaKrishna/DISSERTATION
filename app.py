import streamlit as st

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

ROBOTS = [
    "TIAGo",
    "TurtleBot3",
    "Panda",
    "UR5",
]

WORLDS = [
    "Hospital",
    "Restaurant",
    "Warehouse",
    "Kitchen",
]

WORKSPACES = [
    "Default Workspace",
    "Simulation Workspace",
]

# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("🤖 Capability-Aware Robot Task Planning Framework")

st.caption("M.Tech Dissertation Demonstration Platform")

st.divider()

# --------------------------------------------------
# INPUT SECTION (Fixed)
# --------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    robot = st.selectbox(
        "Robot",
        ROBOTS
    )

with col2:
    world = st.selectbox(
        "World",
        WORLDS
    )

with col3:
    workspace = st.selectbox(
        "Workspace",
        WORKSPACES
    )

task = st.chat_input(
    "Enter natural language instruction..."
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

st.subheader("LLM Response")

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