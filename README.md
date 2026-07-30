# Humanizer

A Claude Code skill that strips the signs of AI-generated writing out of prose.

Surface cleanup is the easy half. Anyone can delete em dashes and swap out `delve`. The tells that actually survive editing live in structure and cadence: paragraphs you could reorder without breaking the argument, colon-lead cascades, every sentence landing at 20 words, tidy summary endings that tie a bow. This skill is organized around fixing those first.

**Current version: 2.9.0.** `SKILL.md` is the canonical rule set. If this README and `SKILL.md` disagree, `SKILL.md` wins.

## What this is honest about

Editing AI-drafted text does not beat a trained classifier. A controlled run of six rewrites across two genres, scored against GPTZero Model 4.6b, held at 100% AI on every single one, including rewrites where sentence-level edits had driven the per-sentence panel mostly clean. The same author's genuinely human-written essay scored 94% human on the same oracle with no editing at all.

The variable that moves a detector's verdict is authorship direction, and editing cannot change it.

So this is a writing-quality tool. Every rule in it also makes prose less generic, which is the reason to use it. [references/DETECTION-LIMITS.md](references/DETECTION-LIMITS.md) has the full study, including the genres where the floor is irreducible.

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

## Portability

`SKILL.md` conforms to the [Agent Skills](https://agentskills.io) open standard, which a good number of agents now read: Cursor, Gemini CLI, OpenAI Codex, GitHub Copilot, VS Code, Goose, OpenCode, Roo Code, Amp, and others. The frontmatter sets only `name`, `description`, `license`, and `metadata`, so nothing in it is tied to one product. `allowed-tools` is deliberately absent; the spec marks it experimental with support that varies by agent.

`score.py` is stdlib Python and cares about no agent at all. You can run it on a text file with no LLM in the loop.

So the rules travel. Point any skills-compatible agent at this directory, or just paste `SKILL.md` into a system prompt.

## Attribution

This is an independent rewrite descended from [blader/humanizer](https://github.com/blader/humanizer) by Siqi Chen, MIT licensed. The two have diverged: as of this version they share six lines of text, all of them headings and frontmatter keys. The layer taxonomy, the mode system, the statistical battery, and all of the Python are written here. The debt is real anyway, and that project is worth reading on its own.

The underlying pattern catalogue originates with Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup, available under CC BY-SA. `SKILL.md` lists the individual studies it relies on.

## Repo contents

| File | What it is |
|---|---|
| `SKILL.md` | The canonical rule set. Everything else is support. |
| `.claude-plugin/plugin.json` | Plugin manifest, so the repo can be loaded as a Claude Code plugin as well as a plain skill. |
| `score.py` | The scoring battery. Stdlib only. |
| `references/` | Material loaded on demand rather than on every invocation: the detector study, a worked example, the source list, voice calibration. |
| `perplexity.py`, `binoculars.py` | Local detector-metric experiments. Kept as infrastructure, and documented in `references/DETECTION-LIMITS.md` as *not* faithful proxies for how modern detectors behave. They need PyTorch if you want to run them. |

## License

MIT. See `LICENSE`.
