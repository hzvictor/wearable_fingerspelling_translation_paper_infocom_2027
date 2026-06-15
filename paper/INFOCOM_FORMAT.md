# INFOCOM Paper Format Notes

As of 2026-06-15, the IEEE INFOCOM 2027 main-conference author instructions were not available from the public INFOCOM site. This project is initialized from the official IEEE INFOCOM 2026 main-conference submission rules and should be rechecked once INFOCOM 2027 publishes its CFP and submission guidelines.

Official sources checked:

- INFOCOM 2026 Call for Papers: https://infocom2026.ieee-infocom.org/call-papers
- INFOCOM 2026 Main Conference Submission Guidelines: https://infocom2026.ieee-infocom.org/submission-guidelines-main-conference
- INFOCOM 2026 Final Paper Submission Guidelines: https://infocom2026.ieee-infocom.org/authors/final-paper-submission-guidelines-main-conference
- IEEE conference templates page linked by INFOCOM: https://www.ieee.org/conferences/publishing/templates.html

Working format assumptions:

- Use standard IEEE Transactions/IEEEtran conference format.
- LaTeX class: `IEEEtran.cls` version 1.8, unmodified.
- Preamble required by INFOCOM 2026: `\documentclass[10pt,conference,letterpaper]{IEEEtran}`.
- Use 10-point Times, two columns, US letter, and default IEEEtran margins and line spacing.
- Do not use packages or commands that override margins, font size, line spacing, column separation, caption spacing, or section spacing.
- Submission manuscript is double blind: no author names, affiliations, acknowledgments, identifying PDF metadata, or self-identifying links.
- Maximum length: 10 printed pages total.
- Main text, including figures, tables, appendices, and all non-reference material, must be no more than 9 pages.
- References may occupy the remaining space up to page 10.
- Paper must be self-contained; reviewers are not required to inspect external supplementary material.
- Figures must remain legible in black-and-white printing.

Before submission:

- Recheck INFOCOM 2027 rules, deadlines, EDAS link, author cap, and anonymity policy.
- Verify PDF page count and that references start no earlier than page 10 only if main text reaches page 9.
- Remove author-identifying metadata from the generated PDF.
- For final camera-ready, restore full author list exactly as submitted in EDAS metadata.
