# idt_latex: research paper (ChangeGuard + CodeOrigin platform)

Upload this folder to Overleaf (New Project, Upload Project, as a zip).
Main file: `idt_latex.tex`. Compiler: pdfLaTeX. Bibliography: `references.bib` (25 entries).

```
idt_latex.tex             paper (template preamble + amssymb, array)
references.bib            references, taken from the team's checked related-work list
figures/*.pdf             vector figures (no screenshots)
tables/*.tex              result tables, generated from data/derived.json
data/derived.json         every number used in the paper, recomputed from the stored runs
data/make_data.py         builds derived.json from the raw run files
figures/make_figures.py   result plots          (reads data/derived.json)
figures/make_tables.py    result tables          (reads data/derived.json)
figures/make_diagrams.py  Fig. 1 and Fig. 2, as PDF and as Claude Design artboards
```

## Where the numbers come from

| Result | Raw source |
|---|---|
| CodeOrigin held-out run 8 (399 answers) | `reports/itsdangerous_heldout.json` |
| CodeOrigin demo run 5 (255 answers) | `reports/dev_full_3models.json` |
| CodeOrigin hosted run 10 (DeepSeek) | merged platform `eval/results/deepseek_*.json` |
| ChangeGuard 27-question comparison | `endsem/evaluation/results.json`, `CATEGORY_COMPARISON.md` |
| ChangeGuard references, cost, code-gen rescore | merged platform `eval/results/changeguard_metrics.json`, `codegen_*.json` |

CodeOrigin statistics are recomputed with CodeOrigin's own `services/eval/app/stats.py`
(2000 bootstrap resamples, sign-flip test, seed 0) and match `docs/EVALUATION.md`.

## Regenerating

```
python idt_latex/data/make_data.py --codeorigin <CodeOrigin dir> --changeguard <endsem dir> --platform-eval <merged eval dir>
python idt_latex/figures/make_figures.py
python idt_latex/figures/make_tables.py
```

`make_figures.py` and `make_tables.py` need only `data/derived.json`, which is committed.

## Before submitting

- Replace group number, names, roll numbers, the Overleaf link and the contribution lines.
- Rewrite the text in your own words (AI-content limit 10%) and make the AI-use declaration
  match what you actually did.
- Each configuration was run once at temperature 0; the paper reports bootstrap intervals,
  not mean +/- s.d. over 3 runs. If your faculty requires 3 runs, rerun with 3 seeds.
