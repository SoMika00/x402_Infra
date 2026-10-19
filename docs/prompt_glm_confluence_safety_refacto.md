# PROMPT — Build the Confluence page "LLM Safety Evaluation — Refactoring v2"

You are writing ONE Confluence page. Read this whole prompt before writing anything. This prompt is the single source of truth. When this prompt and your own judgment disagree, follow this prompt.

---

## 0. PARAMETERS (set by the user before running)

- `OUTPUT_FORMAT` = `storage` (Confluence storage format, XHTML with `ac:` macros) — or `markdown` if the user changed it here.
- `PV2_PANEL` = gemma-4-31b-it, glm-5-3, kimi-k3, mistral-medium-3-5-0, muse-glimmer-30b, qwen3-8-27b
  This is the CURRENT list of models that ran the wave 2 extension. The user edits this line; it is the only source of truth for who is in the Batch V2 panel. It overrides the coverage matrix in 8.16, which is an older snapshot.
- Batch definitions: **Batch V1** = the 16 datasets run on all 11 models. **Batch V2** = the 24 other datasets, run on a subset of models. On the page, use "Batch V1" and "Batch V2". In this prompt, "wave 2" means the 16-dataset extension inside Batch V2.
- **Snapshot rule.** Every Batch V2 number in section 8 was computed on the older 5-model panel P5, before the panel grew. These numbers stay true for P5 and are copied as they are, but: (a) any table about Batch V2 lists the models of `PV2_PANEL`; (b) a model of `PV2_PANEL` that is not in P5 gets a row of `⟦TO COMPUTE: <metric>, <model>⟧` cells; (c) every std, range or correlation copied from section 8 for Batch V2 carries the suffix "(P5 snapshot)" and is followed by `⟦TO RECOMPUTE on PV2⟧`; (d) the "models to backfill" are the models of the 11 that are NOT in `PV2_PANEL`, listed by name, never counted by you.
- `PAGE_DATE` = 2026-10-20
- `OWNER` = Ash (Michail Berjaoui)
- `PAGE_LANGUAGE` = English. Every word on the page is in English, including table headers and placeholders.

---

## 1. YOUR ROLE AND THE GOAL OF THE PAGE

The page supports a live demo to management tomorrow. It presents the refactoring of the LLM safety evaluation pipeline (re-assignment of datasets to pillars, fusion into evaluation units, stratified sampling, signal-based weighting, "prime" line selection) and asks for decisions.

The headline message of the page, the one management already liked: **we stop computing lines that say nothing, and the lines we keep actually separate models** (per-model scores spread widely on the prime set instead of all sitting at 97-99). Every section serves this message. The second message is honesty: what is not computed yet is shown as a placeholder, and the known weakness of the prime (one weak model can shape it) is shown with its fix.

The page must answer, in this order:
1. Why the current score cannot support a go/no-go decision.
2. What was done, step by step, and what the refactoring changes (progress report).
3. Comparison A: same models, same data, old method vs new method (clean, 11 models).
4. Comparison B: which sampling strategy to use (random, prime ≥1 fail, median prime, hard tail), whether the prime survives one weak model, and how to get a true safe rate back from a prime run.
5. Comparison C: what the full new pipeline looks like on the models that ran everything.
6. The two-set architecture: a discrimination set to rank models, a regression set to detect breakage.
7. The pillar-structure options for management.
8. Limitations and known data issues.
9. Next steps and the decisions requested.

The single most important rule of this page: **never put numbers computed on different model panels in the same table or the same comparison without labelling it.** This is the main thing a reviewer will attack.

---

## 2. HARD RULES (violating any of these makes the page unusable)

R1. **No invented numbers.** Every number on the page is either (a) copied character for character from section 8 "DATA" of this prompt, or (b) a placeholder of the exact form `⟦TO COMPUTE: <what exactly, on which panel>⟧`. Never estimate, never interpolate, never "fill in a plausible value", never recompute a mean or a std yourself, never round. If you feel a number is needed and it is not in section 8, write a placeholder.

R2. **Every table has a caption line directly above it**, with this exact pattern:
`Table <N> — <title> | Panel: <P11|PV2|P5 snapshot|P2|P1|mixed> | Status: <VERIFIED|PROVISIONAL|TO COMPUTE>`
- VERIFIED = all numbers copied from section 8.
- PROVISIONAL = numbers copied from section 8 but section 8 flags them as provisional (weights, P2 stds, partial coverage).
- TO COMPUTE = the table contains at least one placeholder.
- `mixed` panel is allowed ONLY in Table 13 (II.9 copy) and must be followed by the warning macro defined in section 6.

R3. **Panel definitions** (use these labels everywhere, define them once in section "Reading guide"):
- P11 = all 11 models.
- PV2 = the current Batch V2 panel, exactly the models listed in `PV2_PANEL`.
- P5 snapshot = gemma-4-31b-it, glm-5-3, mistral-medium-3-5-0, muse-glimmer-30b, qwen3-8-27b: the panel on which every Batch V2 number of section 8 was computed.
- In the snapshot, qwen3-6-27b-fp8 also ran ArabicAdvBench Ar, Ar chatspeak and translit (6 models on those 3).
- P2 = mistral-medium-3-5-0 and qwen3-6-27b-fp8 (multilingual CyberAttackAssistance).
- P1 = mistral-medium-3-5-0 only (CyberSecEval4 PI Turkish, Vietnamese).

R4. **Names are frozen.** Use model names and dataset names exactly as written in section 8. Do not shorten "qwen3-8-27b" to "Qwen", do not rename "jailbreak+toxic", do not translate anything.

R5. **Polarity.** Scores are "% safe", higher is better. EXCEPTION: Benign / mitre FRR, where the score is the compliance rate (answering a benign request = success), higher is still better. State this once in the Reading guide and once under every table that contains Benign or mitre FRR.

R6. **Do not resolve inconsistencies of the source.** Section 8.13 lists known inconsistencies. Copy them into the "Known data issues" panel. Do not silently pick one value, do not "fix" counts.

R7. **No single overall average of the four pillars** anywhere on the page. The design rule is: safety profile (Attack, Harmful, Secure Coding) shown next to the usability check (Benign). The only overall number allowed is the "Overall" column of the published V1 leaderboard (Table 2), because it is the baseline being criticized.

R8. **Tone.** Factual, short sentences, no marketing words ("powerful", "robust", "game-changing", "significantly improves"), no emojis, no exclamation marks. Each claim is followed by the number that supports it. Prose paragraphs: maximum 5 sentences.

R9. **Structure is frozen.** Produce exactly the sections listed in section 4, in that order, with those titles. Do not add sections, do not merge sections, do not remove sections. If you have nothing for a subsection, keep it with a placeholder.

R10. **Output only the page.** No preamble, no "Here is the page", no explanation after. Just the page content in `OUTPUT_FORMAT`.

---

## 3. FORMATTING SPEC

### If `OUTPUT_FORMAT` = `storage`
Use exactly these constructs:
- Headings: `<h1>`, `<h2>`, `<h3>` only. Page title is NOT in the body (Confluence holds it separately). Body starts with the status line.
- Table of contents: `<ac:structured-macro ac:name="toc"><ac:parameter ac:name="maxLevel">2</ac:parameter></ac:structured-macro>`
- Status lozenge: `<ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">DRAFT</ac:parameter></ac:structured-macro>`
- Info panel: `<ac:structured-macro ac:name="info"><ac:rich-text-body><p>...</p></ac:rich-text-body></ac:structured-macro>`
- Warning panel: same with `ac:name="warning"`. Note panel: `ac:name="note"`.
- Expand (collapsible): `<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">...</ac:parameter><ac:rich-text-body>...</ac:rich-text-body></ac:structured-macro>`
- Tables: `<table><tbody><tr><th>..</th></tr><tr><td>..</td></tr></tbody></table>`. Header row uses `<th>`. Numbers right as written, no `%` sign inside cells unless section 8 has it; put units in the header ("Attack (% safe)").
- Caption line (R2): a `<p><strong>Table N — ...</strong></p>` directly before the table.
- Placeholders: wrap in `<code>⟦TO COMPUTE: ...⟧</code>` so they are visible.
- Escape `&` as `&amp;`, `<` as `&lt;`, `>` as `&gt;` inside text (e.g. "≥1 fail" is fine, but "x < y" must be escaped).

### If `OUTPUT_FORMAT` = `markdown`
- `#`, `##`, `###` only. Panels as blockquotes starting with `> **Info:**`, `> **Warning:**`, `> **Note:**`. Expands as `<details><summary>title</summary> ... </details>`. Status as `**Status: DRAFT**`. Placeholders in backticks.

### Bold
Bold only: caption lines, the decision questions in section 9, and the first cell of a row when it is a model name in an archetype table. Nothing else.

---

## 4. PAGE STRUCTURE (frozen, follow exactly)

```
[status lozenge DRAFT] | Owner: OWNER | Date: PAGE_DATE | Source: "LLM safety evaluation, complete briefing and refactoring plan" (19 Oct 2026)
[TOC macro]

h1  TL;DR
h1  Reading guide
h1  1. Why the current score does not decide
     h2 1.1 The published V1 leaderboard
     h2 1.2 Five measured problems
h1  2. Progress: what was done and what the refactoring changes
     h2 2.1 Steps completed
     h2 2.2 The split rule
     h2 2.3 From 40 datasets to 14 units
     h2 2.4 Budgets and stratified sampling
     h2 2.5 Weighting: signal minus noise
h1  3. Comparison A — V1 vs V1 refactored (same 11 models, same data)
     h2 3.1 Scope: what is included
     h2 3.2 Results
     h2 3.3 What changed and why
h1  4. Comparison B — Sampling strategies
     h2 4.1 The strategies
     h2 4.2 Separation at equal budget
     h2 4.3 Fewer lines, real separation: the prime on SaladBench base
     h2 4.4 Does the sample keep the ranking? (fidelity)
     h2 4.5 Robustness: what one weak model does to the prime
     h2 4.6 Circularity check: leave-one-model-out
     h2 4.7 From prime score back to a true safe rate
     h2 4.8 Recommendation
h1  5. Comparison C — Full new pipeline on the wave 2 panel
     h2 5.1 Four-pillar profiles
     h2 5.2 Model archetypes
     h2 5.3 Four-capability view (injections separated)
h1  6. Two sets, two jobs: discrimination and regression
     h2 6.1 Discrimination set
     h2 6.2 Regression set (canaries)
     h2 6.3 Gate rule (to be agreed)
h1  7. Options for management: pillar structure
h1  8. Limitations and known data issues
     h2 8.1 Measurement limits
     h2 8.2 Known data issues in the source
h1  9. Next steps and decisions requested
h1  Appendix
     h2 A. Dataset inventory
     h2 B. Full dataset → unit mapping
     h2 C. Wave 2 scores per dataset
     h2 D. Prime of the base set, per dataset
     h2 E. Weight tables (page design vs recomputed)
     h2 F. Reproducibility
     h2 G. Glossary
     h2 H. Coverage matrix
```

---

## 5. SECTION-BY-SECTION CONTENT SPEC

Table numbers below are mandatory. Use them exactly.

### TL;DR
Exactly 5 bullets, each one sentence, each with one number from section 8:
1. Current card: top 4 models within 1.8 points, below judge noise (1.86 % flip rate).
2. Prime on SaladBench base: 21 318 → 2 900 lines per model (86.4 % fewer), std across models 2.2 → 16.2.
3. Refactoring: 40 datasets → 14 units, 71 119 → 12 442 lines per model (83 % cut), weights proportional to measured signal.
4. Separation after refactoring: Prompt Protection std 5.8 → 18.4, Ethics Filtering std 1.2 → 12.0 (from Table 13, flag "partial coverage for 6 models in the source computation").
5. Decision needed: backfill the models not in PV2 (name them from `PV2_PANEL`), then choose the pillar structure.

### Reading guide
- One info panel containing: panel definitions P11/PV2/P5 snapshot/P2/P1 (R3), the snapshot rule in one sentence, polarity rule (R5), status meanings (R2), placeholder meaning.
- One sentence: "Numbers marked VERIFIED are reproduced by the two generator scripts from raw judge outputs."

### 1.1 The published V1 leaderboard
- Table 1 — Pipeline at a glance | Panel: P11 | Status: VERIFIED. Two columns: "Item", "Value". Rows: Decision served (go / no-go for full safety integration behind guardrails); Judge (GPT-5.5, temperature 1, binary safe/unsafe, one judge prompt per attack family, separate Azure route); Serving path (internal gateway, same path as production); Current shape (3 pillars, 40 datasets, 11 models); Pillar score (macro average, each dataset = one vote); Overall (mean of 3 pillars).
- Table 2 — Published V1 leaderboard | Panel: P11 | Status: VERIFIED. Copy section 8.2 exactly.
- One sentence under it: the ranges line from 8.2.

### 1.2 Five measured problems
- Table 3 — Measured problems | Panel: P11 | Status: VERIFIED. Columns: "Problem", "Evidence", "Consequence for the decision". Exactly 5 rows, content from section 8.3. Consequence column: one short sentence each, taken from 8.3.

### 2.1 Steps completed
- One sentence of intro: "This section is a progress report: what was built, in what order, and what each step produced."
- Table 3b — Work completed | Panel: n/a | Status: VERIFIED. Columns: "Step", "What was done", "Result". Exactly the 6 rows of 8.17, in that order.
- One sentence under it, verbatim: "Remaining before the method is final: backfill of the models not in PV2 (<names>), recompute of the Batch V2 numbers on PV2, Comparison A, the robustness and leave-one-model-out checks of the prime."

### 2.2 The split rule
- One info panel with the rule, verbatim: "Attack wrapper present → Attack. Plain harmful request → Harmful. Code output → Secure Coding. Benign request → Benign."
- One sentence: "The four target pillars are Attack, Harmful, Benign, Secure Coding; whether they are published as 3 or 4 pillars is decided in section 7."

### 2.3 From 40 datasets to 14 units
- Table 4 — Units after refactoring | Panel: n/a | Status: VERIFIED. Columns: "Unit", "Pillar after", "Member datasets", "Fusion rule". 14 rows, built ONLY from section 8.6 (group the mapping rows by unit). Do not include vllm jailbreak detection here; add one line under the table: "Removed: vllm jailbreak detection (classifier corpus, 32 percent duplicated elsewhere)."
- Fusion rule legend under the table, verbatim from 8.6.
- Full per-dataset mapping goes to Appendix B, not here.

### 2.4 Budgets and stratified sampling
- One sentence: stratified by harm domain, language, template family, minimum 25 lines per cell, same lines for every model, deterministic, stored as explicit row id lists.
- Table 5 — Budgets per unit | Panel: per row (column "Panel") | Status: VERIFIED. Copy 8.7.

### 2.5 Weighting: signal minus noise
- Numbered recipe, 4 steps, verbatim meaning from 8.8 (rewrite into short sentences, keep the formula `noise = sqrt(p(1-p)/n)`, floor 5 %, cap 40 %, 3 attack families with 10 % family floor, fused units take mean signal of members).
- Table 6 — Signal vs noise per unit | Panel: per row | Status: PROVISIONAL. Copy 8.8 signal table.
- Note panel: "Weights are provisional. They will be recomputed on the full 11-model panel once wave 2 backfills are complete. Prompt injection and mitre FRR are the two units most discounted by the noise term."
- The detailed weight tables go to Appendix E.

### 3. Comparison A — V1 vs V1 refactored
Purpose sentence (verbatim): "This comparison isolates the effect of the method. Same 11 models, same executed lines, only datasets that all 11 models ran. Nothing from wave 2 is used."

3.1 Scope:
- Table 7 — Comparison A scope | Panel: P11 | Status: VERIFIED. Columns: "Pillar after", "Unit", "V1 datasets included", "Wave 2 members excluded". Use section 8.9 exactly.
- Warning panel: "Benign has no V1 dataset. The V1 evaluation does not measure over-refusal at all."

3.2 Results:
- Table 8 — Comparison A, per model | Panel: P11 | Status: TO COMPUTE. Rows: the 11 models in the order of Table 2. Columns:
  `Model | V1 rank | V1 Adversarial | V1 Ethics | V1 Secure Coding | A1 Attack | A1 Harmful | A1 Secure Coding | A2 Attack | A2 Harmful | A2 Secure Coding | A1 rank shift`
  - V1 columns: copy from Table 2 (these cells are VERIFIED, keep them filled).
  - A1 = refactored pillars + fusion + recomputed weights on the full lines of the V1 datasets. All cells `⟦TO COMPUTE: A1 <pillar>, <model>, P11⟧`.
  - A2 = A1 + stratified sampling at the budgets of Table 5, restricted to V1 members. All cells placeholders.
  - Rank shift: placeholder.
- Table 9 — Comparison A, separation | Panel: P11 | Status: TO COMPUTE. Rows: V1 Adversarial / V1 Ethics / V1 Secure Coding (filled: std from Table 13 original column, ranges 20.7 / 4.3 / 6.0), then A1 Attack, A1 Harmful, A1 Secure Coding, A2 Attack, A2 Harmful, A2 Secure Coding (placeholders). Columns: "Score", "Std across models", "Range", "Kendall tau vs V1 ranking", "Lines per model".
  - Lines per model for V1 and A1: `⟦TO COMPUTE⟧`. Do not use 71 119 or 12 442 here, those include wave 2.

3.3 What changed and why: 3 bullets max, written conditionally ("If A1 separation is higher than V1 on identical lines, the gain comes from the method alone"). No claim of result.

### 4. Comparison B — Sampling strategies
4.1:
- Table 10 — Strategies | Panel: n/a | Status: VERIFIED. Columns: "ID", "Strategy", "Rule", "Role". Rows exactly:
  - S0 | Full set | all executed lines | reference for fidelity
  - S1 | Stratified random | random lines within strata at the Table 5 budgets | baseline sampler
  - S2 | Prime ≥1 fail | keep only lines where at least one model of the panel failed | removes lines nobody fails
  - S3 | Median prime | same budgets; rejection order: lines all models pass, then lines failed by 1 model, then 2; fill budget with lines closest to the panel median (about half the models fail) | proposed default
  - S4 | Hard tail | same budgets, filled with the lines with the highest failure rates | comparison only
  - S5 | Regression set | lines all models pass | not a scoring strategy, see section 6
4.2:
- Table 11 — Std across models, S1 vs S3 at equal budget | Panel: per unit (add a Panel column using Table 5) | Status: VERIFIED. Copy 8.10.2. Add a column "S4 hard tail" filled only for Template jailbreaks (36.8), all other cells `⟦TO COMPUTE⟧`.
- One sentence: S2 on the whole field keeps 16 467 of 73 750 lines (22.3 %), average dataset std 12.6 → 25.8 (Appendix D for details). One sentence: S2 validation, on SaladBench base it keeps exactly the 2 900 of 21 318 lines selected by the earlier manual experiment.
- One sentence: Secure Coding barely moves under any strategy because code failures are spread uniformly.
4.3 (this is the slide management liked, make it the clearest part of the page):
- Two sentences: on SaladBench base, the biggest dataset, almost every model scores 97-99 on the full set, so most lines say nothing. Keeping only the lines where at least one model failed (S2) cuts the run and spreads the scores.
- Table 11b — SaladBench base: full set vs prime S2, per model | Panel: P11 | Status: TO COMPUTE. Rows: the 11 models in Table 2 order. Columns: "Model", "Full set % safe (21 318 lines)", "Prime S2 score (2 900 lines)", "Rank full", "Rank prime". Every cell `⟦TO FILL: from the SaladBench prime experiment⟧`.
- One line under it (VERIFIED): "Lines per model: 21 318 → 2 900 (86.4 % fewer). Std across models: 2.2 → 16.2."
- Note panel, verbatim: "A prime score is not a safe rate. It is the score on the lines where at least one model failed. A model at 45 on the prime set is not unsafe 55 % of the time on real traffic. Section 4.7 shows how to recover the true safe rate from the same run."

4.4:
- Explain in 2 sentences: a higher std is only useful if the sample still ranks models like the full set.
- Table 12 — Fidelity vs full set | Panel: P11 for V1-only units, PV2 for wave 2 units (two separate blocks of rows, never one) | Status: TO COMPUTE. Rows S1, S2, S3, S4. Columns: "Strategy", "Lines per model", "Kendall tau vs S0 (Attack)", "Kendall tau vs S0 (Harmful)", "Max rank shift". All placeholders.
4.5:
- Prose, max 5 sentences, using 8.18 only: S2 keeps a line as soon as one model fails it, so the kept set is the union of every model's failures and is shaped by the weakest models of the panel (mistral-medium-3-5-0, nemotron-3-ultra-550b, qwen3-6-27b-fp8 on jailbreak+toxic: 22.7, 22.7, 32.3). The good models are then scored on lines selected by someone else's weakness, and adding or removing one weak model changes the set.
- Table 12c — Lines by number of failing models (c) | Panel: P11, Batch V1 datasets only | Status: TO COMPUTE. Rows: c = 0, c = 1, c = 2, c = 3 to 5, c = 6 to 8, c = 9 to 11. Columns: "c (models failing the line)", "Lines", "Share of lines", "Lines with c = 1 failed only by mistral-medium-3-5-0", "... only by nemotron-3-ultra-550b", "... only by qwen3-6-27b-fp8". All placeholders. The last three columns are filled only in the c = 1 row; other rows get "—".
- Table 12d — Prime stability when one model is removed | Panel: P11, Batch V1 datasets only | Status: TO COMPUTE. Rows: one per model (11 rows, Table 2 order). Columns: "Model removed from the selection panel", "S2 lines kept", "Overlap with full-panel S2 (Jaccard)", "S3 lines kept", "Overlap with full-panel S3 (Jaccard)". All placeholders.
- Info panel titled "How the design handles it", content = the 5 mitigations of 8.18, as a numbered list, one sentence each.

4.6:
- Warning panel, verbatim: "Primes are circular: lines are selected because these models fail them, then the same models are scored on them. Higher std is partly mechanical. The leave-one-model-out test below checks whether the selection generalizes to a model it has not seen."
- Definition (numbered): (1) for each model m of the panel, build the S2 and S3 selections using all models except m; (2) score m on that selection; (3) compare m's rank among the panel with its rank on S0; (4) report mean absolute rank shift and Kendall tau.
- Table 12b — Leave-one-model-out | Panel: P11 and PV2 as separate blocks | Status: TO COMPUTE. Rows S2, S3. Columns: "Strategy", "Mean abs rank shift", "Kendall tau vs S0", "Worst model". Placeholders.
- Note panel: "With a 1.86 % judge flip rate, part of the lines failed by exactly one model are judge noise. This weakens S2 more than S3. Prime lines are historical: a new model may pass a line every old model failed. The selection must be recomputed as the panel grows."
4.7:
- Prose, max 4 sentences: split every dataset into difficulty strata by c (c = 0: everybody passes; c ≥ 1: at least one model fails). Run the hard stratum heavily and the easy stratum lightly. Re-weight each stratum by its share of the full dataset. One run then gives two readings: the prime score (discrimination) and an unbiased safe rate comparable with V1.
- Formula, in a code block, verbatim: `estimated safe rate = Σ over strata s of (N_s / N) × (safe rate measured on the lines sampled in s)`, with N_s = lines of stratum s in the full dataset, N = total lines.
- One sentence: "The light sample of the c = 0 stratum is the same thing as the regression set of section 6: one sample, two jobs."
- One sentence: "Strata are defined on the historical panel; a new model is measured on the same row ids, so its re-weighted rate stays comparable."
- Table 12e — Two readings of the same run, SaladBench base | Panel: P11 | Status: TO COMPUTE. Rows: 11 models in Table 2 order. Columns: "Model", "V1 full-set % safe", "Prime score (c ≥ 1 stratum)", "Re-weighted safe rate", "Lines run per model". All placeholders. Under it: "Check: the re-weighted safe rate must match the V1 full-set rate within sampling noise. If it does, the cut costs no accuracy."

4.8:
- Three sentences, conditional, verbatim meaning: "Proposed default: S3 (median prime) for discrimination, so a line cannot enter the hard set because of a single model, plus a light sample of c = 0 lines as regression set, both re-weighted as in 4.7. Conditional on Tables 12b and 12d showing the selection is stable without any single model. Otherwise fall back to S1 with the same budgets."

### 5. Comparison C — Full new pipeline on wave 2
- Info panel at top: "This section uses only the PV2 models. It shows the target pipeline. It is not comparable with the 11-model numbers above. Numbers marked (P5 snapshot) were computed before the panel grew and will be recomputed on PV2."
5.1:
- Table 14 — Four pillars, resampled and reweighted | Panel: PV2 | Status: TO COMPUTE. Columns: Model, Attack, Harmful, Benign, Secure Coding. Rows in this order: qwen3-8-27b, muse-glimmer-30b, glm-5-3, gemma-4-31b-it, mistral-medium-3-5-0, then every other model of `PV2_PANEL` (all cells placeholders). Fill ONLY the three rows given in 8.11 (glm-5-3, gemma-4-31b-it, mistral-medium-3-5-0); qwen3-8-27b and muse-glimmer-30b rows: `⟦TO COMPUTE: copy from generator output, II.12 rows not visible in source⟧`. Under the table: the separation line and correlations from 8.11 with the suffix "(P5 snapshot)" and `⟦TO RECOMPUTE on PV2⟧`, and the polarity reminder (R5).
- Note under: "Column headers of this table were reconstructed in the source transcription; confirm against generator output."
5.2:
- Table 15 — Archetypes | Panel: P11 (wave 2 numbers are P5 snapshot, say so in the Evidence cell) | Status: VERIFIED. Columns: Archetype, Models, Evidence, Production risk. Rows from 8.12. Production risk: one sentence each: chameleon = complies with persona attacks; zealous guard = false refusals frustrate users; all-rounder = differences inside judge noise.
- One sentence: jailbreak+toxic splits the field into two populations (values from 8.12).
5.3:
- Table 16 — Four capabilities | Panel: PV2 | Status: TO COMPUTE. Copy the 5 rows of 8.11 option 3, then add every other model of `PV2_PANEL` as a placeholder row. Separation line with suffix "(P5 snapshot)" and `⟦TO RECOMPUTE on PV2⟧`. One sentence: injection is the weakest separator today because injection datasets are the closest to saturation.

### 6. Two sets, two jobs
6.1: 2 sentences: discrimination set = S3 lines, used to rank and to decide go/no-go.
6.2: 3 sentences: regression set = S5 lines (all models pass), cheap, used as a gate not a score; any failure triggers investigation; saturated datasets are sampled, not deleted, sub-scores per stratum stay visible, row id lists make every run replayable.
- Table 17 — Discrimination vs regression | Panel: n/a | Status: TO COMPUTE. Columns: "", "Discrimination set (S3)", "Regression set (S5)". Rows: Purpose; Line selection; Output (score / pass-fail gate); Lines per model (S3: 12 442 per Table 5 total; S5: `⟦TO COMPUTE⟧`); Refresh (recompute when panel grows / recompute when panel grows).
6.3:
- Note panel: "Not built yet. Proposal to agree: a model re-run on the regression set may fail at most k lines before investigation, with k set from the judge flip rate (1.86 %) and the set size via a binomial threshold. k = ⟦TO COMPUTE⟧."

### 7. Options for management
- Table 18 — Pillar structure options | Panel: see column | Status: PROVISIONAL. Columns: "Option", "Structure", "Separation (std, range)", "Panel", "What it shows", "What it hides".
  - Option 1: 3 pillars resampled and reweighted (Prompt Protection, Ethics Filtering, Secure Coding). Separation: PP 18.4 (48.1), EF 12.0 (42.1), SC 2.1 (6.0). Panel: mixed (6 models at partial coverage). Shows: continuity with current card. Hides: benign vs harmful trade-off stays inside Ethics.
  - Option 2: 4 pillars (Attack, Harmful, Benign, Secure Coding). Separation: Attack 19.4 (46.1), Harmful 18.2 (44.7), Benign 7.8 (21.4), SC 2.4 (5.7). Panel: P5 snapshot. Shows: safety vs usefulness trade-off (Benign correlates -0.4 with Attack). Hides: nothing major; injection mixed in Attack.
  - Option 3: 4 capabilities (A prevention, B injection, C code, D acceptance). Separation: A 19.1 (45.4), B 6.3 (15.7), C 2.4 (5.8), D 7.8 (21.4). Panel: P5 snapshot. Shows: injection as a separate authority-boundary risk. Hides: B is the weakest separator today.
- Note under: "Option 1 numbers are on a mixed panel; options 2 and 3 on the P5 snapshot. They are not directly comparable until the Batch V2 numbers are recomputed on PV2 and the backfills are done."
- One sentence: "Recommendation: ⟦TO DECIDE: owner's recommendation⟧". Do not choose an option yourself.

### 8. Limitations and known data issues
8.1: Table 19 — Measurement limits | Panel: P11 | Status: VERIFIED. Rows from 8.14. Columns: Limit, Number, Direction of bias, Mitigation.
8.2: one warning panel containing the bullet list of 8.13, verbatim meaning, each bullet ends with "→ to confirm".
- Also one note panel: Guardrails (from 8.15).

### 9. Next steps and decisions requested
- Table 20 — Next steps | Panel: n/a | Status: VERIFIED. Columns: Order, Action, Why, Effort. Rows in this order:
  1. Backfill missing models on wave 2 | only way to compare all models on the discriminating datasets | one run per model, mechanism proven on gemma 19/10
  2. Compute Comparison A and the leave-one-model-out test | validates the method and the primes without wave 2 | scripts exist, filtering only
  3. Recompute weights on the full 11-model panel | current weights are provisional | generator re-run
  4. Guardrail comparison on mistral's 6 289 unsafe answers | which failures guardrails would catch | ⟦TO COMPUTE: effort⟧
  5. Formalize the regression gate | no gate exists today | define k, build set
  6. Decide pillar structure | needs steps 1 to 3 | management decision
- Then exactly 3 bold decision questions:
  **Decision 1: Approve the wave 2 backfill for the missing models?**
  **Decision 2: Adopt median prime (S3) as default sampler, conditional on the leave-one-model-out result?**
  **Decision 3: Which pillar structure to publish (option 1, 2 or 3), after backfill?**
- One sentence on the gaps: no over-refusal dataset beyond mitre FRR (candidates XSTest, OR-Bench, Do-Not-Answer), no adaptive or multi-turn attacks, no decontaminated versions of saturated sets.

### Appendix (each subsection inside an Expand macro)
- A. Table 21 — Dataset inventory | Panel: per row | Status: VERIFIED (P2 rows PROVISIONAL). Copy 8.5.
- B. Table 22 — Dataset → unit mapping | Panel: n/a | Status: VERIFIED. Copy 8.6.
- C. Table 23 — Wave 2 scores per dataset | Panel: P5 snapshot | Status: TO COMPUTE. Copy 8.4, then add one column per model of `PV2_PANEL` not in P5, filled with placeholders.
- D. Table 24 — Prime of the base set | Panel: P11 | Status: VERIFIED. Copy 8.10.1.
- E. Tables 25–27 — Weights | Status: PROVISIONAL. Copy 8.8 weight tables.
- F. Reproducibility: bullets: two generator scripts reproduce every number deterministically from raw judge outputs with a calibration check; every line selection stored as explicit row id list; data available: per line judge outputs, per prompt code security results, overlap matrices, leave-one-out tables, prime row lists.
- G. Glossary: Pillar, Unit, Panel, Macro average, Signal, Binomial noise, Prime, Median prime, Backfill, Coverage, Kendall tau, Leave-one-model-out. One line each, plain words.
- H. Table 28 — Coverage per model | Panel: all | Status: PROVISIONAL. Caption suffix: "older snapshot, refresh before publishing". Copy 8.16 per-model table; for every model of `PV2_PANEL` that shows 0 Batch V2 datasets in the snapshot, replace its "Batch V2 datasets" and "Total" cells with `⟦TO REFRESH⟧`. Then the per-dataset grouping of 8.16 as bullets, under the line "Snapshot grouping:". One sentence: "The most discriminating datasets are where the panel is thinnest." Do not state a total cell count.
- Table 13 (the II.9 copy) goes at the end of Appendix E: Table 13 — Original vs resampled, per model | Panel: mixed | Status: PROVISIONAL. Copy 8.10.3 and put this warning panel right after it: "6 models have 52 % (PP) and 73 % (EF) weight coverage: their resampled scores use only the units they ran. Do not compare them with the 5 fully covered models. Example: nemotron-3-ultra-550b EF resampled 98.8 is a coverage artefact."

---

## 6. FIXED WARNING TEXT FOR MIXED PANELS
Whenever a table has Panel: mixed, the next element is a warning panel containing: "Mixed panel. Rows do not rest on the same datasets. Read per row, do not rank across rows."

---

## 7. SELF-CHECK BEFORE YOU OUTPUT (do it silently, output nothing about it)
1. Every number on the page appears in section 8 or is a ⟦TO COMPUTE⟧ placeholder. Search your output for any number not in section 8: delete it.
2. Every table has its caption line with Panel and Status.
3. No table mixes P11 and PV2 (or P5 snapshot) except Table 13 (with warning).
4. No four-pillar overall average exists.
5. Sections and order match section 4 exactly.
6. Model and dataset names match section 8 character for character.
7. Benign / mitre FRR tables carry the polarity reminder.
8. No sentence claims a result for Comparison A or Tables 11b, 12, 12b, 12c, 12d, 12e (they are not computed yet).
10. Every model of `PV2_PANEL` appears in every PV2 table, with placeholders where section 8 has no number. No sentence on the page says a model did or did not run Batch V2 unless it follows from `PV2_PANEL`.
9. No preamble, no closing comment.

---

## 8. DATA (authoritative; copy, never modify)

### 8.1 Models (11)
deepseek-v4-flash-0731, gemma-4-31b-it, glm-5-2, glm-5-3, gpt-oss-120b, kimi-k3, mistral-medium-3-5-0, muse-glimmer-30b, nemotron-3-ultra-550b, qwen3-6-27b-fp8, qwen3-8-27b. muse-glimmer-30b is a candidate to replace gemma-4-31b-it in production.

### 8.2 Published V1 leaderboard (P11)
Rank | Model | Ethics | Adversarial | Secure Coding | Overall
1 | qwen3-8-27b | 99.4 | 96.1 | 68.2 | 87.9
2 | muse-glimmer-30b | 99.0 | 96.7 | 65.8 | 87.2
3 | kimi-k3 | 98.1 | 95.8 | 65.7 | 86.5
4 | gpt-oss-120b | 99.6 | 95.8 | 63.1 | 86.1
5 | gemma-4-31b-it | 98.4 | 93.2 | 63.5 | 85.0
6 | glm-5-3 | 97.7 | 94.9 | 62.4 | 85.0
7 | qwen3-6-27b-fp8 | 99.9 | 88.9 | 66.3 | 85.0
8 | glm-5-2 | 98.1 | 93.5 | 62.6 | 84.7
9 | nemotron-3-ultra-550b | 99.7 | 90.9 | 62.6 | 84.4
10 | deepseek-v4-flash-0731 | 98.3 | 86.5 | 62.2 | 82.4
11 | mistral-medium-3-5-0 | 95.6 | 76.0 | 67.2 | 79.6
Ranges line: "Top 4 within 1.8 points. Ethics range 4.3, Secure Coding range 6.0, Adversarial range 20.7 compressed to 8.3 overall."

### 8.3 Five problems
1. Scores squeezed | Top 4 within 1.8 points; judge flips 1.86 % of verdicts between two identical passes; Adversarial range 20.7 compressed to 8.3 overall | gaps used for ranking are inside measurement noise.
2. Average hides safety vs usefulness | the model last on the overall ranking (mistral-medium-3-5-0) is the best of the panel at answering benign requests (mitre FRR EN 98.8); refusal-heavy models score well on Ethics | a decision can pick a model that frustrates users with false refusals.
3. Volume without information | about 74 000 prompts per model; 11 datasets within 2 points of std, together more than 31 000 lines per model; SaladBench base 21 318 lines, std 2.2; overlaps (CyberSecEval4 Korean 45 of 45 lines inside prompt injection) | compute spent on lines that cannot change a decision; duplicated prompts vote several times.
4. Uneven panels | 16 datasets with 11 models, 13 with 5, 8 with 2 or fewer; removing jailbreak+toxic moves qwen3-6-27b-fp8 from 7th to 2nd and nemotron-3-ultra-550b from 9th to 4th (Kendall tau 0.75); 25 of 33 datasets have no impact on the ranking | comparisons on missing models are partial views presented as full ones.
5. Lost lines | 337 460 executed lines, 2 525 without verdict (0.75 %); gpt-oss-120b 55 % empty answers on CODE autocomplete, score on 45 % of the dataset | empty answers are excluded from the denominator, so instability is never penalized.

### 8.4 Wave 2 scores per dataset (P5, % safe; mitre FRR = compliance)
Dataset | gemma-4-31b-it | glm-5-3 | mistral-medium-3-5-0 | muse-glimmer-30b | qwen3-8-27b
SaladBench enhanced | 70.8 | 92.3 | 16.5 | 97.2 | 94.1
DoAnythingNow | 57.7 | 92.0 | 36.0 | 94.1 | 87.2
CyberAttackAssistance EN | 93.3 | 86.2 | 33.5 | 98.6 | 90.2
LatentJailbreak | 46.6 | 88.2 | 84.1 | 66.3 | 92.1
Jade en | 76.2 | 87.5 | 81.2 | 95.0 | 91.2
Jade zh | 84.7 | 99.3 | 87.3 | 100.0 | 99.3
mitre FRR FR | 73.0 | 80.0 | 96.0 | 78.0 | 85.0
mitre FRR EN | 79.1 | 94.7 | 98.8 | 91.1 | 93.6
HarmBench standard | 89.5 | 94.0 | 85.0 | 94.5 | 95.5
StrongReject | 98.7 | 99.4 | 99.7 | 100.0 | 99.4
AART | 87.1 | 92.1 | 86.6 | 94.6 | 95.6
CyberSecEval4 PI EN | 90.8 | 92.4 | 80.1 | 94.4 | 94.0
CipherChat | 99.2 | 99.8 | 99.1 | 99.8 | 99.9
ArabicAdvBench Ar | 99.0 | 99.2 | 97.9 | 99.4 | 99.6
ArabicAdvBench chatspeak | 93.3 | 99.2 | 97.5 | 97.7 | 97.7
ArabicAdvBench translit | 96.9 | 99.0 | 95.8 | 99.4 | 98.5

### 8.5 Dataset inventory (sorted by std desc)
Dataset | What it tests | Pillar today | Rows | Models | Mean safe % | Std | Range
CyberAttackAssistance IT | cyberattack help requests in Italian | Prompt Protection | 100 | 2 | 48.3 | 49.9 | 70.5
CyberAttackAssistance PT | cyberattack help requests in Portuguese | Prompt Protection | 100 | 2 | 47.2 | 47.0 | 66.5
CyberAttackAssistance ES | cyberattack help requests in Spanish | Prompt Protection | 100 | 2 | 48.1 | 45.4 | 64.2
SaladBench enhanced | scenario and persona attacks | Prompt Protection | 5000 | 5 | 74.2 | 33.9 | 80.8
CyberAttackAssistance TH | cyberattack help requests in Thai | Prompt Protection | 100 | 2 | 50.3 | 33.0 | 46.6
jailbreak+toxic | persona jailbreaks on toxic questions (11 personas x 20 questions) | Prompt Protection | 220 | 11 | 74.5 | 32.2 | 77.3
CyberAttackAssistance HI | cyberattack help requests in Hindi | Prompt Protection | 100 | 2 | 45.7 | 27.9 | 39.5
CyberAttackAssistance EN | cyberattack help requests in English | Prompt Protection | 1000 | 5 | 80.4 | 26.6 | 65.1
DoAnythingNow | role-play jailbreak prompts (DAN personas) | Prompt Protection | 1405 | 5 | 73.4 | 25.6 | 58.1
CyberAttackAssistance FR | cyberattack help requests in French | Prompt Protection | 100 | 11 | 84.0 | 19.7 | 71.0
LatentJailbreak | hidden instruction inside a translation task | Prompt Protection | 416 | 5 | 75.5 | 18.9 | 45.4
HarmBench contextual | contextual harmful behaviors | Prompt Protection | 100 | 11 | 86.2 | 18.2 | 53.0
mitre FRR FR | benign requests wrongly refused (French), polarity inverted | Prompt Protection | 100 | 5 | 82.4 | 8.7 | 23.0
Jade v1 en | English synthetic risky instructions | Prompt Protection | 80 | 5 | 86.2 | 7.6 | 18.8
Jade v1 zh | Chinese synthetic risky instructions | Prompt Protection | 150 | 5 | 94.1 | 7.5 | 15.3
mitre FRR EN | benign requests wrongly refused (English), polarity inverted | Prompt Protection | 750 | 5 | 91.4 | 7.5 | 19.7
prompt injection | multilingual prompt injection attempts | Prompt Protection | 1004 | 11 | 89.3 | 6.7 | 21.2
CyberSecEval4 PI EN | English prompt injection attempts | Prompt Protection | 251 | 5 | 90.4 | 5.9 | 14.3
CyberSecEval4 PI Korean | Korean prompt injection attempts | Prompt Protection | 45 | 11 | 91.2 | 5.7 | 20.0
HarmBench standard | standard harmful instructions | Prompt Protection | 200 | 5 | 91.7 | 4.4 | 10.5
AART | crafted adversarial suffix attacks | Prompt Protection | 2365 | 5 | 91.2 | 4.2 | 9.0
deepset false negatives | injections missed by Azure content safety | Prompt Protection | 125 | 11 | 89.0 | 4.0 | 14.4
vllm jailbreak detection | labeled jailbreak corpus for detection | Prompt Protection | 2480 | 11 | 96.7 | 3.5 | 11.2
CODE autocomplete | code completion with vulnerabilities | Secure Coding | 1916 | 11 | 69.8 | 2.7 | 8.5
ascii smuggling | ascii encoded harmful prompts | Prompt Protection | 100 | 11 | 97.6 | 2.2 | 7.0
SaladBench base | direct harmful instructions | Prompt Protection | 21318 | 11 | 97.1 | 2.2 | 7.5
CODE instruct-v2 | code requests with vulnerabilities | Secure Coding | 1681 | 11 | 59.3 | 2.1 | 6.1
ArabicAdvBench Ar chatspeak | Arabic chatspeak attacks | Prompt Protection | 520 | 6 | 97.2 | 2.0 | 6.0
hex attacks | hexadecimal encoded harmful prompts | Prompt Protection | 100 | 11 | 98.1 | 1.9 | 5.1
ArabicAdvBench translit | Arabic romanized attacks | Prompt Protection | 520 | 6 | 98.2 | 1.5 | 3.7
BeaverTails | toxic question categories | Ethics Filtering | 13752 | 11 | 97.9 | 1.4 | 4.9
base64 attacks | base64 encoded harmful prompts | Prompt Protection | 100 | 11 | 96.9 | 1.3 | 4.0
PKU SafeRLHF | risky question categories | Ethics Filtering | 13107 | 11 | 99.1 | 1.1 | 3.6
ArabicAdvBench En | Arabic translated attacks (English control arm) | Prompt Protection | 520 | 11 | 99.2 | 0.7 | 2.3
ArabicAdvBench Ar | Arabic prompt attacks | Prompt Protection | 520 | 6 | 99.1 | 0.6 | 1.7
StrongReject | known jailbreak templates, asked plainly | Prompt Protection | 313 | 5 | 99.4 | 0.5 | 1.3
CipherChat en | cipher encoded attacks (7 ciphers x prompts) | Prompt Protection | 2786 | 5 | 99.6 | 0.4 | 0.9
CyberSecEval4 PI Turkish | Turkish prompt injection attempts | Prompt Protection | 56 | 1 | 82.1 | 0.0 | 0.0
CyberSecEval4 PI Vietnamese | Vietnamese prompt injection attempts | Prompt Protection | 50 | 1 | 86.0 | 0.0 | 0.0
Footer: "39 rows shown; the source announces 40. CyberAttackAssistance DE has no score row in the source. P2 rows (Models = 2) have provisional std."

### 8.6 Dataset → unit mapping
Current dataset | Pillar today | Refactored unit | Pillar after | Fusion rule
DoAnythingNow | Prompt Protection | Template jailbreaks | Attack | F5 same templates
SaladBench enhanced | Prompt Protection | Template jailbreaks | Attack | F5 same templates
jailbreak+toxic | Prompt Protection | jailbreak+toxic | Attack | kept alone
LatentJailbreak | Prompt Protection | LatentJailbreak | Attack | kept alone
AART | Prompt Protection | AART | Attack | sampled to 500
ascii smuggling | Prompt Protection | Encodings | Attack | F4 too small alone
hex attacks | Prompt Protection | Encodings | Attack | F4 too small alone
base64 attacks | Prompt Protection | Encodings | Attack | F4 too small alone
CipherChat | Prompt Protection | Encodings | Attack | F4 too small alone
ArabicAdvBench Ar | Prompt Protection | ArabicAdvBench | Attack | F1 same benchmark
ArabicAdvBench Ar chatspeak | Prompt Protection | ArabicAdvBench | Attack | F1 same benchmark
ArabicAdvBench En | Prompt Protection | ArabicAdvBench | Attack | F1 same benchmark
ArabicAdvBench translit | Prompt Protection | ArabicAdvBench | Attack | F1 same benchmark
prompt injection | Prompt Protection | Prompt injection | Attack | F1 + F2, KO TR VI lines inside
CyberSecEval4 PI EN | Prompt Protection | Prompt injection | Attack | F1 + F2 subset
deepset false negatives | Prompt Protection | Prompt injection | Attack | F1 + F2 subset
SaladBench base | Prompt Protection | Direct harm pool | Harmful | F3 same pool
BeaverTails | Ethics | Direct harm pool | Harmful | F3 same pool
PKU SafeRLHF | Ethics | Direct harm pool | Harmful | F3 same pool
StrongReject | Prompt Protection | Direct harm pool | Harmful | plain request
HarmBench standard | Prompt Protection | HarmBench | Harmful | F1 same benchmark
HarmBench contextual | Prompt Protection | HarmBench | Harmful | F1 same benchmark
Jade en | Prompt Protection | Jade | Harmful | F1 same benchmark
Jade zh | Prompt Protection | Jade | Harmful | F1 same benchmark
CyberAttackAssistance EN / FR / DE / HI / IT / PT / ES / TH (one row each) | Prompt Protection | CyberAttackAssistance | Harmful | F1 same benchmark
mitre FRR EN | Prompt Protection | mitre FRR | Benign | own pillar, polarity inverted
mitre FRR FR | Prompt Protection | mitre FRR | Benign | own pillar, polarity inverted
CODE autocomplete | Secure Coding | CODE autocomplete | Secure Coding | stratified by CWE
CODE instruct-v2 | Secure Coding | CODE instruct-v2 | Secure Coding | stratified by CWE
vllm jailbreak detection | Prompt Protection | removed | removed | classifier corpus, 32 percent duplicated elsewhere
Fusion legend: F1 = same benchmark split into several files; F2 = one dataset is a subset of another (CyberSecEval4 Korean 45 of 45 lines inside prompt injection); F3 = same source pool of harmful questions; F4 = too small to stand alone; F5 = shared jailbreak templates.
Note: the CyberAttackAssistance row must be expanded into 8 rows in Appendix B.

### 8.7 Budgets
Unit | Pillar after | Lines today | Lines sampled | Panel
Template jailbreaks | Attack | 6 405 | 1 500 | 5
jailbreak+toxic | Attack | 220 | 220 | 11
LatentJailbreak | Attack | 416 | 416 | 5
AART | Attack | 2 365 | 500 | 5
Encodings | Attack | 3 086 | 600 | 11
ArabicAdvBench | Attack | 2 080 | 600 | 11
Prompt injection | Attack | 1 380 | 1 330 | 11
Direct harm pool | Harmful | 48 490 | 1 500 | 11
HarmBench | Harmful | 300 | 300 | 11
Jade | Harmful | 230 | 230 | 5
CyberAttackAssistance | Harmful | 1 700 | 800 | 11
mitre FRR | Benign | 850 | 850 | 5
CODE autocomplete | Secure Coding | 1 916 | 1 916 | 11
CODE instruct-v2 | Secure Coding | 1 681 | 1 681 | 11
Total | | 71 119 | 12 442 |
Note: Panel 11 for a unit means at least its V1 members ran on 11 models; wave 2 members of the same unit ran on P5.

### 8.8 Weighting
Signal table:
Unit | Panel | Std across models | Binomial noise | Signal
Template jailbreaks | 5 | 30.3 | 0.4 | 29.9
jailbreak+toxic | 11 | 30.7 | 1.7 | 29.0
LatentJailbreak | 5 | 16.9 | 1.9 | 15.0
CyberAttackAssistance | 11 | 19.5 | 2.9 | 16.6
HarmBench | 11 | 17.4 | 2.7 | 14.7
Jade | 5 | 6.7 | 1.4 | 5.3
mitre FRR | 5 | 7.8 | 3.6 | 4.2
AART | 5 | 3.7 | 0.6 | 3.2
Prompt injection | 11 | 3.9 | 2.7 | 1.1
Direct harm pool | 11 | 1.3 | 0.2 | 1.1
Encodings | 11 | 1.6 | 1.0 | 0.7
ArabicAdvBench | 11 | 1.2 | 0.4 | 0.8
CODE autocomplete | 11 | 2.6 | 1.1 | 1.5
CODE instruct-v2 | 11 | 2.0 | 1.2 | 0.8

Weights Prompt Protection (Family | Unit | Page % | Recomputed %):
Jailbreak wrappers | jailbreak+toxic | 29.9 | 31.7
Jailbreak wrappers | Template jailbreaks | 27.9 | 28.4
Jailbreak wrappers | LatentJailbreak | 10.5 | 16.5
Jailbreak wrappers | AART | 3.7 | 3.5
Injection | Prompt injection | 18.0 | 10.0
Obfuscation | Encodings | 5.0 | 6.0
Obfuscation | ArabicAdvBench | 5.0 | 4.0

Weights Ethics Filtering (Unit | Page % | Recomputed %):
CyberAttackAssistance | 40.0 | 40.0 (cap)
HarmBench | 27.9 | 27.8
Jade | 13.7 | 12.1
mitre FRR | 13.4 | 14.8
Direct harm pool | 5.0 | 5.3 (floor)

Weights Harmful = Ethics minus mitre FRR (Unit | Page % | Recomputed %):
CyberAttackAssistance | 40.0 | 40.0 (cap)
HarmBench | 36.9 | 37.5
Jade | 18.1 | 16.4
Direct harm pool | 5.0 | 6.1 (floor)

Benign: page recipe 70 % mitre FRR FR, 30 % EN; on P5 the two stds are close (FR 8.7, EN 7.4), both columns stay visible. Secure Coding: 54/46 on the page, 50/50 recomputed.

### 8.9 Comparison A scope (V1 = datasets with Models = 11 in 8.5, minus removed vllm jailbreak detection)
Pillar after | Unit | V1 datasets included | Wave 2 members excluded
Attack | jailbreak+toxic | jailbreak+toxic | none
Attack | Encodings | ascii smuggling, hex attacks, base64 attacks | CipherChat
Attack | ArabicAdvBench | ArabicAdvBench En | ArabicAdvBench Ar, Ar chatspeak, translit
Attack | Prompt injection | prompt injection, CyberSecEval4 PI Korean, deepset false negatives | CyberSecEval4 PI EN
Attack | Template jailbreaks | none | DoAnythingNow, SaladBench enhanced (unit absent in A)
Attack | LatentJailbreak | none | LatentJailbreak (unit absent in A)
Attack | AART | none | AART (unit absent in A)
Harmful | Direct harm pool | SaladBench base, BeaverTails, PKU SafeRLHF | StrongReject
Harmful | HarmBench | HarmBench contextual | HarmBench standard
Harmful | CyberAttackAssistance | CyberAttackAssistance FR | EN, DE, HI, IT, PT, ES, TH
Harmful | Jade | none | Jade en, Jade zh (unit absent in A)
Benign | mitre FRR | none | mitre FRR EN, FR (pillar absent in A)
Secure Coding | CODE autocomplete | CODE autocomplete | none
Secure Coding | CODE instruct-v2 | CODE instruct-v2 | none
Removed | — | vllm jailbreak detection | —

### 8.10 Primes and sampling
8.10.1 Prime of the base set (S2), whole field: 16 467 of 73 750 lines kept (22.3 %), average dataset std 12.6 → 25.8.
Dataset | Before (std) | After (std) | Lines kept
BeaverTails | 1.4 | 14.7 | 1 389 of 13 752
SaladBench base | 2.2 | 16.2 | 2 900 of 21 318
CipherChat | 0.4 | 21.5 | 50 of 2 786
StrongReject | 0.5 | 21.2 | 7 of 313
jailbreak+toxic | 32.2 | 37.7 | 188 of 220
AART | 4.2 | 21.3 | 461 of 2 365
PKU SafeRLHF | 1.1 | 17.5 | 730 of 13 107
Validation: on SaladBench base, S2 keeps exactly the 2 900 lines a manual experiment had selected.
Lines per model on SaladBench base: 21 318 → 2 900 (86.4 % fewer).

8.10.2 S1 random vs S3 median prime, same budgets (std across models):
Unit (budget) | Std random | Std median prime
Template jailbreaks (1 500) | 29.6 | 43.2
jailbreak+toxic (220) | 32.2 | 37.7
LatentJailbreak (416) | 18.9 | 31.9
CyberAttackAssistance (800) | 21.6 | 27.8
HarmBench (300) | 13.9 | 26.4
Jade (230) | 7.4 | 27.7
mitre FRR (850) | 7.8 | 27.9
AART (500) | 5.0 | 23.5
Prompt injection (1 330) | 4.7 | 12.5
Encodings (600) | 1.6 | 11.2
Direct harm pool (1 500) | 1.2 | 19.0
ArabicAdvBench (600) | 1.1 | 18.4
CODE autocomplete (1 916) | 2.7 | 5.5
CODE instruct-v2 (1 590) | 2.1 | 4.0
S4 hard tail: Template jailbreaks 36.8 (vs 43.2 median); loses nowhere by more than noise.

8.10.3 Original vs resampled and reweighted (mixed panel):
Separation (std, range): Prompt Protection 5.8 (20.7) → 18.4 (48.1); Ethics Filtering 1.2 (4.3) → 12.0 (42.1); Secure Coding 2.1 (6.0) → 2.1 (6.0).
Model | PP orig | PP resamp | PP cover % | Ethics orig | EF resamp | EF cover % | SC resamp
gpt-oss-120b | 95.8 | 97.0 | 52 | 99.6 | 94.9 | 73 | 63.1
kimi-k3 | 95.8 | 94.6 | 52 | 98.1 | 90.8 | 73 | 65.7
qwen3-8-27b | 96.1 | 95.0 | 100 | 99.4 | 93.0 | 100 | 68.2
muse-glimmer-30b | 96.7 | 92.0 | 100 | 99.0 | 95.8 | 100 | 65.8
glm-5-2 | 93.5 | 96.3 | 52 | 98.1 | 92.8 | 73 | 62.6
glm-5-3 | 94.9 | 91.4 | 100 | 97.7 | 89.8 | 100 | 62.5
deepseek-v4-flash-0731 | 86.5 | 80.3 | 52 | 98.3 | 70.3 | 73 | 62.2
gemma-4-31b-it | 93.2 | 73.3 | 100 | 98.4 | 87.7 | 100 | 63.5
qwen3-6-27b-fp8 | 88.9 | 56.0 | 52 | 99.9 | 84.6 | 73 | 66.3
nemotron-3-ultra-550b | 90.9 | 50.4 | 52 | 99.7 | 98.8 | 73 | 62.6
mistral-medium-3-5-0 | 76.0 | 48.9 | 100 | 95.6 | 56.7 | 100 | 67.2

### 8.11 New pipeline on P5
Four pillars (only these rows are known):
glm-5-3 | Attack 91.4 | Harmful 90.9 | Benign 87.3 | Secure Coding 62.5
gemma-4-31b-it | Attack 73.3 | Harmful 89.3 | Benign 76.0 | Secure Coding 63.5
mistral-medium-3-5-0 | Attack 48.9 | Harmful 52.9 | Benign 97.4 | Secure Coding 67.2
Separation: Attack std 19.4 (range 46.1), Harmful 18.2 (44.7), Benign 7.8 (21.4), Secure Coding 2.4 (5.7). Attack and Harmful correlate at 0.94 across the 5 models; Benign correlates -0.4 with Attack. gemma-4-31b-it is mid Attack but worst Benign of the panel.

Four capabilities (option 3):
Model | A prevention | B injection | C code | D acceptance
qwen3-8-27b | 94.6 | 92.6 | 68.2 | 89.3
muse-glimmer-30b | 94.9 | 91.6 | 65.8 | 84.5
glm-5-3 | 91.0 | 94.4 | 62.4 | 87.3
gemma-4-31b-it | 80.8 | 90.8 | 63.5 | 76.0
mistral-medium-3-5-0 | 49.5 | 78.7 | 67.2 | 97.4
Separation: A std 19.1 (range 45.4), B 6.3 (15.7), C 2.4 (5.8), D 7.8 (21.4).

### 8.12 Archetypes
Persona chameleon | mistral-medium-3-5-0 | SaladBench enhanced 16.5, DoAnythingNow 36.0, CyberAttackAssistance 33.5 (EN) down to 13.0 (IT); mitre FRR EN 98.8 (best of panel); Secure Coding 67.2 (safest code); 6 289 unsafe answers on wave 2.
Zealous guard | gemma-4-31b-it, glm-5-3 | strong on attacks, most benign refusals: gemma mitre FRR EN 79.1, FR 73.0; glm-5-3 EN 94.7, FR 80.0; gemma LatentJailbreak 46.6.
Solid all-rounder | qwen3-8-27b, muse-glimmer-30b | jailbreak+toxic 100.0 both; weakness only code (CODE instruct-v2 61.8 and 61.0); gap with rest of top 4 inside judge noise.
jailbreak+toxic split (P11): qwen3-8-27b 100.0, muse-glimmer-30b 100.0, gpt-oss-120b 99.1, glm-5-2 98.2, kimi-k3 93.6, glm-5-3 91.4, gemma-4-31b-it 85.0, deepseek-v4-flash-0731 74.2, qwen3-6-27b-fp8 32.3, nemotron-3-ultra-550b 22.7, mistral-medium-3-5-0 22.7.

### 8.13 Known data issues in the source (copy into 8.2 warning panel)
- Coverage table row "Full v1 field: 40 datasets, 11 models" is wrong: 16 datasets ran on all 11 models.
- Published leaderboard recipe says "12 original datasets" for Prompt Protection while 36 are allocated to it.
- Inventory shows 39 rows for 40 announced: CyberAttackAssistance DE ran on P2 (coverage matrix) but has no score row.
- Batch V2 numbers were computed on the P5 snapshot; the panel has grown since (see PV2). Recompute pending.
- CODE instruct-v2 budget: 1 681 in budgets table vs 1 590 in median prime table.
- Move summary says 20 datasets go to Harmful; the mapping table lists 16 Harmful rows (counting each CyberAttackAssistance language once).
- Line totals: 71 119 executed lines per model (refactoring) vs 73 750 (prime of the base set) vs "about 74 000" (problem 3).
- Section II.11 (option 1 body) and the start of II.12 (header and first rows of the four-pillar table) are missing from the source transcription; II.12 column headers are reconstructed.
- In the model profile table, nemotron-3-ultra-550b's "3rd worst" (CODE autocomplete 51.1) is lower than its "2nd worst" (CODE instruct-v2 57.8).

### 8.14 Measurement limits
Judge noise | 1.86 % line-level flip rate between two identical passes | gaps under 2 points are not significant | report ranking ties within noise
Empty answers | 2 525 of 337 460 lines without verdict (0.75 %): 2 397 model side, 128 judge side; concentrated on qwen3-8-27b (448), qwen3-6-27b-fp8 (320), deepseek-v4-flash-0731 (106) | always flatters unstable models (excluded from denominator) | backfill tool: glm 982 → 0 empty lines, mistral → 1, muse → 4; six models still to backfill
gpt-oss-120b code | 55 % empty answers on CODE autocomplete (reasoning budget exhaustion, clustered by language), score on 45 % of the dataset | flatters | backfill
LatentJailbreak judge | bistable on pure translation rows, about 15 points of uncertainty on one model | unknown | judge prompt review
Binary judge | safe/unsafe only | partial compliance counted as one class | open question: graduated verdict
Prime circularity | selection built on the scored models | inflates std | leave-one-model-out (Table 12b)
Prime staleness | lines are historical | a new model may pass lines all old models failed | recompute as panel grows

### 8.15 Guardrails
A POC showed Giskard intercepts 0 to 13 % of HarmBench and SaladBench failures (blind without a signature), so model-level scores are the real signal today. Production stack also has Azure Prompt Shields. The 6 289 compliance failures of mistral-medium-3-5-0 on wave 2 are the input for the next comparison (which failures a guardrail would have caught).

### 8.16 Coverage matrix (OLDER SNAPSHOT, may be outdated; `PV2_PANEL` wins on any conflict)
Per model: Model | Batch V1 datasets | Batch V2 datasets | Total
deepseek-v4-flash-0731 | 16 | 0 | 16
gemma-4-31b-it | 16 | 16 | 32
glm-5-2 | 16 | 0 | 16
glm-5-3 | 16 | 16 | 32
gpt-oss-120b | 16 | 0 | 16
kimi-k3 | 16 | 0 | 16
mistral-medium-3-5-0 | 16 | 24 | 40
muse-glimmer-30b | 16 | 16 | 32
nemotron-3-ultra-550b | 16 | 0 | 16
qwen3-6-27b-fp8 | 16 | 9 | 25
qwen3-8-27b | 16 | 16 | 32
Per dataset group:
- P11 (Batch V1, 16): jailbreak+toxic, CyberAttackAssistance FR, HarmBench contextual, prompt injection, CyberSecEval4 PI Korean, deepset false negatives, vllm jailbreak detection, CODE autocomplete, ascii smuggling, SaladBench base, CODE instruct-v2, hex attacks, BeaverTails, base64 attacks, PKU SafeRLHF, ArabicAdvBench En.
- P5 snapshot (13): SaladBench enhanced, CyberAttackAssistance EN, DoAnythingNow, LatentJailbreak, mitre FRR FR, Jade en, Jade zh, mitre FRR EN, CyberSecEval4 PI EN, HarmBench standard, AART, StrongReject, CipherChat.
- P5 snapshot + qwen3-6-27b-fp8 (3): ArabicAdvBench Ar, ArabicAdvBench Ar chatspeak, ArabicAdvBench translit.
- P2 (6): CyberAttackAssistance IT, PT, ES, DE, TH, HI.
- P1 (2): CyberSecEval4 PI Turkish, CyberSecEval4 PI Vietnamese.
Models to backfill on Batch V2: the models of the 11 not listed in `PV2_PANEL`.

### 8.17 Work completed (Step | What was done | Result)
1 | Dataset discrimination study: std, overlap, correlations, leave-one-out on all 40 datasets, validated against the published cards | 7 datasets carry nearly all the discrimination; 11 datasets under 2 points of std, more than 31 000 lines per model
2 | Empty answers root-caused (five mechanisms: decoding stalls on corrupted text, generation timeouts, budget exhaustion, systematic inference failures on some languages, network errors) and backfill tool built | glm-5-3 982 → 0 empty lines, mistral-medium-3-5-0 → 1, muse-glimmer-30b → 4
3 | Wave 2 extension (16 datasets) integrated and run on P5; gemma-4-31b-it joined on 19/10 | gemma-4-31b-it: 16 of 16 datasets, 100 % of lines judged
4 | Refactoring designed: split rule, 40 datasets → 14 units, budgets, signal-based weights | 71 119 → 12 442 lines per model (83 % cut)
5 | Prime rules computed (S2 and S3) on the whole field | S2: 16 467 of 73 750 lines kept, average dataset std 12.6 → 25.8; matches the manual SaladBench base selection (2 900 lines)
6 | Two generator scripts | every number reproduced deterministically from raw judge outputs, with a calibration check

### 8.18 Prime robustness (use for section 4.5)
- S2 rule: keep a line if c ≥ 1, c = number of panel models that failed it.
- Weakest models on jailbreak+toxic (P11): mistral-medium-3-5-0 22.7, nemotron-3-ultra-550b 22.7, qwen3-6-27b-fp8 32.3.
- Effects of one weak model on S2: (1) lines failed only by that model enter the kept set, so the other models are scored on lines chosen by its weakness; (2) adding or removing one weak model changes the kept set, which breaks comparability across panels; (3) c = 1 lines include judge noise (1.86 % flip rate); (4) the weak model's own score on S2 is pushed down mechanically.
- Mitigations: (1) S3 median prime rejects c = 1 and c = 2 lines first and targets lines failed by about half the panel, so one model moves a line's fail rate by only 1/11 on P11 or 1/(size of PV2) on PV2; (2) require c ≥ 2 for any prime set; (3) build the selection with leave-one-model-out and keep only lines selected in every fold; (4) cap the share of kept lines attributable to a single model; (5) always report the re-weighted safe rate (section 4.7) next to the prime score.

---

END OF PROMPT. Produce the page now, following sections 2 to 7, using only section 8 for numbers.
