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

The current theme sample map is: `paper`–business analysis, `letter`–longform, `ink`–opinion, `frost`–news, `bone`–tutorial, `folio`–profile. `tests/visuals.py` renders these six source-based cases at 320/360/390/430px and separately renders the *same image-bearing article* under all six themes. A neutralized-color, full-page browser comparison checks that typography, grid, component geometry and reading rhythm do not collapse to color-only variants; it is a structural regression signal, not an aesthetic score. The six editorial cases have no body images and are not counted as image evidence.

## Real-image visual fixture

`visual-sample.md` is a human-authored visual test, not an LLM output, article-quality score, or factual proof. Its image is Katsushika Hokusai's *Under the Wave off Kanagawa* (The Met, object 45434). The museum API identifies it as public domain (`isPublicDomain=true`); The Met Open Access policy applies CC0 to public-domain images and data. Source image and license: [object record](https://www.metmuseum.org/art/collection/search/45434), [API record](https://collectionapi.metmuseum.org/public/collection/v1/objects/45434), [direct image](https://images.metmuseum.org/CRDImages/as/original/DP130155.jpg), [Open Access policy](https://www.metmuseum.org/hubs/open-access).

- `visual-assets/great-wave.jpg`: local 1800×1210 derivative of the Met primary image, resized without retouching.
- `visual-assets/great-wave-cover.jpg`: 2.35:1 crop `(0, 364, 1800, 1130)` from that derivative. It keeps the wave, boats and small Fuji together, but cuts off the highest wave crest; the square-feed crop is separately inspected in the browser preview. The crop is a preview choice, not the full work.
- `visual-assets/great-wave-crest.jpg`: 820×705 detail crop `(300, 55, 1120, 760)`; `great-wave-fuji.jpg`: 690×580 detail crop `(900, 560, 1590, 1140)`. Both are explicitly labeled as crops of the same source work, not separate objects or external evidence.
- Declared roles: cover crop; full-width explanatory image; detail crop; adjacent comparison pair. Alt text explains each crop and its reading purpose. The museum scan is a catalog image, not a field photograph, AI illustration, or evidence of current sea conditions.
- Browser checks validate local load, declared image count, overflow, body/table/caption text sizes, and all four mobile widths under all six themes. Human review is still needed to judge focal point, role fit, authenticity in a specific article, and whether the detail remains legible at phone size; browser rendering does not prove WeChat behavior.

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
