"""
visualize_results.py
--------------------
Experimental Results & Analysis – all graphs for dissertation.

Usage:
    python app/visualize_results.py

Outputs:
    Saves every figure as a high-resolution PNG in  app/figures/
    and also shows them interactively (close each window to advance).

Dataset columns used
--------------------
  task, world, robot
  overall_score, task_success
  metric_<name>_score   (9 metrics)
  metric_<name>_status  (PASS / WARNING / FAIL)
"""

import os
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE     = os.path.dirname(os.path.abspath(__file__))
PKL_PATH = os.path.join(HERE, "dataset.pkl")
FIG_DIR  = os.path.join(HERE, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── Load ──────────────────────────────────────────────────────────────────────
df = pd.read_pickle(PKL_PATH)
print(f"Loaded dataset: {df.shape[0]} rows x {df.shape[1]} columns")

# ── Shared style ──────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.15)
plt.rcParams.update({
    "figure.dpi":       150,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
    "font.family":      "DejaVu Sans",
    "axes.spines.top":  False,
    "axes.spines.right":False,
})

# Consistent colour maps
ROBOT_PALETTE  = {"h2": "#4C72B0", "nao": "#DD8452", "pepper": "#55A868"}
WORLD_PALETTE  = {"apartment": "#C44E52", "hospital": "#8172B2", "kitchen": "#937860"}
STATUS_PALETTE = {"PASS": "#2ecc71", "WARNING": "#f39c12", "FAIL": "#e74c3c"}

METRIC_NAMES = [c.replace("metric_", "").replace("_score", "")
                for c in df.columns if c.endswith("_score") and c != "overall_score"]
METRIC_SCORE_COLS  = [f"metric_{m}_score"  for m in METRIC_NAMES]
METRIC_STATUS_COLS = [f"metric_{m}_status" for m in METRIC_NAMES]
METRIC_LABELS      = [m.replace("_", " ").title() for m in METRIC_NAMES]

def save(fig, name):
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path)
    print(f"  Saved -> {path}")

# ============================================================================
# Fig 1 – Overall Score Distribution (histogram + KDE)
# ============================================================================
fig, ax = plt.subplots(figsize=(8, 4.5))
scores = df["overall_score"].dropna().values
ax.hist(scores, bins=20, color="#4C72B0", edgecolor="white",
        alpha=0.75, density=True, label="Histogram")
# Manual Gaussian KDE (no scipy needed)
bw = 1.06 * scores.std() * len(scores)**(-0.2)
x_grid = np.linspace(scores.min() - 0.05, scores.max() + 0.05, 300)
kde_vals = np.mean(
    np.exp(-0.5 * ((x_grid[:, None] - scores[None, :]) / bw) ** 2), axis=1
) / (bw * np.sqrt(2 * np.pi))
ax.plot(x_grid, kde_vals, color="#C44E52", linewidth=2.5, label="KDE")
ax.axvline(scores.mean(), color="#e67e22", linestyle="--",
           linewidth=1.8, label=f"Mean = {scores.mean():.3f}")
ax.set_xlabel("Overall Score")
ax.set_ylabel("Density")
ax.set_title("Fig 1 - Distribution of Overall Evaluation Scores")
ax.legend()
save(fig, "fig01_overall_score_distribution.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 2 – Task-Success Rate (donut chart)
# ============================================================================
counts   = df["task_success"].value_counts()
labels   = ["Failure", "Success"]
values   = [counts.get(False, 0), counts.get(True, 0)]
colors   = ["#e74c3c", "#2ecc71"]
explode  = [0.03, 0.03]

fig, ax = plt.subplots(figsize=(6, 6))
wedges, texts, autotexts = ax.pie(
    values, labels=labels, autopct="%1.1f%%", colors=colors,
    explode=explode, startangle=90, pctdistance=0.78,
    wedgeprops=dict(width=0.55, edgecolor="white", linewidth=2))
for at in autotexts:
    at.set_fontsize(13); at.set_fontweight("bold")
ax.set_title("Fig 2 – Task-Success Rate (n=269)", pad=18)
save(fig, "fig02_task_success_rate.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 3 – Overall Score by Robot (box + strip)
# ============================================================================
fig, ax = plt.subplots(figsize=(8, 5))
order = sorted(df["robot"].unique())
sns.boxplot(data=df, x="robot", y="overall_score", order=order,
            hue="robot", palette=ROBOT_PALETTE, width=0.45, linewidth=1.5,
            legend=False, ax=ax)
sns.stripplot(data=df, x="robot", y="overall_score", order=order,
              hue="robot", palette=ROBOT_PALETTE, size=3.5, alpha=0.4,
              jitter=True, legend=False, ax=ax)
ax.set_xlabel("Robot"); ax.set_ylabel("Overall Score")
ax.set_title("Fig 3 - Overall Score Distribution by Robot")
save(fig, "fig03_score_by_robot.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 4 – Overall Score by World / Environment (violin)
# ============================================================================
fig, ax = plt.subplots(figsize=(8, 5))
order = sorted(df["world"].unique())
sns.violinplot(data=df, x="world", y="overall_score", order=order,
               hue="world", palette=WORLD_PALETTE, inner="quartile",
               linewidth=1.5, legend=False, ax=ax)
ax.set_xlabel("Environment (World)"); ax.set_ylabel("Overall Score")
ax.set_title("Fig 4 - Overall Score by Environment")
save(fig, "fig04_score_by_world.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 5 – Mean Score per Robot x World (grouped bar)
# ============================================================================
pivot = df.groupby(["world", "robot"])["overall_score"].mean().unstack()
fig, ax = plt.subplots(figsize=(9, 5))
pivot.plot(kind="bar", ax=ax, colormap="tab10", edgecolor="white",
           linewidth=0.8, width=0.7)
ax.set_xlabel("Environment"); ax.set_ylabel("Mean Overall Score")
ax.set_title("Fig 5 – Mean Overall Score: Robot x Environment")
ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
ax.legend(title="Robot", bbox_to_anchor=(1, 1))
ax.set_ylim(0, 1.05)
save(fig, "fig05_mean_score_robot_world.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 6 – Mean Metric Scores (horizontal bar)
# ============================================================================
metric_means = df[METRIC_SCORE_COLS].mean().rename(
    dict(zip(METRIC_SCORE_COLS, METRIC_LABELS)))
metric_means_sorted = metric_means.sort_values()

fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.barh(metric_means_sorted.index, metric_means_sorted.values,
               color=sns.color_palette("coolwarm_r", len(metric_means_sorted)),
               edgecolor="white")
for bar, val in zip(bars, metric_means_sorted.values):
    ax.text(val + 0.005, bar.get_y() + bar.get_height()/2,
            f"{val:.3f}", va="center", fontsize=10)
ax.set_xlim(0, 1.08)
ax.axvline(1.0, color="grey", linestyle="--", linewidth=1)
ax.set_xlabel("Mean Score"); ax.set_title("Fig 6 – Mean Score per Evaluation Metric")
save(fig, "fig06_mean_metric_scores.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 7 – Metric Status Breakdown (stacked bar – PASS / WARNING / FAIL)
# ============================================================================
status_counts = {}
for col, label in zip(METRIC_STATUS_COLS, METRIC_LABELS):
    vc = df[col].value_counts(normalize=True) * 100
    status_counts[label] = {s: vc.get(s, 0) for s in ["PASS", "WARNING", "FAIL"]}

sc_df = pd.DataFrame(status_counts).T.sort_values("FAIL", ascending=False)

fig, ax = plt.subplots(figsize=(10, 5.5))
bottom = np.zeros(len(sc_df))
for status in ["PASS", "WARNING", "FAIL"]:
    vals = sc_df[status].values
    bars = ax.bar(sc_df.index, vals, bottom=bottom,
                  color=STATUS_PALETTE[status], label=status,
                  edgecolor="white", linewidth=0.8)
    for bar, v in zip(bars, vals):
        if v > 4:
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_y() + bar.get_height()/2,
                    f"{v:.0f}%", ha="center", va="center",
                    fontsize=8.5, color="white", fontweight="bold")
    bottom += vals

ax.set_ylabel("Percentage of Evaluations (%)"); ax.set_ylim(0, 105)
ax.set_title("Fig 7 – Metric Status Distribution (PASS / WARNING / FAIL)")
ax.set_xticklabels(sc_df.index, rotation=30, ha="right")
ax.legend(loc="upper right")
save(fig, "fig07_metric_status_stacked.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 8 – Per-Metric Score by Robot (grouped box)
# ============================================================================
df_melt = df.melt(id_vars=["robot"],
                  value_vars=METRIC_SCORE_COLS,
                  var_name="metric", value_name="score")
df_melt["metric"] = (df_melt["metric"]
                     .str.replace("metric_", "")
                     .str.replace("_score", "")
                     .str.replace("_", " ")
                     .str.title())

fig, ax = plt.subplots(figsize=(14, 5.5))
sns.boxplot(data=df_melt, x="metric", y="score", hue="robot",
            palette=ROBOT_PALETTE, width=0.6, linewidth=1.2, ax=ax)
ax.set_xlabel("Metric"); ax.set_ylabel("Score")
ax.set_title("Fig 8 - Per-Metric Score by Robot")
ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
ax.legend(title="Robot", bbox_to_anchor=(1, 1))
save(fig, "fig08_metric_score_by_robot.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 9 – Correlation Heatmap of Metric Scores
# ============================================================================
corr_df = df[METRIC_SCORE_COLS + ["overall_score"]].copy()
corr_df.columns = METRIC_LABELS + ["Overall"]
corr = corr_df.corr()

fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlGn",
            vmin=-1, vmax=1, linewidths=0.5, linecolor="white",
            annot_kws={"size": 8}, ax=ax)
ax.set_title("Fig 9 – Correlation Heatmap of Evaluation Metrics")
ax.tick_params(axis="x", rotation=30)
ax.tick_params(axis="y", rotation=0)
save(fig, "fig09_metric_correlation_heatmap.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 10 – Mean Overall Score per Task (line chart, coloured by world)
# ============================================================================
task_world = (df.groupby(["task", "world"])["overall_score"]
              .mean().reset_index())

fig, ax = plt.subplots(figsize=(13, 5))
for world, grp in task_world.groupby("world"):
    grp_sorted = grp.sort_values("task")
    ax.plot(grp_sorted["task"], grp_sorted["overall_score"],
            marker="o", markersize=5, linewidth=1.8,
            color=WORLD_PALETTE[world], label=world.title())
ax.set_xlabel("Task ID"); ax.set_ylabel("Mean Overall Score")
ax.set_title("Fig 10 – Mean Overall Score per Task (by Environment)")
ax.set_xticks(sorted(df["task"].unique()))
ax.tick_params(axis="x", labelsize=7, rotation=45)
ax.legend(title="Environment")
save(fig, "fig10_score_per_task.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 11 – Task-Success Rate by Robot (bar chart)
# ============================================================================
success_robot = (df.groupby("robot")["task_success"]
                 .value_counts(normalize=True)
                 .mul(100).rename("pct").reset_index())

fig, ax = plt.subplots(figsize=(8, 5))
sns.barplot(data=success_robot[success_robot["task_success"] == True],
            x="robot", y="pct", palette=ROBOT_PALETTE,
            order=sorted(df["robot"].unique()), ax=ax)
for p in ax.patches:
    ax.annotate(f"{p.get_height():.1f}%",
                (p.get_x() + p.get_width()/2., p.get_height()),
                ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.set_xlabel("Robot"); ax.set_ylabel("Task Success Rate (%)")
ax.set_ylim(0, 65)
ax.set_title("Fig 11 – Task-Success Rate by Robot")
save(fig, "fig11_task_success_by_robot.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 12 – Radar / Spider Chart: Mean Metric Scores by Robot
# ============================================================================
robots      = sorted(df["robot"].unique())
num_metrics = len(METRIC_NAMES)
angles      = np.linspace(0, 2 * np.pi, num_metrics, endpoint=False).tolist()
angles     += angles[:1]   # close the polygon

fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
for robot in robots:
    vals = df[df["robot"] == robot][METRIC_SCORE_COLS].mean().tolist()
    vals += vals[:1]
    ax.plot(angles, vals, linewidth=2, label=robot.title(),
            color=ROBOT_PALETTE[robot])
    ax.fill(angles, vals, alpha=0.12, color=ROBOT_PALETTE[robot])

ax.set_xticks(angles[:-1])
ax.set_xticklabels(METRIC_LABELS, size=9)
ax.set_ylim(0, 1.05)
ax.set_yticks([0.25, 0.5, 0.75, 1.0])
ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], size=8)
ax.set_title("Fig 12 – Radar Chart: Mean Metric Scores by Robot",
             pad=20, fontsize=13)
ax.legend(loc="lower right", bbox_to_anchor=(1.35, -0.05))
save(fig, "fig12_radar_metric_robot.png")
plt.show(); plt.close(fig)

# ============================================================================
# Fig 13 – Score Heatmap: Task x Robot
# ============================================================================
heat = df.pivot_table(index="task", columns="robot",
                      values="overall_score", aggfunc="mean")
fig, ax = plt.subplots(figsize=(8, 12))
sns.heatmap(heat, annot=True, fmt=".2f", cmap="YlGn",
            linewidths=0.4, linecolor="white",
            vmin=0, vmax=1, annot_kws={"size": 8}, ax=ax)
ax.set_title("Fig 13 – Overall Score Heatmap: Task x Robot")
ax.set_xlabel("Robot"); ax.set_ylabel("Task ID")
save(fig, "fig13_heatmap_task_robot.png")
plt.show(); plt.close(fig)

# ============================================================================
print(f"\nAll figures saved in: {FIG_DIR}")
