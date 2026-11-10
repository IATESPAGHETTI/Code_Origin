"""Result figures for the paper, drawn from ../data/derived.json (vector PDF)."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "data", "derived.json"), encoding="utf-8"))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times"], "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
MODES = ["no_context", "code_only", "code_history", "oracle"]
MODE_LABEL = {"no_context": "No context", "code_only": "Code only", "code_history": "Code + history", "oracle": "Oracle"}
MODELS = ["llama2", "codellama:7b", "starcoder2:3b"]
MODE_COL = {"no_context": "#c9c9c9", "code_only": "#8fb3ea", "code_history": "#2f5fb3", "oracle": "#d27a1f"}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, name + ".pdf"))
    plt.close(fig)


# Fig. 3: held-out history-question correctness by mode
ho = D["codeorigin"]["heldout"]["models"]
ds = D["codeorigin"]["deepseek_run10_summary"]["history_means"]
groups = MODELS + ["deepseek (hosted)"]
fig, ax = plt.subplots(figsize=(6.2, 2.9))
w = 0.2
for mi, mode in enumerate(MODES):
    xs, ys, lo, hi = [], [], [], []
    for gi, g in enumerate(groups):
        if g in ho:
            v = ho[g]["modes"][mode]
            y, (l, h) = v["history_mean"], v["history_ci"]
        else:
            y, l, h = ds[mode], ds[mode], ds[mode]
        xs.append(gi + (mi - 1.5) * w)
        ys.append(y)
        lo.append(y - l)
        hi.append(h - y)
    n = len(MODELS)  # local models carry bootstrap intervals; the hosted run stored only means
    ax.bar(xs[:n], ys[:n], w, yerr=[lo[:n], hi[:n]], capsize=2, color=MODE_COL[mode], label=MODE_LABEL[mode],
           error_kw={"lw": 0.7})
    ax.bar(xs[n:], ys[n:], w, color=MODE_COL[mode])
ax.set_xticks(range(len(groups)))
ax.set_xticklabels(groups)
ax.set_ylabel("Correctness, 24 history questions")
ax.set_ylim(0, 1.08)
ax.legend(frameon=False, ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.15))
save(fig, "fig_heldout_modes")

# Fig. 4: history effect (code_history - code_only) with 95% CI
rows = []
for run, key in (("Demo repository (run 5)", "demo_dev"), ("pallets/itsdangerous (run 8)", "heldout")):
    for m in MODELS:
        p = D["codeorigin"][key]["models"][m]["paired"]["history|code_only"]
        rows.append((f"{m}, {run}", p["mean_diff"], p["ci_low"], p["ci_high"], p["n"]))
e = D["codeorigin"]["deepseek_run10_summary"]["effect"]
rows.append(("deepseek (hosted), pallets/itsdangerous (run 10)", e["mean"], e["low"], e["high"], 24))
fig, ax = plt.subplots(figsize=(6.2, 3.0))
for i, (lab, m, l, h, n) in enumerate(rows[::-1]):
    col = "#2f5fb3" if l > 0 else "#7a7a7a"
    ax.errorbar(m, i, xerr=[[m - l], [h - m]], fmt="o", color=col, capsize=3, ms=5)
ax.axvline(0, color="#444", lw=0.8)
ax.axvline(0.10, color="#d27a1f", lw=0.8, ls="--")
ax.text(0.12, 4.5, "dashed line: pre-registered minimum gain (0.10)", fontsize=7, color="#a65c12", va="center")
ax.set_yticks(range(len(rows)))
ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=8)
ax.set_xlabel("Correctness gain from history (code + history minus code only), 95% CI")
ax.set_xlim(-0.3, 1.0)
save(fig, "fig_effect")

# Fig. 5: ChangeGuard hand-graded correctness per category
cg = D["changeguard"]["hand_grades"]
cats = ["code_explanation", "code_retrieval", "dependency_understanding", "bug_analysis", "rag_documentation",
        "code_generation", "refactoring", "repo_level_understanding"]
labels = ["Explanation", "Retrieval", "Dependency", "Bug analysis", "RAG / docs", "Code gen.", "Refactoring", "Repo-level"]
M = [[cg[c][m] for c in cats] for m in MODELS]
fig, ax = plt.subplots(figsize=(6.2, 2.0))
im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(cats)))
ax.set_xticklabels(labels, fontsize=8, rotation=20, ha="right")
ax.set_yticks(range(3))
ax.set_yticklabels(MODELS, fontsize=8)
for i in range(3):
    for j in range(len(cats)):
        ax.text(j, i, f"{M[i][j]:.2f}", ha="center", va="center", fontsize=8, color="white" if M[i][j] > 0.55 else "black")
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("Correctness", fontsize=8)
for s in ax.spines.values():
    s.set_visible(False)
save(fig, "fig_changeguard")

# Fig. 6: quality against speed for both systems
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.4, 2.6))
for m, mk in zip(MODELS, ["o", "s", "^"]):
    v = ho[m]["modes"]["code_history"]
    a1.scatter(v["latency_median_s"], v["hallucination_rate"], marker=mk, s=40, color="#2f5fb3")
    a1.annotate(m, (v["latency_median_s"], v["hallucination_rate"]), textcoords="offset points", xytext=(5, 4), fontsize=8)
a1.set_xlabel("Median latency (s)")
a1.set_ylabel("Hallucination rate")
a1.set_title("(a) CodeOrigin, held-out, code + history", fontsize=9)
a1.set_ylim(0, 0.75)
a1.set_xlim(0, 20)
perf = D["changeguard"]["changeguard_metrics"]["performance"]
hal = D["changeguard"]["changeguard_metrics"]["hallucination"]
for m, mk in zip(MODELS, ["o", "s", "^"]):
    x, y = perf[m]["latency_median_s"], hal[m]["answer_rate"]
    a2.scatter(x, y, marker=mk, s=40, color="#d27a1f")
    a2.annotate(m, (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
a2.set_xlabel("Median latency (s)")
a2.set_ylabel("Answers with fabricated refs")
a2.set_title("(b) ChangeGuard, 27 questions", fontsize=9)
a2.set_ylim(0, 0.35)
a2.set_xlim(0, 70)
save(fig, "fig_cost")
print("figures ok")
