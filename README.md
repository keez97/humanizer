# Humanizer

A Claude Code skill that removes signs of AI-generated writing from text, making it sound more natural and human.

**Current version: 2.7.0.** The canonical rule set is in `SKILL.md` — this README is an orientation guide only. If this file and `SKILL.md` conflict, `SKILL.md` wins.

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
/humanizer detect    # flag-only audit — no rewrite; severity-grouped tell report
```

Optionally pass a writing sample in `full` mode ("match my voice — here's a post") for sample-based voice calibration.

Do NOT use on: chat replies, status updates, tables, code, commit messages, JSONL/YAML, internal artifacts (state.md, plans, handoffs), frontend chrome.

**When in doubt, use `/humanizer light`** — it scrubs surface tells without stripping confidence-label hedging or imposing first-person voice.

## Mode tiering

| Mode | Active rules | Use for |
|---|---|---|
| `full` | Every tell (Layers A–D), the honest-limit detection-resistance layer, soul/imperfection mandate, full self-scoring battery | Graded essays, cover letters, exec summaries for human readers, published body copy, method narratives |
| `light` | Banned vocab (C2) + em-dash (C5) + signpost density (C8) only. De-hedging suppressed (tell D1 is OFF) | Analytical docs — consulting memos, case studies, technical docs, validation scorecards. Preserves `speculative`/`inferred` confidence labels. |
| `off` | Skill not applied | Chat, tables, code, internal artifacts |
| `detect` | Flag-only — no rewrite. Reports tells grouped by severity (P0/P1/P2) with a definitely-fix vs judgment-call verdict per flag | Auditing without altering: someone else's text, published content, or a pipeline/gate check |

The de-hedging suppression in `light` mode is a binding invariant, not a style preference. The source-quality protocol requires confidence labels to survive on analytical deliverables.

## Self-scoring script

After the editing passes, run the mechanical gate before delivering:

```bash
python3 ~/.claude/skills/humanizer/score.py <draft-file> --mode full
python3 ~/.claude/skills/humanizer/score.py <draft-file> --mode light
```

Ship gate: ALL HARD checks pass AND fewer than 3 soft gates fail. Two-pass cap — do not iterate beyond two battery cycles. In `--mode light`, only checks #6 (banned vocab), #7 (em-dash), #8 (signpost density) are active.

## What's new in v2.7.0

Capabilities harvested faithfully from other open-source humanizer skills (rules incorporated as-written, only refitted to this skill's ID scheme; verified against each source verbatim):

- **New structural tells:** reshuffleable paragraphs (A6, from Aboudjem P38), treadmill/restatement density (B16, P43), symbolic gloss (B1, P40), "Whether…" range-closers + infomercial hooks (B9, P39/P41), noun-phrase cycling (B7, P31), erratic inline bolding (C6, P42), "does more than X; it Y" (B4, slopbuster).
- **`detect` mode** — flag-only audit, no rewrite; tells grouped P0/P1/P2 with a definitely-fix vs judgment-call verdict (from conorbronsdon).
- **Voice calibration** — optional `full`-mode sample matching (match the sample's *variance*, not just its mean; never upgrade vocabulary), with a `light`-mode carve-out (from blader + humanink).
- **System guardrails:** cluster-not-isolated flagging (blader), quoted/illustrative-text exemption (conorbronsdon), patch-vs-rebuild threshold (conorbronsdon), and a "know your own fingerprint" note (Claude's signature cluster, from humanink).

## What's new in v2.6.0

- **Full restructure / dedup.** The accreted ~64 numbered rules (many of which covered the same tell at instance-level *and* density-level) are consolidated into one deduplicated set of tells, grouped by the layer you fix them at: Architecture (A) → Sentence & rhetoric (B) → Lexical & surface (C) → Hedging & distribution (D). ~50% shorter, no operative content lost. SKILL.md is the canonical rule set.
- **Honest Limits (detection-resistance) promoted to the top.** A 2026-06-12 controlled study (GPTZero Model 4.6b oracle) established that editing AI-drafted text does not beat a trained classifier — the document verdict is driven by authorship *direction*, which editing can't change. The skill is now framed as a quality tool, not a detector-evasion tool. The procedural-genre floor and the integrity routing are stated explicitly.
- **Layer D caveat.** The burstiness/CV target can push *up* the AI score on analytical/technical text; the honest-limit findings govern when they conflict with the distribution battery.

## What carried over (v2.5.0 foundations)

- Detection-aware statistical layer (tells D1–D6 / battery): sentence-length CV, paragraph-length variance, signpost density, tricolon saturation, negation-reversal density, hedge density, lexical banlist (29 words), em-dash hard gate, contractions alibi floor.
- Mode tiering (`full` / `light` / `off`); light mode is the default for analytical deliverables, with de-hedging suppressed as a binding invariant.
- Five-pass workflow: architecture → sentence → lexical → audit → read-aloud. Order matters.
- Self-scoring battery (`score.py`) as ship gate with HARD/soft distinction.

## Tells at a glance

The deduplicated tells live in four fix-order layers. Full definitions, before/after examples, density thresholds, and mode flags are in `SKILL.md`.

| Layer | IDs | What it catches |
|---|---|---|
| A — Architecture | A1–A6 | Source-review framing, patterned issue paragraphs / list uniformity, roadmap sentences, formulaic "challenges" sections, abstract framing-tissue concentration, reshuffleable paragraphs |
| B — Sentence & rhetoric | B1–B16 | Significance inflation & symbolic gloss, -ing pseudo-depth, copula avoidance, negative parallelism, rule of three, false ranges, synonym & noun-phrase cycling, frame-then-pivot, tidy closers/slogans/hooks, stacked declaratives & length monotony, clever inversions, performative similes, tidy concessions, colon-restatement & cascades, opening-word repetition, treadmill/restatement |
| C — Lexical & surface | C1–C11 | AI vocabulary, hard banlist (29 words), categorical pronouncements, nominalizations/coined compounds, em dash, curly quotes/boldface/erratic bolding/emojis, filler, signpost & connective density, promotional language, vague attributions, notability name-dropping |
| D — Hedging & distribution | D1–D6 | Hedging (instance/numeric/density — suppressed in light), sentence-length CV, paragraph-length variance, perplexity/specificity anchors, framework-mapping enumeration, contractions alibi floor |
| Communication artifacts | — | Chatbot artifacts, knowledge-cutoff disclaimers, sycophantic tone, generic positive conclusions |
| Cross-cutting | — | Cluster-not-isolated flagging, quoted/illustrative-text exemption, patch-vs-rebuild threshold, Claude-fingerprint note, optional voice calibration |

## References

- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) — primary source
- [WikiProject AI Cleanup](https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup) — maintaining organization

## Version history

- **2.7.0** — Capability harvest from peer OSS humanizer skills (blader, conorbronsdon/avoid-ai-writing, Aboudjem/humanizer-skill, sirambrosio/humanink), incorporated faithfully and verified against each source. New tells (A6, B16, + enrichments to B1/B4/B7/B9/C6), `detect` mode, optional voice calibration, and cross-cutting guardrails (cluster gate, quoted-source exemption, patch-vs-rebuild, Claude fingerprint). Battery and modes' core contract unchanged.
- **2.6.0** — Detection-resistance layer promoted to top (honest limits of editing AI-drafted text vs. trained classifiers; procedural-genre floor; integrity routing). Full restructure: ~64 instance+density rules deduplicated into one tell set across four fix-order layers (A/B/C/D); ~50% shorter, no operative content lost. SKILL.md is canonical; battery and modes unchanged.
- **2.5.0** — Statistical-distribution layer, mode tiering (full/light/off), self-scoring battery (`score.py`), analytical/argumentative + structural + rhetorical-craft patterns, over-humanizing trap guardrails, four-pass workflow
- **2.3.0** — Added pattern #25: hyphenated word pair overuse
- **2.2.0** — Added final "obviously AI generated" audit + second-pass rewrite prompts
- **2.1.1** — Fixed pattern #18 example (curly quotes vs straight quotes)
- **2.1.0** — Added before/after examples for all 24 patterns
- **2.0.0** — Complete rewrite based on raw Wikipedia article content
- **1.0.0** — Initial release

## License

MIT
