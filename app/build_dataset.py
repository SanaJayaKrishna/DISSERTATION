"""
build_dataset.py
----------------
Reads every JSON file in app/tmp/, extracts structured fields, and saves
the result as a pickle file (dataset.pkl) in the app/ directory.

Columns produced
----------------
Filename info:
  task      – numeric task id (e.g. 37)
  world     – world name  (e.g. "apartment")
  robot     – robot name  (e.g. "pepper")

Raw objects (stored as Python dicts – handy for deep inspection):
  plan        – the full plan dict
  evaluation  – the full evaluation dict

Flat evaluation fields:
  overall_score   – float
  task_success    – bool

Per-metric columns  (one set per metric key in evaluation["metrics"]):
  metric_<name>_score   – float
  metric_<name>_status  – str   (e.g. "PASS", "WARNING", "FAIL")
  metric_<name>_weight  – float

Usage
-----
  python app/build_dataset.py

Then in a notebook / script:
  import pandas as pd
  df = pd.read_pickle("app/dataset.pkl")
  print(df.head())
"""

import json
import os
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────
TMP_DIR = os.path.join(os.path.dirname(__file__), "tmp")
OUTPUT  = os.path.join(os.path.dirname(__file__), "dataset.pkl")
# ─────────────────────────────────────────────────────────────────────────────


def parse_filename(stem: str) -> dict:
    """
    Split  '37_apartment_pepper'  into its three components.
    Returns {task: int, world: str, robot: str}.
    """
    parts = stem.split("_", 2)   # split on first two underscores only
    if len(parts) != 3:
        raise ValueError(
            f"Unexpected filename format: '{stem}'  (expected <task>_<world>_<robot>)"
        )
    task, world, robot = parts
    return {
        "task":  int(task),
        "world": world.lower(),
        "robot": robot.lower(),
    }


def flatten_metrics(metrics: dict) -> dict:
    """
    Convert
        {"capability": {"score": 1.0, "status": "PASS", "weight": 0.25}, ...}
    into
        {"metric_capability_score": 1.0, "metric_capability_status": "PASS",
         "metric_capability_weight": 0.25, ...}
    """
    flat = {}
    for name, data in metrics.items():
        prefix = f"metric_{name}"
        flat[f"{prefix}_score"]  = data.get("score")
        flat[f"{prefix}_status"] = data.get("status")
        flat[f"{prefix}_weight"] = data.get("weight")
    return flat


def process_file(filepath: str) -> dict:
    """Parse a single JSON file and return one flat record (dict)."""
    stem = os.path.splitext(os.path.basename(filepath))[0]

    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    record = parse_filename(stem)

    # ── Raw top-level objects ────────────────────────────────────────────────
    record["plan"]       = data.get("plan")
    record["evaluation"] = data.get("evaluation")

    # ── Flat evaluation summary fields ───────────────────────────────────────
    evaluation = data.get("evaluation", {})
    record["overall_score"] = evaluation.get("overall_score")
    record["task_success"]  = evaluation.get("task_success")

    # ── Per-metric columns ───────────────────────────────────────────────────
    metrics = evaluation.get("metrics", {})
    record.update(flatten_metrics(metrics))

    return record


def main():
    json_files = sorted(
        [f for f in os.listdir(TMP_DIR) if f.endswith(".json")],
        key=lambda f: (int(f.split("_")[0]), f),   # sort by task number then name
    )

    if not json_files:
        print(f"No JSON files found in {TMP_DIR}")
        return

    records = []
    errors  = []

    for filename in json_files:
        filepath = os.path.join(TMP_DIR, filename)
        try:
            records.append(process_file(filepath))
        except Exception as exc:
            errors.append((filename, str(exc)))
            print(f"  [SKIP] {filename}: {exc}")

    df = pd.DataFrame(records)

    # ── Tidy column order: identifiers → scores → metrics → raw objects ──────
    id_cols     = ["task", "world", "robot"]
    score_cols  = ["overall_score", "task_success"]
    metric_cols = sorted([c for c in df.columns if c.startswith("metric_")])
    raw_cols    = ["plan", "evaluation"]
    df = df[id_cols + score_cols + metric_cols + raw_cols]

    df.to_pickle(OUTPUT)

    print(f"\n✓  Saved {len(df)} rows × {len(df.columns)} columns  →  {OUTPUT}")
    print(f"   Skipped {len(errors)} file(s) due to errors.\n")
    print("Columns:")
    for col in df.columns:
        dtype = str(df[col].dtype)
        print(f"  {col:<45} ({dtype})")


if __name__ == "__main__":
    main()
