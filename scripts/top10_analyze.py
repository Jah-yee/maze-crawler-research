#!/usr/bin/env python3
"""Run the core top-10 analyses: archetype clustering, classifier, decision
tree, per-team vs-baseline gap, and plots.

Reads:
  reports/top10_analysis/master_episode_matrix.csv
  reports/top10_analysis/team_aggregate.csv

Writes:
  reports/top10_analysis/archetype_assignments.csv
  reports/top10_analysis/feature_importance.csv
  reports/top10_analysis/decision_tree_rules.txt
  reports/top10_analysis/per_team_gap.csv
  reports/top10_analysis/plot_*.png
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "top10_analysis"

# ---- Load ----
ep = pd.read_csv(OUT / "master_episode_matrix.csv")
agg = pd.read_csv(OUT / "team_aggregate.csv")

# Restrict to top 1..10 + us (rank 24)
TOP10_TEAMS = [
    "bunterrrrr",
    "Андрей Савельев",
    "Takahiro Matsumoto",
    "Hazy Maze Crawler",
    "PavelLiashkov",
    "Nicolas Klodt",
    "Daniel Bekker",
    "AI TOOK MY JOB AND YOUR JOB!",
    "ZERO HQR",
    "JosephMontana",
]
ALL_TEAMS = TOP10_TEAMS + ["Jiayi Du"]

ep_focus = ep[ep["team_name"].isin(ALL_TEAMS)].copy()
agg_focus = agg[agg["team_name"].isin(ALL_TEAMS)].copy().reset_index(drop=True)
agg_top10 = agg[agg["team_name"].isin(TOP10_TEAMS)].copy().reset_index(drop=True)

# ---- 1. Archetype clustering on team-level aggregates ----
# Features chosen for STRATEGIC intent rather than ELO performance.
CLUSTER_FEATURES = [
    "build_scout_mean",        # scout-heavy vs scout-light
    "build_miner_mean",        # miner-heavy vs miner-light
    "build_worker_mean",       # worker-heavy vs worker-light
    "first_miner_mean",        # early miner vs late
    "max_factory_energy_mean", # economy ceiling
    "north_pct_mean",          # north-cadence
    "south_pct_mean",          # save-south
    "east_pct_mean",
    "west_pct_mean",
    "jump_north_pct_mean",
    "pct_episodes_no_scout",
    "transfer_north_pct_mean",
    "remove_wall_total_mean",
]

X_team = agg_top10[CLUSTER_FEATURES].fillna(0).values
scaler = StandardScaler()
X_team_scaled = scaler.fit_transform(X_team)

# Pick k via simple inertia visual
inertias = []
for k in range(1, 7):
    km = KMeans(n_clusters=k, n_init=20, random_state=0).fit(X_team_scaled)
    inertias.append(km.inertia_)

# Use k=3 as default. Validate by spread; if one cluster has ≤1 team try k=2.
chosen_k = 3
km = KMeans(n_clusters=chosen_k, n_init=50, random_state=0).fit(X_team_scaled)
labels = km.labels_
if min(np.bincount(labels)) < 1:
    chosen_k = 2
    km = KMeans(n_clusters=chosen_k, n_init=50, random_state=0).fit(X_team_scaled)
    labels = km.labels_

agg_top10 = agg_top10.copy()
agg_top10["archetype_id"] = labels

# Name archetypes by centroid characteristics
centroids = scaler.inverse_transform(km.cluster_centers_)
arch_summary = pd.DataFrame(centroids, columns=CLUSTER_FEATURES)
arch_summary["archetype_id"] = range(chosen_k)
arch_summary["n_teams"] = [int((labels == i).sum()) for i in range(chosen_k)]
arch_summary["members"] = [
    ",".join(agg_top10[agg_top10["archetype_id"] == i]["team_name"].tolist())
    for i in range(chosen_k)
]

# Heuristic naming
def name_archetype(row):
    scout = row["build_scout_mean"]
    miner = row["build_miner_mean"]
    energy = row["max_factory_energy_mean"]
    no_scout_pct = row["pct_episodes_no_scout"]
    # Three archetype heuristics
    if no_scout_pct >= 60 or scout < 1.0:
        return "Silent Miner (no scout, mine-driven)"
    if scout >= 4.0:
        return "Scout Swarm (heavy vision, lighter mines)"
    if 1.0 <= scout < 4.0 and miner >= 3.0:
        return "Hybrid (balanced miners + a few scouts)"
    return "Other"

arch_summary["name"] = arch_summary.apply(name_archetype, axis=1)

arch_summary.to_csv(OUT / "archetypes_summary.csv", index=False)

assignments = agg_top10[["team_name", "rank", "team_score", "archetype_id"]].copy()
assignments["archetype_name"] = assignments["archetype_id"].map(
    dict(zip(arch_summary["archetype_id"], arch_summary["name"]))
)
assignments.to_csv(OUT / "archetype_assignments.csv", index=False)
print("\n=== Archetype Assignments ===")
print(assignments.to_string(index=False))
print("\n=== Archetype Summary (centroids, members) ===")
print(arch_summary[["archetype_id", "name", "n_teams", "members"]].to_string(index=False))

# ---- PCA scatter plot for archetype visualization ----
all_teams_for_pca = agg_focus.copy()
X_all = all_teams_for_pca[CLUSTER_FEATURES].fillna(0).values
X_all_scaled = scaler.transform(X_all)
pca = PCA(n_components=2, random_state=0)
coords = pca.fit_transform(X_all_scaled)

fig, ax = plt.subplots(figsize=(11, 8))
colors = {0: "#1f77b4", 1: "#d62728", 2: "#2ca02c", 3: "#ff7f0e"}

# Assign each top-10 team its archetype color; us = gray
team_arch = dict(zip(agg_top10["team_name"], labels))
for i, row in all_teams_for_pca.iterrows():
    team = row["team_name"]
    rank = int(row["rank"])
    if team == "Jiayi Du":
        c = "#666666"
        marker = "X"
        size = 360
    else:
        c = colors.get(team_arch.get(team, -1), "#888")
        marker = "o"
        size = 220
    ax.scatter(coords[i, 0], coords[i, 1], c=c, marker=marker, s=size, edgecolor="black", linewidth=1.0)
    short = team[:14]
    ax.annotate(f"#{rank} {short}", (coords[i, 0], coords[i, 1]),
                fontsize=9, xytext=(8, 4), textcoords="offset points")
ax.set_title("Top 1-10 + Us: PCA of strategy aggregates (color = K-means archetype, X = us)")
ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
ax.grid(True, alpha=0.3)
# Legend
for aid in range(chosen_k):
    name = arch_summary[arch_summary["archetype_id"] == aid]["name"].iloc[0]
    ax.scatter([], [], c=colors[aid], s=140, label=f"Archetype {aid}: {name}")
ax.scatter([], [], c="#666666", marker="X", s=180, label="Us (Jiayi Du / v24)")
ax.legend(loc="best", fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "plot_pca_archetypes.png", dpi=140)
plt.close(fig)

# ---- 2. Random Forest classifier: top1-3 vs top4-10 vs us ----
def class_for(row):
    rank = int(row["rank"])
    if rank <= 3:
        return "top1-3"
    if rank <= 10:
        return "top4-10"
    return "us"

ep_focus = ep_focus.copy()
ep_focus["class"] = ep_focus.apply(class_for, axis=1)

CLF_FEATURES = [
    "first_miner",
    "first_scout",
    "build_miner",
    "build_scout",
    "build_worker",
    "factory_jump",
    "transfer_total",
    "remove_wall_total",
    "transform_total",
    "max_factory_energy",
    "max_mines",
    "steps",
    "row_100",
    "row_200",
    "energy_100",
    "energy_200",
    "energy_300",
    "idle_pct",
    "north_pct",
    "south_pct",
    "east_pct",
    "west_pct",
    "jump_north_pct",
    "jump_side_pct",
    "transfer_north_pct",
    "remove_north_pct",
    "miner_per_minute",
    "scout_per_minute",
]
# Impute missing as median per column
X = ep_focus[CLF_FEATURES].copy()
for c in CLF_FEATURES:
    X[c] = X[c].fillna(X[c].median())
y = ep_focus["class"].values

rf = RandomForestClassifier(n_estimators=300, max_depth=None, min_samples_leaf=2,
                            random_state=0, n_jobs=-1, class_weight="balanced")
rf.fit(X, y)
fi = pd.DataFrame({"feature": CLF_FEATURES, "importance": rf.feature_importances_})
fi = fi.sort_values("importance", ascending=False).reset_index(drop=True)
fi.to_csv(OUT / "feature_importance.csv", index=False)
print("\n=== Random Forest Feature Importance (top 12) ===")
print(fi.head(12).to_string(index=False))

# Plot
fig, ax = plt.subplots(figsize=(9, 8))
top12 = fi.head(15)
ax.barh(top12["feature"][::-1], top12["importance"][::-1])
ax.set_xlabel("Importance")
ax.set_title("RF feature importance: distinguishing top1-3 / top4-10 / us")
fig.tight_layout()
fig.savefig(OUT / "plot_feature_importance.png", dpi=140)
plt.close(fig)

# ---- 3. Decision tree for interpretable rules ----
dt = DecisionTreeClassifier(max_depth=4, min_samples_leaf=12, random_state=0,
                            class_weight="balanced")
dt.fit(X, y)
rules_text = export_text(dt, feature_names=CLF_FEATURES)
(OUT / "decision_tree_rules.txt").write_text(rules_text)
print("\n=== Decision Tree (depth 4) — interpretable rules ===")
print(rules_text)

# ---- 4. Per-team gap vs bunterrrrr and vs us ----
bunt = agg.loc[agg["team_name"] == "bunterrrrr"].iloc[0]
us = agg.loc[agg["team_name"] == "Jiayi Du"].iloc[0]

GAP_METRICS = [
    "build_scout_mean",
    "build_miner_mean",
    "build_worker_mean",
    "first_miner_mean",
    "max_factory_energy_mean",
    "energy_100_mean",
    "energy_200_mean",
    "energy_300_mean",
    "row_100_mean",
    "row_200_mean",
    "row_300_mean",
    "north_pct_mean",
    "south_pct_mean",
    "pct_episodes_no_scout",
    "pct_episodes_no_miner",
]
gap_rows = []
for _, row in agg_focus.iterrows():
    gap_row = {"team_name": row["team_name"], "rank": int(row["rank"]),
               "team_score": row["team_score"]}
    for m in GAP_METRICS:
        gap_row[m] = row[m]
        gap_row[f"{m}__minus_bunterrrrr"] = row[m] - bunt[m] if pd.notna(row[m]) and pd.notna(bunt[m]) else None
        gap_row[f"{m}__minus_us"] = row[m] - us[m] if pd.notna(row[m]) and pd.notna(us[m]) else None
    gap_rows.append(gap_row)
gap_df = pd.DataFrame(gap_rows).sort_values("rank")
gap_df.to_csv(OUT / "per_team_gap.csv", index=False)

# ---- 5. Plot energy trajectories ----
fig, ax = plt.subplots(figsize=(11, 7))
xs = [50, 100, 200, 300, 400]
for _, r in agg_focus.iterrows():
    ys = [r["energy_50_mean"], r["energy_100_mean"], r["energy_200_mean"],
          r["energy_300_mean"], r["energy_400_mean"]]
    if r["team_name"] == "Jiayi Du":
        ax.plot(xs, ys, "-", color="#666", lw=3.0, marker="X", markersize=10,
                label=f"#{int(r['rank'])} {r['team_name']} (us)")
    elif r["team_name"] == "bunterrrrr":
        ax.plot(xs, ys, "-", color="#d62728", lw=3.0, marker="o", markersize=8,
                label=f"#{int(r['rank'])} {r['team_name']}")
    else:
        ax.plot(xs, ys, "-", alpha=0.85, marker="o", markersize=5,
                label=f"#{int(r['rank'])} {r['team_name']}")
ax.set_title("Mean factory energy trajectory: Top 1-10 vs us")
ax.set_xlabel("Step")
ax.set_ylabel("Mean factory energy")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "plot_energy_trajectory.png", dpi=140)
plt.close(fig)

# ---- 6. Plot row trajectories ----
fig, ax = plt.subplots(figsize=(11, 7))
for _, r in agg_focus.iterrows():
    ys = [r["row_50_mean"], r["row_100_mean"], r["row_200_mean"],
          r["row_300_mean"], r["row_400_mean"]]
    if r["team_name"] == "Jiayi Du":
        ax.plot(xs, ys, "-", color="#666", lw=3.0, marker="X", markersize=10,
                label=f"#{int(r['rank'])} {r['team_name']} (us)")
    elif r["team_name"] == "bunterrrrr":
        ax.plot(xs, ys, "-", color="#d62728", lw=3.0, marker="o", markersize=8,
                label=f"#{int(r['rank'])} {r['team_name']}")
    else:
        ax.plot(xs, ys, "-", alpha=0.85, marker="o", markersize=5,
                label=f"#{int(r['rank'])} {r['team_name']}")
ax.set_title("Mean factory row trajectory: Top 1-10 vs us")
ax.set_xlabel("Step")
ax.set_ylabel("Mean factory row")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "plot_row_trajectory.png", dpi=140)
plt.close(fig)

# ---- 7. Plot scout vs miner build mix ----
fig, ax = plt.subplots(figsize=(10, 7))
for _, r in agg_focus.iterrows():
    x = r["build_scout_mean"]
    y = r["build_miner_mean"]
    if r["team_name"] == "Jiayi Du":
        ax.scatter(x, y, c="#666", marker="X", s=360, edgecolor="black", lw=1.2)
        ax.annotate(f"#{int(r['rank'])} {r['team_name']} (us)", (x, y),
                    xytext=(8, 4), textcoords="offset points", fontsize=10, weight="bold")
    elif r["team_name"] == "bunterrrrr":
        ax.scatter(x, y, c="#d62728", s=300, edgecolor="black", lw=1.2)
        ax.annotate(f"#{int(r['rank'])} {r['team_name']}", (x, y),
                    xytext=(8, 4), textcoords="offset points", fontsize=10, weight="bold")
    else:
        ax.scatter(x, y, c="#1f77b4", s=180, alpha=0.8, edgecolor="black", lw=0.6)
        ax.annotate(f"#{int(r['rank'])} {r['team_name'][:14]}", (x, y),
                    xytext=(6, 4), textcoords="offset points", fontsize=9)
ax.set_xlabel("Mean BUILD_SCOUT count per episode")
ax.set_ylabel("Mean BUILD_MINER count per episode")
ax.set_title("Build mix: scouts vs miners (Top 1-10 + us)")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "plot_scout_vs_miner.png", dpi=140)
plt.close(fig)

# ---- 8. Plot first miner step distribution per team ----
fig, ax = plt.subplots(figsize=(12, 7))
teams_in_order = [t for t in ALL_TEAMS]
data = [ep_focus[(ep_focus["team_name"] == t) & ep_focus["first_miner"].notna()]["first_miner"].values
        for t in teams_in_order]
labels_plot = [f"#{int(agg_focus[agg_focus['team_name']==t]['rank'].iloc[0])} {t[:14]}"
               for t in teams_in_order]
bp = ax.boxplot(data, tick_labels=labels_plot, showmeans=True)
ax.set_ylabel("First BUILD_MINER step (episode)")
ax.set_title("First-miner timing per team (lower = earlier miner economy)")
ax.tick_params(axis="x", rotation=30)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "plot_first_miner.png", dpi=140)
plt.close(fig)

print("\nWrote analyses + plots to", OUT)
