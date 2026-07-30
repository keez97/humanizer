# AGENTS.md

Guidance for coding agents working in this repository.

## What this repo is

A Claude Code skill plus a scoring script. Two artifacts matter:

- **`SKILL.md`** is the runtime. YAML frontmatter (`name`, `version`, `description`, `allowed-tools`) followed by the editor prompt. This is the canonical rule set, and it is the file the model actually reads. If a change belongs anywhere, it usually belongs here.
- **`score.py`** is the mechanical half. Stdlib only, no dependencies, exit code 0/1. It enforces the checks in `SKILL.md` § Self-scoring battery that can be measured without judgment.

`README.md` is for humans. `perplexity.py` and `binoculars.py` are retained experiments, documented in `SKILL.md` § Honest Limits as *not* faithful proxies for modern detectors. Do not present them as working detection.

## Rules for changes

**`SKILL.md` and `score.py` must stay in sync.** Every mechanical threshold in the battery table has a corresponding check in `score.py`. Change one, change the other, and update the table.

**Respect the evidence tiers.** Vocabulary in `score.py` is split into `BANNED_VOCAB` (corroborated by a cited study, HARD gate) and `WATCHLIST_VOCAB` (observed only, soft gate). Do not promote a word to tier 1 on intuition. Wikipedia's page is explicit that a word being overused by AI does not imply its synonyms are, so do not expand either list by adding synonyms of existing entries.

**Vocabulary is stored as lemmas.** `inflect()` derives plurals, tenses, and adverb forms at match time. Add the lemma, not every form.

**Never weaken the scorer through config.** The `--config` path may extend or tighten defaults. It may not remove entries or raise thresholds. A missing or malformed config warns to stderr and falls back to hardcoded defaults; it must never crash.

**Two checks are deliberately not automated.** Colon-restatement (#11) and perplexity-anchor coverage (#13) need judgment. Do not write regex approximations for them; the script prints them as MODEL-JUDGMENT and the skill routes them through a self-review pass.

**Illustrative text is off-limits.** `strip_non_prose()` drops fenced code, headings, tables, blockquotes, and inline code spans, because those carry quoted examples rather than the author's prose. This is what lets `SKILL.md` and `README.md` discuss the banlist without failing on it. Preserve that behavior.

## Verifying a change

There is no test suite. Verify by running the scorer:

```bash
python3 score.py README.md --mode light     # must PASS; the README is a live fixture
python3 score.py <sample> --mode full
```

The README passing its own light-mode battery is a real check, not decoration. If a change to the vocabulary or the stripping logic breaks it, that is a signal worth reading before you adjust the README.

## Provenance

Descended from [blader/humanizer](https://github.com/blader/humanizer) (MIT, Siqi Chen); the pattern catalogue originates with Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) (CC BY-SA). When adding a tell, cite where it came from, and prefer the studies listed in `SKILL.md` § Reference over intuition.
