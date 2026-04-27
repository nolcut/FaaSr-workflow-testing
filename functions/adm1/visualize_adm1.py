import csv
import math
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


OBSERVABLES = ["S_ac", "S_ch4", "S_gas_ch4", "pH"]


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

    s_min = min(r["score"] for r in runs)
    s_max = max(r["score"] for r in runs)
    cmap = plt.get_cmap("viridis_r")

    def color_for(score):
        t = (score - s_min) / (s_max - s_min) if s_max > s_min else 0.0
        return cmap(t)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    for ax, col in [(axes[0, 0], "S_ch4"), (axes[0, 1], "pH")]:
        for r in runs:
            ax.plot(syn_t, r["per_col"][col][0], color=color_for(r["score"]),
                    linewidth=0.9, alpha=0.85)
        ax.scatter(syn_t, syn[col], color="red", s=14, zorder=5, label="synthetic")
        ax.set_xlabel("time (d)")
        ax.set_ylabel(col)
        ax.set_title(f"{col}: 15 runs vs synthetic")
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, alpha=0.3)

    sorted_runs = sorted(runs, key=lambda r: r["score"])
    ranks = [r["rank"] for r in sorted_runs]
    scores = [r["score"] for r in sorted_runs]
    bar_colors = [color_for(s) for s in scores]
    axes[1, 0].bar(range(len(ranks)), scores, color=bar_colors)
    axes[1, 0].set_xticks(range(len(ranks)))
    axes[1, 0].set_xticklabels([str(r) for r in ranks])
    axes[1, 0].set_xlabel("run rank (sorted by score)")
    axes[1, 0].set_ylabel("normalized RMSE (sum over observables)")
    axes[1, 0].set_title("Match quality per run (lower is better)")
    axes[1, 0].grid(True, alpha=0.3, axis="y")

    rank_score = {r["rank"]: r["score"] for r in runs}
    xs = [k_m_ac_vals[r - 1] for r in rank_score]
    ys = [rank_score[r] for r in rank_score]
    axes[1, 1].scatter(xs, ys, c=[color_for(s) for s in ys], s=80)
    for r in runs:
        axes[1, 1].annotate(str(r["rank"]),
                            (k_m_ac_vals[r["rank"] - 1], r["score"]),
                            textcoords="offset points", xytext=(5, 4), fontsize=9)
    axes[1, 1].axvline(8.0, color="gray", linestyle="--", alpha=0.6, label="default 8.0")
    axes[1, 1].set_xlabel("k_m_ac (linspace 4..14)")
    axes[1, 1].set_ylabel("normalized RMSE")
    axes[1, 1].set_title("Score vs swept k_m_ac")
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    fig.suptitle("ADM1 parameter-search match against synthetic measurements", fontsize=13)
    fig.tight_layout()
    fig.savefig("/tmp/match_plot.png", dpi=150)

    best = sorted_runs[0]
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
