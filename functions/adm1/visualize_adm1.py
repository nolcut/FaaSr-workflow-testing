import csv
import math
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


OBSERVABLES = ["S_ac", "S_ch4", "S_gas_ch4", "pH"]
TRAJECTORY_PANELS = ["S_ac", "S_gas_ch4"]


def _linspace(n, start, stop):
    if n == 1:
        return [float(start)]
    return [start + (stop - start) * i / (n - 1) for i in range(n)]


def _logspace(n, start, stop, base=10.0):
    return [base ** e for e in _linspace(n, start, stop)]


def _gaussian_jitter(n, center, scale, seed=0):
    return [random.Random(seed + i).gauss(center, scale) for i in range(n)]


def _read_run(path):
    cols = {c: [] for c in OBSERVABLES}
    with open(path) as f:
        for row in csv.DictReader(f):
            for c in OBSERVABLES:
                cols[c].append(float(row[c]))
    return cols


def _read_synthetic(path):
    idxs, times, cols = [], [], {c: [] for c in OBSERVABLES}
    with open(path) as f:
        for row in csv.DictReader(f):
            idxs.append(int(row["idx"]))
            times.append(float(row["time"]))
            for c in OBSERVABLES:
                cols[c].append(float(row[c]))
    return idxs, times, cols


def visualize_adm1(n_runs: int = 15):
    invocation_id = faasr_invocation_id()
    base = f"adm1-demo/{invocation_id}"

    faasr_get_file(
        local_file="synthetic_measurements.csv",
        remote_file="synthetic_measurements.csv",
        local_folder="/tmp",
        remote_folder=base,
    )
    syn_idx, syn_t, syn = _read_synthetic("/tmp/synthetic_measurements.csv")

    syn_std = {}
    for c in OBSERVABLES:
        m = sum(syn[c]) / len(syn[c])
        var = sum((v - m) ** 2 for v in syn[c]) / len(syn[c])
        syn_std[c] = math.sqrt(var) or 1.0

    runs = []
    for rank in range(1, n_runs + 1):
        local = f"/tmp/run_{rank}.csv"
        faasr_get_file(
            local_file=f"run_{rank}.csv",
            remote_file=f"run_{rank}.csv",
            local_folder="/tmp",
            remote_folder=f"{base}/runs",
        )
        run = _read_run(local)
        n_run = len(run[OBSERVABLES[0]])

        score = 0.0
        per_col = {}
        for c in OBSERVABLES:
            sse = 0.0
            preds = []
            for k, idx in enumerate(syn_idx):
                pred = run[c][min(idx, n_run - 1)]
                preds.append(pred)
                sse += (pred - syn[c][k]) ** 2
            rmse = math.sqrt(sse / len(syn_t))
            per_col[c] = (preds, rmse)
            score += rmse / syn_std[c]
        runs.append({"rank": rank, "score": score, "per_col": per_col})

    k_m_ac_vals = _linspace(n_runs, 4.0, 14.0)
    Y_ac_vals = _logspace(n_runs, -1.7, -1.1)
    k_dis_vals = _gaussian_jitter(n_runs, 0.5, 0.15, 42)

    sorted_runs = sorted(runs, key=lambda r: r["score"])
    best = sorted_runs[0]
    worst = sorted_runs[-1]

    fig = plt.figure(figsize=(15, 10), constrained_layout=True)
    gs = GridSpec(3, 3, figure=fig, height_ratios=[2.2, 2.2, 1.6])

    # Two trajectory panels (top two rows, full width)
    for row, col in enumerate(TRAJECTORY_PANELS):
        ax = fig.add_subplot(gs[row, :])
        for r in runs:
            if r["rank"] in (best["rank"], worst["rank"]):
                continue
            ax.plot(syn_t, r["per_col"][col][0], color="#bbbbbb",
                    linewidth=0.9, alpha=0.7, zorder=2)
        ax.plot(syn_t, worst["per_col"][col][0], color="#d62728",
                linewidth=2.0, linestyle="--", zorder=3,
                label=f"worst (rank {worst['rank']}, score {worst['score']:.2f})")
        ax.plot(syn_t, best["per_col"][col][0], color="#1f77b4",
                linewidth=2.4, zorder=4,
                label=f"best (rank {best['rank']}, score {best['score']:.2f})")
        ax.scatter(syn_t, syn[col], color="black", s=22, zorder=5,
                   label="synthetic measurements", edgecolor="white", linewidth=0.5)
        ax.set_xlabel("time (d)")
        ax.set_ylabel(col)
        ax.set_title(f"{col} — 15 ADM1 runs against synthetic data")
        ax.legend(loc="best", fontsize=9, framealpha=0.9)
        ax.grid(True, alpha=0.3)

    # Bottom row: bar chart + 2 param-vs-score scatters
    ax_bar = fig.add_subplot(gs[2, 0])
    ranks_sorted = [r["rank"] for r in sorted_runs]
    scores_sorted = [r["score"] for r in sorted_runs]
    bar_colors = ["#1f77b4" if r == best["rank"]
                  else "#d62728" if r == worst["rank"]
                  else "#888888" for r in ranks_sorted]
    ax_bar.bar(range(len(ranks_sorted)), scores_sorted, color=bar_colors)
    ax_bar.set_xticks(range(len(ranks_sorted)))
    ax_bar.set_xticklabels([str(r) for r in ranks_sorted], fontsize=8)
    ax_bar.set_xlabel("run rank (sorted by score)")
    ax_bar.set_ylabel("normalized RMSE")
    ax_bar.set_title("Match quality per run")
    ax_bar.grid(True, alpha=0.3, axis="y")

    # Param scatters
    rank_score = {r["rank"]: r["score"] for r in runs}
    param_specs = [
        ("k_m_ac", k_m_ac_vals, 8.0, "linear"),
        ("Y_ac", Y_ac_vals, 0.05, "log"),
    ]
    for col_i, (name, vals, default, scale) in enumerate(param_specs):
        ax = fig.add_subplot(gs[2, col_i + 1])
        xs = [vals[r - 1] for r in range(1, n_runs + 1)]
        ys = [rank_score[r] for r in range(1, n_runs + 1)]
        colors = ["#1f77b4" if r == best["rank"]
                  else "#d62728" if r == worst["rank"]
                  else "#888888" for r in range(1, n_runs + 1)]
        ax.scatter(xs, ys, c=colors, s=70, zorder=3, edgecolor="white", linewidth=0.5)
        ax.axvline(default, color="green", linestyle=":", alpha=0.7,
                   label=f"BSM2 default {default:g}")
        ax.set_xscale(scale)
        ax.set_xlabel(name)
        ax.set_ylabel("normalized RMSE")
        ax.set_title(f"score vs {name}")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        f"ADM1 parameter-search calibration "
        f"(best: rank {best['rank']} — k_m_ac={k_m_ac_vals[best['rank']-1]:.2f}, "
        f"Y_ac={Y_ac_vals[best['rank']-1]:.4f}, k_dis={k_dis_vals[best['rank']-1]:.3f})",
        fontsize=12,
    )
    fig.savefig("/tmp/match_plot.png", dpi=150)

    faasr_log(
        f"Best run: rank={best['rank']}, score={best['score']:.4f}, "
        f"k_m_ac={k_m_ac_vals[best['rank']-1]:.3f}, "
        f"Y_ac={Y_ac_vals[best['rank']-1]:.4f}, "
        f"k_dis={k_dis_vals[best['rank']-1]:.4f}"
    )

    faasr_put_file(
        local_file="match_plot.png",
        remote_file="match_plot.png",
        local_folder="/tmp",
        remote_folder=base,
    )
