"""Result tables (LaTeX rows) from ../data/derived.json, so no number is copied by hand."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "data", "derived.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "..", "tables")
os.makedirs(OUT, exist_ok=True)
MODELS = ["llama2", "codellama:7b", "starcoder2:3b"]
MODES = ["no_context", "code_only", "code_history", "oracle"]
TT = {"llama2": "llama2", "codellama:7b": "codellama:7b", "starcoder2:3b": "starcoder2:3b"}


def w(name, rows):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        # \bottomrule must sit in the same file as the last row: after \input returns, the
        # tabular has already started a new cell and \bottomrule would be a misplaced \noalign.
        fh.write("\n".join(rows) + "\n\\bottomrule\n")


def f2(x):
    return "--" if x is None else f"{x:.2f}"


def signed(x):
    s = f"{x:+.2f}"
    return "$-$" + s[1:] if s.startswith("-") else s


def dz(x):
    return f"{x:.2f}".replace("-", "$-$")


def verdict(p, control_ok=True):
    if p["mean_diff"] >= 0.10 and p["ci_low"] > 0:
        return "useful"
    return "inconclusive"


# Main held-out table
ho = D["codeorigin"]["heldout"]["models"]
rows = []
for m in MODELS:
    v = ho[m]["modes"]
    p = ho[m]["paired"]["history|code_only"]
    best = max(v[k]["history_mean"] for k in MODES[:3])
    cells = []
    for k in MODES:
        s = f2(v[k]["history_mean"])
        cells.append(f"\\textbf{{{s}}}" if k != "oracle" and abs(v[k]["history_mean"] - best) < 1e-9 else s)
    rows.append(f"{TT[m]} & " + " & ".join(cells) +
                f" & {signed(p['mean_diff'])} [{signed(p['ci_low'])}, {signed(p['ci_high'])}] & {p['p_value']:.3f} & {dz(p['effect_size_dz'])} & {verdict(p)} \\\\")
ds = D["codeorigin"]["deepseek_run10_summary"]
hm, e = ds["history_means"], ds["effect"]
rows.append("deepseek (hosted)$^{\\dagger}$ & " + " & ".join(
    (f"\\textbf{{{f2(hm[k])}}}" if k == "code_history" else f2(hm[k])) for k in MODES) +
    f" & {signed(e['mean'])} [{signed(e['low'])}, {signed(e['high'])}] & $<$0.001 & 1.61 & useful \\\\")
w("heldout.tex", rows)

# Demo-repository (run 5) effect, for the ablation of repository
demo = D["codeorigin"]["demo_dev"]["models"]

# Diagnostics: retrieval per mode and per-model quality in code_history
rows = []
for mode in ("code_only", "code_history", "oracle"):
    v = ho["llama2"]["modes"][mode]
    rows.append(f"{mode.replace('_', ' ')} & {f2(v['evidence_recall'])} & {f2(v['evidence_precision'])} \\\\")
w("retrieval.tex", rows)
rows = []
for m in MODELS:
    v = ho[m]["modes"]["code_history"]
    fl = v["failures"]
    rows.append(f"{TT[m]} & {f2(v['answerable_mean'])} & {100*v['hallucination_rate']:.0f}\\% & {f2(v['unsupported_ratio'])} & "
                f"{f2(v['citation_validity'])} & {v['latency_median_s']:.1f} & {fl.get('retrieval_miss', 0)} & "
                f"{fl.get('model_ignored_evidence', 0)} & {fl.get('hallucinated', 0)} & {fl.get('under_refused', 0)} \\\\")
w("quality.tex", rows)

# ChangeGuard per-category table
cg = D["changeguard"]
cats = ["code_explanation", "code_retrieval", "dependency_understanding", "bug_analysis", "rag_documentation",
        "code_generation", "refactoring", "repo_level_understanding"]
names = {"code_explanation": "Code explanation", "code_retrieval": "Code retrieval",
         "dependency_understanding": "Dependency understanding", "bug_analysis": "Bug analysis",
         "rag_documentation": "RAG / documentation", "code_generation": "Code generation",
         "refactoring": "Refactoring", "repo_level_understanding": "Repository-level"}
kf = cg["changeguard_keyfacts"]["local"]
rows = []
for c in cats:
    hg = [cg["hand_grades"][c][m] for m in MODELS]
    b = max(hg)
    hcell = " & ".join((f"\\textbf{{{x:.2f}}}" if abs(x - b) < 1e-9 else f"{x:.2f}") for x in hg)
    if c == "code_generation":
        kcell = " & ".join(kf[m]["codegen_pass"] + " pass" for m in MODELS)
    else:
        kcell = " & ".join(f"{kf[m]['category'][c]:.2f}" for m in MODELS)
    rows.append(f"{names[c]} & {cg['category_n'][c]} & {cg['precision_at_5'][c]:.2f} & {hcell} & {kcell} \\\\")
w("changeguard.tex", rows)

# ChangeGuard cost and reliability
hal, perf, cr = cg["changeguard_metrics"]["hallucination"], cg["changeguard_metrics"]["performance"], cg["codegen_rescore"]
rows = []
for m in MODELS:
    h, p, c = hal[m], perf[m], cr[m]
    rows.append(f"{TT[m]} & {h['unsupported_references']}/{h['references']} & {100*h['answer_rate']:.0f}\\% & "
                f"{p['latency_median_s']:.1f} & {p['latency_p95_s']:.1f} & {p['tokens_per_s']:.1f} & {p['cpu_pct_mean']:.0f}\\% & "
                f"{p['mem_gib_mean']:.2f} & {c['raw_pass']}/{c['items']} & {c['all_tests_pass']}/{c['items']} & {c['meaningful_pass']}/{c['items']} \\\\")
w("changeguard_cost.tex", rows)

# Ablation table: one component changed at a time
p5 = {m: demo[m]["paired"]["history|code_only"]["mean_diff"] for m in MODELS}
p8 = {m: ho[m]["paired"]["history|code_only"]["mean_diff"] for m in MODELS}
orc = {m: ho[m]["modes"]["oracle"]["history_mean"] - ho[m]["modes"]["code_history"]["history_mean"] for m in MODELS}
noc = {m: ho[m]["paired"]["history|no_context"]["mean_diff"] for m in MODELS}
gd, gc = cg["codegen_grounded_deepseek_rescore"]["cloud"], cg["changeguard_deepseek_codegen_rescore"]["cloud"]
ch, rt = cg["chunking"], cg["retrieval"]
trip = lambda d: " / ".join(signed(d[m]) for m in MODELS)
rows = [
    "\\multicolumn{3}{@{}l}{\\emph{CodeOrigin (history gain on 24 held-out history questions; llama2 / codellama / starcoder2)}} \\\\",
    f"Remove history from retrieval & code only $\\rightarrow$ code + history & {trip(p8)} \\\\",
    f"Remove all retrieval & no context $\\rightarrow$ code + history & {trip(noc)} \\\\",
    f"Replace retrieval with gold evidence & code + history $\\rightarrow$ oracle & {trip(orc)} \\\\",
    f"Change repository & held-out $\\rightarrow$ fictional demo (run 5) & {trip(p5)} \\\\",
    "Change the scorer & key facts $\\rightarrow$ DeepSeek judge & +0.35 / +0.35 / +0.06 \\\\",
    "Drop 2 weak questions & 24 $\\rightarrow$ 22 questions & +0.33 / +0.27 / $-$0.02 \\\\",
    "\\midrule",
    "\\multicolumn{3}{@{}l}{\\emph{ChangeGuard (5 retrieval questions; 4 test-generation tasks)}} \\\\",
    f"Chunking & fixed 800 chars $\\rightarrow$ AST/structure & P@5 {ch['fixed']['p5']:.2f} $\\rightarrow$ {ch['structure']['p5']:.2f}; context {ch['fixed']['chars']} $\\rightarrow$ {ch['structure']['chars']} chars \\\\",
    f"Metadata filter & all files $\\rightarrow$ source code only & P@5 {rt['vector_similarity']['p5']:.2f} $\\rightarrow$ {rt['metadata_filtered_source_code']['p5']:.2f} \\\\",
    f"Test prompt context (DeepSeek) & no example test $\\rightarrow$ retrieved test file & meaningful passes {gc['meaningful_pass']}/{gc['items']} $\\rightarrow$ {gd['meaningful_pass']}/{gd['items']} \\\\",
    f"Code extraction before pytest & raw reply $\\rightarrow$ extracted code & local passes 0/12 $\\rightarrow$ {sum(cr[m]['all_tests_pass'] for m in MODELS)}/12 (meaningful {sum(cr[m]['meaningful_pass'] for m in MODELS)}/12) \\\\",
]
w("ablation.tex", rows)
print("tables ok")
