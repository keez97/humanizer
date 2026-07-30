# Humanizer

A Claude Code skill that strips the signs of AI-generated writing out of prose.

Surface cleanup is the easy half. Anyone can delete em dashes and swap out `delve`. The tells that actually survive editing live in structure and cadence: paragraphs you could reorder without breaking the argument, colon-lead cascades, every sentence landing at 20 words, tidy summary endings that tie a bow. This skill is organized around fixing those first.

**Current version: 2.9.0.** `SKILL.md` is the canonical rule set. If this README and `SKILL.md` disagree, `SKILL.md` wins.

## What this is honest about

Editing AI-drafted text does not beat a trained classifier. A controlled run of six rewrites across two genres, scored against GPTZero Model 4.6b, held at 100% AI on every single one, including rewrites where sentence-level edits had driven the per-sentence panel mostly clean. The same author's genuinely human-written essay scored 94% human on the same oracle with no editing at all.

The variable that moves a detector's verdict is authorship direction, and editing cannot change it.

So this is a writing-quality tool. Every rule in it also makes prose less generic, which is the reason to use it. If you came looking for something that launders AI output past a plagiarism gate on graded work, this will not do that, and `SKILL.md` says so in more detail than you probably want. See the Honest Limits section there.

## Install

```bash
git clone https://github.com/keez97/humanizer.git ~/.claude/skills/humanizer
```

That is the whole install. `score.py` is stdlib-only, so there is nothing to pip install and no virtualenv to create. Update with `git -C ~/.claude/skills/humanizer pull`.

Cloned into your skills directory like that, it loads as a skills-directory plugin and the skill keeps its plain name, so you invoke it as `/humanizer`.

It also ships a plugin manifest, so you can load it as a normal plugin instead:

```bash
claude --plugin-dir /path/to/humanizer
```

Loaded that way the skill is namespaced, so it becomes `/humanizer:humanizer`. Both routes run identical rules; pick whichever fits how you manage extensions.

## Usage

```
/humanizer           # full mode: essays, cover letters, published body copy
/humanizer light     # light mode: memos, case studies, technical docs
/humanizer detect    # flag-only audit, no rewrite
```

In `full` mode you can pass a writing sample ("match my voice, here's a post") and it will calibrate against your own sentence-length variance, vocabulary register, and punctuation habits rather than imposing a default voice.

Do not run it on chat replies, tables, code, commit messages, YAML, or internal artifacts like plans and handoffs. It will corrupt structure that parsers depend on.

**When in doubt, use `light`.** It scrubs surface tells without stripping confidence hedging or forcing first person into a document that should not have it.

### Modes

| Mode | Active | Use for |
|---|---|---|
| `full` | Every tell (Layers A through E), the statistical battery, the soul/imperfection mandate | Graded essays, cover letters, exec summaries, published body copy |
| `light` | Banned vocab, em dash, signpost density. De-hedging is OFF | Consulting memos, case studies, technical docs |
| `off` | Nothing | Chat, tables, code, internal artifacts |
| `detect` | Flag-only, grouped P0/P1/P2 with a fix-vs-judgment-call verdict per flag | Auditing text you are not going to rewrite |

De-hedging stays suppressed in `light` mode as a binding invariant, not a preference. Analytical deliverables need their `speculative` and `inferred` labels to survive the pass.

## The scorer

```bash
python3 ~/.claude/skills/humanizer/score.py <draft> --mode full
python3 ~/.claude/skills/humanizer/score.py <draft> --mode light
python3 ~/.claude/skills/humanizer/score.py <draft> --grok    # add Grok idiolect vocab
cat draft.md | python3 score.py --mode light                  # reads stdin too
```

Fourteen checks. Sentence-length coefficient of variation, paragraph variance, vocabulary tiers, em dashes, signpost density, tricolon saturation, negation reversal, hedge stacking, and a contractions floor. Exit code 0 for pass, 1 for fail, so you can gate a pipeline on it.

Ship gate: every HARD check passes and fewer than three soft checks fail. Two-pass cap. Looping a draft against the battery more than twice over-fits to the battery itself, which becomes its own signature.

Two checks (colon-restatement and perplexity-anchor coverage) need judgment and are deliberately left to the model rather than faked in regex.

## What changed in 2.9.0

- **A no-fabrication rule, as governing principle 8.** The rewrite must not contain a fact, name, number, date, quote, or citation absent from the source, and a fabrication counts as a defect even when it reads better than the vague original. This closes a hole the skill itself opened: rule D4 tells the model to add a concrete anchor to any paragraph that lacks one, which is an open invitation to invent a plausible statistic. D4 now carries an explicit warning, and the audit pass asks a second, separate question about fabricated specifics. Separate on purpose, because an invented number is invisible to a style audit: it looks exactly like what the style audit asked for.
- **A7, fragmented headers.** A heading followed by a line that just restates the heading before the real content starts.
- **A8, diff-anchored writing.** Prose narrating a change instead of describing the thing as it stands. Common in docs and code comments written from a diff.
- **B11 extended** with aphorism formulas: `X is the Y of Z`, `the language of`, `the currency of`, `X becomes a trap`.
- **B9 extended** with fake-candid openers: `Honestly?`, `Look,`, `Real talk`, `Let's be honest`.

Patterns A7, A8 and the two watch-lists were ported from [blader/humanizer](https://github.com/blader/humanizer) v2.9.x, as was the no-fabrication rule.

## What changed in 2.8.0

Synced against the current version of Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing). Two of these fix rules that were wrong, not merely incomplete.

- **Vocabulary is now era-tiered.** The overused word set moves. `delve` was the signature ChatGPT word in 2023, faded through 2024, and fell off sharply in 2025. The current cluster is different and much smaller. A flat banlist calibrated to 2023 hard-fails drafts over dead vocabulary while missing what current models actually overuse.
- **The banlist is split by evidence.** Tier 1 is corroborated by at least one cited study and gates HARD. Tier 2 is observed-but-unproven and gates soft. Fifteen words were previously hard-gated with no study behind them, and a human consultant writes `leverage` and `holistic` without any help from a model.
- **Hedging rule reversed on single hedges.** Reinhart et al. (PNAS) found that hedging qualifiers, intensifiers, and ordinary wordy constructions (`in order to`, `the fact that`) occur *more* in human writing than in LLM output. Stripping them drives prose toward the machine baseline. The rule now targets stacking (`may potentially`) rather than hedging itself.
- **Same correction for plain superlatives.** `One of the best` and `was the first` are human signals. The tell is unearned significance on a routine fact, not confidence.
- **New Layer E: ineffective indicators.** What not to flag. Perfect grammar, mixed formal/casual register, "robotic" prose, academic vocabulary, transition words in isolation. Over-flagging has a real cost, and humans are close to random chance at this: one study measured 57% recognition of AI text against 64% for human text.
- **Model idiolects.** Claude, ChatGPT, Gemini, and Grok have measurably different fingerprints. Knowing the source narrows where to look.
- **Scorer fix:** vocabulary is stored as lemmas now and inflected at match time. The old exact matching silently missed `showcases`, `underscored`, `bolstered`, and `aligned with`.

## Attribution

This is an independent rewrite descended from [blader/humanizer](https://github.com/blader/humanizer) by Siqi Chen, MIT licensed. The two have diverged: as of this version they share six lines of text, all of them headings and frontmatter keys. The layer taxonomy, the mode system, the statistical battery, and all of the Python are written here. The debt is real anyway, and that project is worth reading on its own.

The underlying pattern catalogue originates with Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup, available under CC BY-SA. `SKILL.md` lists the individual studies it relies on.

## Repo contents

| File | What it is |
|---|---|
| `SKILL.md` | The canonical rule set. Everything else is support. |
| `.claude-plugin/plugin.json` | Plugin manifest, so the repo can be loaded as a Claude Code plugin as well as a plain skill. |
| `score.py` | The scoring battery. Stdlib only. |
| `perplexity.py`, `binoculars.py` | Local detector-metric experiments. Kept as infrastructure, and documented in `SKILL.md` as *not* faithful proxies for how modern detectors behave. They need PyTorch if you want to run them. |

## License

MIT. See `LICENSE`.
