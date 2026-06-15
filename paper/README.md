# Paper Workspace

This directory is the LaTeX writing area for the INFOCOM 2027 paper.

## Structure

- `main.tex`: paper entry point and section assembly.
- `macros.tex`: packages and local commands.
- `sections/`: editable paper text, one file per major section.
- `figures/`: paper figures committed to the repository.
- `tables/`: large table sources or generated table fragments.
- `refs/references.bib`: BibTeX database.
- `template/`: official IEEE template sample kept for reference.
- `INFOCOM_FORMAT.md`: format notes and conference-rule checklist.

BibTeX lines are present but commented in `main.tex` until the paper has real citations and `IEEEtran.bst` is available in the TeX environment or committed to the repository.

## Build

Run from this directory:

```sh
make
```

The PDF is generated under `build/main.pdf`.
