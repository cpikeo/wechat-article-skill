# Evaluation data & visual review

This directory separates development/evaluation assets from Skill runtime. The six paired Markdown cases are real-source excerpts, translations or public-domain text; they are not controlled outputs from this V6 model run.

## Sample provenance and rights

| ID | Type | Source | Rights / treatment |
|---|---|---|---|
| `business` | analysis | Our World in Data, *Do workers in richer countries work longer hours?* (2020-12-21; archived) | CC BY 4.0; Chinese evaluation excerpt/translation |
| `news` | news | Chinese Wikinews, Microsoft layoffs (2025-07-03) | CC BY 4.0; evaluation excerpt |
| `tutorial` | tutorial | Python 3 tutorial, `range()` | PSF License Version 2; documentation excerpt |
| `profile` | profile | Chinese Wikipedia, Tu Youyou | CC BY-SA 4.0; adapted excerpt under same license |
| `opinion` | opinion | Liang Qichao, “The Greatest Suffering and the Greatest Joy” | Public-domain-marked text; excerpt restructured without rewriting wording |
| `longform` | longform | Zhu Ziqing, “背影” | Public-domain-marked text; paragraphs only resegmented |

Source URLs, publication status, adaptation and license evidence are recorded in `cases.json`. The repository's MIT license does not relicense these excerpts; follow each source's terms when reusing them. Metadata was last recorded as reviewed on 2026-11-02; this is not a claim of this turn's second-source fact-check.

## What the deterministic evaluation proves

`tests/editorial_eval.py` checks source/edited pairs, declared preservation tokens, edit ledgers, Gate 1/2, literal fact/qualifier/quote changes, repeated rendering and report freshness. It does **not** judge title promise semantically, argument quality, information gain, author voice, theme preference or factual truth.

The current theme sample map is: `paper`–business analysis, `letter`–longform, `ink`–opinion, `frost`–news, `bone`–tutorial, `folio`–profile. `tests/visuals.py` renders these real-source samples at 320/360/390/430px and renders the *same business-analysis draft* under all six themes. A neutralized-color browser capture checks that typographic hierarchy, grid, component geometry and reading rhythm still differ; it is a structural regression signal, not an aesthetic score. The six article samples contain no embedded images, so browser image-load assertions are vacuous; asset paths, roles and upload safety are covered by separate synthetic regression fixtures, not editorial image-quality evaluation.

```bash
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md
python3 tests/visuals.py
```

Screenshot output is generated under the ignored `evaluation/visual-review/` directory and is not a runtime dependency or a committed test artifact.

## Blind review and execution status

Blind A/B packets can be created with the answer key in a separate directory:

```bash
python3 tests/editorial_eval.py \
  --blind-dir /tmp/wechat-blind \
  --key-file /tmp/wechat-key.json \
  --seed reviewer-01
```

The reviewer should identify which draft better fulfills its title, preserves facts and limits, improves logic and information gain, and reads more clearly; cite passages and allow “no preference.”

- **Controlled real-model execution:** `BLOCKED` until a model runner and reproducible prompts/settings are available. Existing pairs are not represented as fresh model generations.
- **Independent blind review:** `UNVERIFIED` until external readers submit results.
- **Second-source fact-check:** `UNVERIFIED`; literal diff and stored provenance are not fact verification.
- **Real WeChat account/device acceptance:** `UNVERIFIED` without authorized account and target devices.
