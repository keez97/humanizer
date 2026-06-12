# Humanizer

A Claude Code skill that removes signs of AI-generated writing from text, making it sound more natural and human.

**Current version: 2.6.0.** The canonical rule set is in `SKILL.md` — this README is an orientation guide only. If this file and `SKILL.md` conflict, `SKILL.md` wins.

## Installation

### Recommended (clone directly into Claude Code skills directory)

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/blader/humanizer.git ~/.claude/skills/humanizer
```

### Manual install/update (only the skill file)

If you already have this repo cloned (or you downloaded `SKILL.md`), copy the skill file into Claude Code's skills directory:

```bash
mkdir -p ~/.claude/skills/humanizer
cp SKILL.md ~/.claude/skills/humanizer/
```

## Usage

Invoke via the slash command:

```
/humanizer           # full mode — external deliverables, essays, published body copy
/humanizer light     # light mode — analytical docs (memos, case studies, technical docs)
```

Do NOT use on: chat replies, status updates, tables, code, commit messages, JSONL/YAML, internal artifacts (state.md, plans, handoffs), frontend chrome.

**When in doubt, use `/humanizer light`** — it scrubs surface tells without stripping confidence-label hedging or imposing first-person voice.

## Mode tiering

| Mode | Active rules | Use for |
|---|---|---|
| `full` | All 64 rules (incl. the §4 detection-resistance layer), soul/imperfection mandate, full self-scoring battery | Graded essays, cover letters, exec summaries for human readers, published body copy, method narratives |
| `light` | Banned vocab + em-dash + signpost density only. De-hedging suppressed (rules 20, 23, 29, 57 are OFF) | Analytical docs — consulting memos, case studies, technical docs, validation scorecards. Preserves `speculative`/`inferred` confidence labels. |
| `off` | Skill not applied | Chat, tables, code, internal artifacts |

The de-hedging suppression in `light` mode is a binding invariant, not a style preference. The source-quality protocol requires confidence labels to survive on analytical deliverables.

## Self-scoring script

After the editing passes, run the mechanical gate before delivering:

```bash
python3 ~/.claude/skills/humanizer/score.py <draft-file> --mode full
python3 ~/.claude/skills/humanizer/score.py <draft-file> --mode light
```

Ship gate: ALL HARD checks pass AND fewer than 3 soft gates fail. Two-pass cap — do not iterate beyond two battery cycles. In `--mode light`, only checks #6 (banned vocab), #7 (em-dash), #8 (signpost density) are active.

## What's new in v2.5.0

- **Detection-aware statistical layer (rules 47-57):** targets the axis AI detectors actually score on — sentence-length CV (burstiness), paragraph-length variance, signpost density, tricolon saturation, negation-reversal density, colon-restatement density, over-hedging, lexical banlist (29 words), em-dash hard gate, contractions alibi floor.
- **Mode tiering:** `full` / `light` / `off` — light mode is now the correct default for analytical deliverables.
- **Four-pass workflow:** architecture (Pass 1) → sentence-level (Pass 2) → lexical (Pass 3) → audit (Pass 4) → read-aloud (Pass 5). Order matters — do not combine.
- **Self-scoring battery** (`score.py`) as ship gate with HARD/soft distinction.
- **Analytical and argumentative patterns (rules 19-24):** colon-with-restatement, hedge-everything numerics, frame-then-pivot, tidy summary-clause endings, numbered-list uniformity, stacked declaratives.
- **Structural patterns (rules 32-39):** colon-lead cascades, categorical academic pronouncements, stacked nominalizations, implication/lesson closers, rule-of-three saturation, roadmap sentences, sentence-length monotony, opening-word repetition.
- **Rhetorical-craft patterns (rules 40-46):** source-review framing, slogan-y standalone sentences, paired coined compounds, clever inversions/chiasmus, performative similes, tidy concession patterns, patterned issue paragraphs.
- **Over-humanizing trap** section: CV ceiling (0.65 max), imperfection rationing, no folksiness for its own sake.

## Patterns at a glance

57 rules organized across six clusters. Full definitions, before/after examples, and mode-applicability flags are in `SKILL.md`.

| Cluster | Rules | What it catches |
|---|---|---|
| Content | 1-6 | Significance inflation, notability name-dropping, -ing analyses, promotional language, vague attributions, formulaic challenges sections |
| Language & grammar | 7-12 | AI vocabulary (surface + analytical sub-list), copula avoidance, negative parallelisms, rule of three, synonym cycling, false ranges |
| Style | 13-18 | Em dash, boldface, inline-header lists, title case headings, emojis, curly quotes |
| Analytical/argumentative | 19-24, 28-31 | Colon-with-restatement, hedge-everything numerics, frame-then-pivot, tidy summary endings, numbered-list uniformity, stacked declaratives, filler phrases, excessive hedging, generic conclusions, hyphenated word-pair overuse |
| Structural | 32-39 | Colon-lead cascades, categorical pronouncements, stacked nominalizations, implication closers, rule-of-three saturation, roadmap sentences, sentence-length monotony, opening-word repetition |
| Rhetorical-craft | 40-46 | Source-review framing, slogan-y standalones, paired coined compounds, clever inversions, performative similes, tidy concession patterns, patterned issue paragraphs |
| Statistical-distribution | 47-57 | Sentence-length CV, perplexity anchors, paragraph-length variance, framework-mapping enumeration, lexical banlist (29 words), em-dash hard gate, signpost density, tricolon density, negation-reversal density, colon-restatement density, over-hedging |

## References

- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) — primary source
- [WikiProject AI Cleanup](https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup) — maintaining organization

## Version history

- **2.5.0** — Statistical-distribution layer (rules 47-57), mode tiering (full/light/off), self-scoring battery (`score.py`), analytical/argumentative patterns (rules 19-24), structural patterns (rules 32-39), rhetorical-craft patterns (rules 40-46), over-humanizing trap guardrails, four-pass workflow
- **2.3.0** — Added pattern #25: hyphenated word pair overuse
- **2.2.0** — Added final "obviously AI generated" audit + second-pass rewrite prompts
- **2.1.1** — Fixed pattern #18 example (curly quotes vs straight quotes)
- **2.1.0** — Added before/after examples for all 24 patterns
- **2.0.0** — Complete rewrite based on raw Wikipedia article content
- **1.0.0** — Initial release

## License

MIT
