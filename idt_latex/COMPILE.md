# How to compile the paper

The paper is `idt_latex.tex`, with references in `references.bib`. The figures in
`figures/` and the tables in `tables/` must stay in those folders next to the `.tex`
file. The paper uses BibTeX, so compiling takes four steps: pdflatex, bibtex, then
pdflatex twice more. Overleaf and `latexmk` run these steps for you.

## Option 1: Overleaf (required for submission)

1. Zip the whole `idt_latex` folder. On Windows: right-click the folder, then
   **Send to → Compressed (zipped) folder**.
2. On overleaf.com choose **New Project → Upload Project** and select the zip.
3. Rename the project to your section and group number, e.g. `CSE1_G5`
   (**Menu → Settings → Project name**, or click the title).
4. Open **Menu** (top left) and check:
   - **Compiler:** pdfLaTeX
   - **Main document:** `idt_latex.tex`
   - **TeX Live version:** the latest one
5. Click **Recompile**. The first compile can take about a minute.
6. Click **Share** and add your course faculty's BMU email as an **Editor**.
7. Copy the project URL from the address bar and paste it into `idt_latex.tex`
   on the line `\noindent\textbf{Overleaf Project Link:} \url{...}`, then
   recompile.
8. Download the PDF with the download icon next to **Recompile**.

If the upload puts everything inside an extra folder (for example
`idt_latex/idt_latex.tex`), set **Main document** to that file. The relative
paths will still work.

## Option 2: On your own computer

Install one TeX distribution:

- Windows: MiKTeX (https://miktex.org/download). The first time you compile,
  allow it to install missing packages.
- macOS: MacTeX (https://tug.org/mactex/).
- Linux: `sudo apt install texlive-publishers texlive-science texlive-latex-extra latexmk`

Then, inside the `idt_latex` folder, either let `latexmk` run every step:

```bash
latexmk -pdf idt_latex.tex
```

or run the four steps by hand:

```bash
pdflatex idt_latex.tex
bibtex idt_latex
pdflatex idt_latex.tex
pdflatex idt_latex.tex
```

The output is `idt_latex.pdf`. To delete the build files afterwards, run
`latexmk -c`.

### Alternative: Tectonic (one program, nothing else to install)

Download it from https://tectonic-typesetting.github.io, then run:

```bash
tectonic idt_latex.tex
```

Tectonic runs BibTeX by itself and downloads any packages it needs.

## Packages used

`IEEEtran` (document class), `geometry`, `times`, `graphicx`, `amsmath`, `amssymb`,
`booktabs`, `cite`, `url`, `array` and `algorithm2e`. Overleaf and full TeX Live have
all of them. On MiKTeX, accept the prompts to install them.

## Common problems

| Message | Cause and fix |
|---|---|
| `File 'architecture.pdf' not found` | The `figures/` folder was not uploaded, or was renamed. Keep `figures/` next to `idt_latex.tex`. |
| `File 'tables/heldout.tex' not found` | Same problem for `tables/`. Upload the whole folder. |
| Citations show as `[?]` | BibTeX has not run yet. On Overleaf, click Recompile again. Locally, run the four steps above. |
| `algorithm2e.sty not found` | MiKTeX: allow the package install. Linux: install `texlive-science`. |
| `Overfull \hbox` warnings | A wide table is slightly too wide. These are warnings, not errors, so the PDF is still produced. Check the table in the PDF; if it runs into the margin, shorten its text or reduce its `p{..cm}` column widths. |
| Reference numbers show as `??` | Compile once more; LaTeX resolves references on the second pass. |

## Regenerating figures and tables (only if the data changes)

The committed PDFs and `.tex` tables are what the paper uses, so you do **not**
need Python to compile. If you change the results, run these from the
repository root:

```bash
python idt_latex/figures/make_figures.py   # result plots, from data/derived.json
python idt_latex/figures/make_tables.py    # result tables, from data/derived.json
```

`data/make_data.py` rebuilds `data/derived.json` from the raw evaluation runs. See
`README.md` for its arguments.

## Before you submit

- Search the PDF for `Name1`, `Group XX` and `REPLACE`: replace every placeholder.
- Check that the layout is still single column, with no section starting on a new page.
- Upload the compiled PDF, not the `.tex` file, to Google Classroom.
