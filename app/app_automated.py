import sys
import json
import tempfile
import streamlit as st
from pathlib import Path

# ------------------------------------------------------------------
# Make the evaluation package importable regardless of CWD
# The app lives in app/, but the evaluation/ package is one level up.
# ------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from model_infer import generate_prompt, infer_model
from evaluation.evaluator import run_evaluation
from evaluation.config import EvaluationConfig

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
# Helpers
# --------------------------------------------------

def get_json_files(folder_path: str):
    """Return all JSON filenames in a folder without the .json extension."""
    folder = Path(folder_path)
    if not folder.exists():
        return []
    return sorted(file.stem for file in folder.glob("*.json"))


def _status_badge(status: str) -> str:
    """Return an emoji badge for a metric status string."""
    return {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌", "MISSING": "❓"}.get(status, "❓")


def _render_evaluation(plan_response: str, robot_name: str, world_name: str, task_number: str) -> None:
    """Run the evaluation pipeline and render all metrics in Streamlit.

    Args:
        plan_response: Raw plan JSON string from the model.
        robot_name: Selected robot stem (e.g. ``aliengo``).
        world_name: Selected world stem (e.g. ``college``).
    """
    # ----------------------------------------------------------------
    # Parse response and save to a temp file for the evaluator
    # ----------------------------------------------------------------
    try:
        plan_dict = json.loads(plan_response)
    except json.JSONDecodeError:
        st.error("❌ The model response is not valid JSON — cannot evaluate.")
        return

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(plan_dict, tmp, indent=2)
        tmp_plan_path = tmp.name

    robot_path = _ROOT / "robots" / f"{robot_name}.json"
    world_path = _ROOT / "worlds" / f"{world_name}.json"
    ontology_path = _ROOT / "robot_skill_ontology.json"

    # ----------------------------------------------------------------
    # Validate prerequisites
    # ----------------------------------------------------------------
    missing = [
        str(p) for p in [robot_path, world_path, ontology_path]
        if not p.exists()
    ]
    if missing:
        st.warning(
            f"⚠️ Cannot evaluate: missing files — {', '.join(missing)}. "
            "Please select a valid robot and world."
        )
        return

    # ----------------------------------------------------------------
    # Run evaluation pipeline
    # ----------------------------------------------------------------
    with st.spinner("🔍 Running deterministic capability verification…"):
        try:
            report = run_evaluation(
                robot_path=robot_path,
                world_path=world_path,
                ontology_path=ontology_path,
                plan_path=tmp_plan_path,
                config=EvaluationConfig(report_capability_trace=True),
            )
        except Exception as exc:
            st.error(f"❌ Evaluation failed: {exc}")
            return

    # ----------------------------------------------------------------
    # Persist raw plan + evaluation to app/tmp/<world>_<robot>.json
    # ----------------------------------------------------------------
    _tmp_dir = Path(__file__).resolve().parent / "tmp"
    _tmp_dir.mkdir(exist_ok=True)
    _raw_report_path = _tmp_dir / f"{task_number}_{world_name}_{robot_name}.json"
    _output = {"plan": plan_dict, "evaluation": report}
    with open(_raw_report_path, "w", encoding="utf-8") as _f:
        json.dump(_output, _f, indent=2, ensure_ascii=False)
    st.caption(f"💾 Saved → `{_raw_report_path.relative_to(Path(__file__).resolve().parent)}`")

    # ================================================================
    # SECTION 1: Overall Score Banner
    # ================================================================
    overall = report["overall_score"]
    status = report["overall_status"]
    task_success = report["task_success"]

    banner_color = (
        "#1a7a4a" if status == "PASS" else
        "#8a6d00" if status == "WARNING" else
        "#8b1a1a"
    )
    st.markdown(
        f"""
        <div style="
            background: {banner_color};
            border-radius: 12px;
            padding: 20px 28px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <div>
                <span style="font-size:2rem; font-weight:800; color:white;">
                    {_status_badge(status)} Overall Plan Score
                </span><br/>
                <span style="color:rgba(255,255,255,0.8); font-size:0.9rem;">
                    Deterministic Capability-Aware Evaluation &nbsp;|&nbsp;
                    Task Success: {"✅ YES" if task_success else "❌ NO"}
                </span>
            </div>
            <div style="
                font-size: 3rem;
                font-weight: 900;
                color: white;
            ">{overall * 100:.1f}<span style="font-size:1.5rem">%</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ================================================================
    # SECTION 2: Metric Cards (top row)
    # ================================================================
    metrics = report.get("metrics", {})

    display_metrics = [
        ("task_success",      "🎯 Task Success"),
        ("capability",        "🤖 Capability"),
        ("constraints",       "⚙️ Constraints"),
        ("action_validity",   "✔ Actions"),
        ("object_validity",   "📦 Objects"),
        ("location_validity", "📍 Locations"),
        ("skill_mapping",     "🧩 Skills"),
        ("sequence",          "🔢 Sequence"),
        ("efficiency",        "⚡ Efficiency"),
    ]

    # Render in rows of 3
    for row_start in range(0, len(display_metrics), 3):
        row = display_metrics[row_start: row_start + 3]
        cols = st.columns(len(row))
        for col, (key, label) in zip(cols, row):
            m = metrics.get(key, {})
            score = m.get("score", 0.0)
            mstatus = m.get("status", "MISSING")
            with col:
                st.metric(
                    label=f"{_status_badge(mstatus)} {label}",
                    value=f"{score * 100:.1f}%",
                    delta=f"weight {m.get('weight', 0.0):.0%}",
                    delta_color="off",
                )

    st.divider()

    # ================================================================
    # SECTION 3: Capability Trace Table
    # ================================================================
    cap_trace = report.get("capability_trace", [])
    if cap_trace:
        st.subheader("🔬 Capability Trace — Step-by-Step Verification")
        st.caption(
            "For each plan step: the required skill, required capabilities, "
            "robot's actual capabilities, and pass/fail result."
        )

        rows = []
        for entry in cap_trace:
            caps_required = ", ".join(entry.get("required_capabilities", [])) or "—"
            caps_checked = entry.get("robot_capabilities_checked", {})
            caps_str = (
                " | ".join(
                    f"{'✅' if v else '❌'} {k}"
                    for k, v in caps_checked.items()
                )
                if caps_checked else "—"
            )
            result = entry.get("result", "?")
            failure = entry.get("failure_reason", "")
            rows.append({
                "Step": f"CP{entry['checkpoint_id']}.{entry['step']}",
                "Action": entry.get("action_name", ""),
                "Resolved Skill": entry.get("required_skill", ""),
                "Required Capabilities": caps_required,
                "Robot Capability Check": caps_str,
                "Result": f"{'✅ PASS' if result == 'PASS' else '❌ FAIL'}",
                "Failure Reason": failure or "—",
            })

        st.dataframe(rows, width=True, hide_index=True)
        st.divider()

    # ================================================================
    # SECTION 4: Errors and Warnings
    # ================================================================
    errors = report.get("errors", [])
    warnings = report.get("warnings", [])

    col_err, col_warn = st.columns(2)
    with col_err:
        st.subheader(f"❌ Errors ({len(errors)})")
        if errors:
            for e in errors:
                st.error(
                    f"**[{e.get('code', 'ERROR')}]** {e.get('message', '')}  \n"
                    f"*{e.get('suggestion', '')}*"
                )
        else:
            st.success("No errors found.")

    with col_warn:
        st.subheader(f"⚠️ Warnings ({len(warnings)})")
        if warnings:
            for w in warnings:
                st.warning(
                    f"**[{w.get('code', 'WARN')}]** {w.get('message', '')}  \n"
                    f"*{w.get('suggestion', '')}*"
                )
        else:
            st.success("No warnings.")

    st.divider()

    # ================================================================
    # SECTION 5: Per-Validator Detail Expanders
    # ================================================================
    st.subheader("🔍 Validator Details")
    validator_details = report.get("validator_details", {})
    for vname, vdata in validator_details.items():
        vstatus = vdata.get("status", "UNKNOWN")
        vscore = vdata.get("normalised_score", 0.0)
        with st.expander(
            f"{_status_badge(vstatus)} {vname}  —  {vscore * 100:.1f}%",
            expanded=False,
        ):
            st.write(vdata.get("comments", ""))
            vis = vdata.get("issues", [])
            if vis:
                for issue in vis:
                    sev = issue.get("severity", "INFO")
                    msg = f"**[{issue.get('code','')}]** {issue.get('message','')} — _{issue.get('suggestion','')}_"
                    if sev in ("CRITICAL", "ERROR"):
                        st.error(msg)
                    elif sev == "WARNING":
                        st.warning(msg)
                    else:
                        st.info(msg)
            else:
                st.success("No issues.")

    st.divider()

    # ================================================================
    # SECTION 6: Download Report
    # ================================================================
    # st.subheader("📥 Download Evaluation Report")
    # report_json = json.dumps(report, indent=2, ensure_ascii=False)
    # st.download_button(
    #     label="⬇️ Download evaluation_report.json",
    #     data=report_json,
    #     file_name="evaluation_report.json",
    #     mime="application/json",
    #     use_container_width=True,
    # )


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("AUTOMATE: 🤖 Capability-Aware Robot Task Planning Framework")

st.caption("M.Tech Dissertation Demonstration Platform")

st.divider()

# --------------------------------------------------
# INPUT SECTION (Fixed)
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    selected_model = st.selectbox(
        "Available Models",
        ["Pick a model", "Qwen/Qwen3.5-9B", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B", "google/gemma-4-e4b", "microsoft/Phi-4-reasoning-plus", "NovaSky-AI/Sky-T1-7B-Preview"],
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

task_area = st.text_area(
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

    if not task_area:
        st.warning("Please enter a natural language task.")

    else:
        # print(_ROOT)

        with open(str(_ROOT)+"/app/tasks/"+world+".task") as taskFile:
            for eachTask in taskFile.readlines():
                task_number = eachTask[:2].strip()
                task = eachTask[3:].strip() 
                st.write(task_number)
                st.write(task)

                # Generate only once
                prompt = generate_prompt(
                    model_name=selected_model,
                    robot_name=robot,
                    world_name=world,
                    workspace_name=workspace,
                    task=task,
                )

                prompt_placeholder = st.empty()

                # with prompt_placeholder.container():
                #     with st.expander("📝 Prompt", expanded=False):
                #         st.code(prompt, language="json")


                # st.spinner("Generating plan...")

                # st.write(f"{task_number} : {task}")

                response = infer_model()
                with st.expander("🤖 Generated Plan", expanded=False):

                    st.code(response, language="json")

                # --------------------------------------------------
                # Evaluation
                # --------------------------------------------------
                with st.expander("📊 Evaluation", expanded=True):
                    _render_evaluation(response, robot, world, task_number)
                    
                with st.spinner("Sleeping for 2 seconds..."):
                    from time import sleep
                    sleep(2)


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