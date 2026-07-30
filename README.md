# Humanizer

A Claude Code skill that strips the tells of AI-generated writing out of prose. A *tell* here means one specific habit that marks text as machine-written, and the skill names 43 of them.

Surface cleanup is the easy half. Anyone can delete em dashes and swap out `delve`. The tells that survive editing are the structural ones: paragraphs you could reorder without breaking the argument, colon-lead cascades, every sentence landing at 20 words, tidy endings that tie a bow. The skill fixes those first.

**Current version: 2.9.0.** `SKILL.md` is the canonical rule set. If this README and `SKILL.md` disagree, `SKILL.md` wins.

## What this is honest about

Editing AI-drafted text doesn't beat a trained classifier. A controlled run of six rewrites across two genres, scored against GPTZero Model 4.6b, held at 100% AI on every one. That includes rewrites where GPTZero's own sentence-by-sentence display had gone mostly green, so the per-sentence view and the document verdict clearly move independently. The same author's genuinely human-written essay scored 94% human on the same detector with no editing at all. What decides the verdict is who drafted the text, and editing can't change that.

So this is a writing-quality tool. Every rule in it also makes prose less generic, which is the reason to use it. [references/DETECTION-LIMITS.md](references/DETECTION-LIMITS.md) has the full study, including the genres where no amount of editing helps.

## Install

```bash
git clone https://github.com/keez97/humanizer.git ~/.claude/skills/humanizer
```

That's the whole install. `score.py` is stdlib-only, so there is nothing to pip install and no virtualenv to create. Update with `git -C ~/.claude/skills/humanizer pull`.

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

**When in doubt, use `light`.** It scrubs surface tells without stripping confidence hedging or forcing first person into a document that shouldn't have it.

### Modes

| Mode | Active | Use for |
|---|---|---|
| `full` | Every tell (Layers A through E), the statistical battery, the soul/imperfection mandate | Graded essays, cover letters, exec summaries, published body copy |
| `light` | Banned vocab, em dash, signpost density. De-hedging is OFF | Consulting memos, case studies, technical docs |
| `off` | Nothing | Chat, tables, code, internal artifacts |
| `detect` | Flag-only, grouped P0/P1/P2 with a fix-vs-judgment-call verdict per flag | Auditing text you aren't going to rewrite |

`light` mode never removes hedging, and that rule cannot be overridden. Analytical documents label claims `speculative` or `inferred`, and a de-hedging pass would strip exactly those labels.

## The scorer

```bash
python3 ~/.claude/skills/humanizer/score.py <draft> --mode full
python3 ~/.claude/skills/humanizer/score.py <draft> --mode light
python3 ~/.claude/skills/humanizer/score.py <draft> --grok    # add Grok idiolect vocab
cat draft.md | python3 score.py --mode light                  # reads stdin too
```

Fourteen checks. How much sentence length varies, how much paragraph length varies, the vocabulary tiers, em dashes, signpost density, tricolon saturation, negation reversal, hedge stacking, and a floor on contractions. Exit code 0 for pass and 1 for fail, so you can gate a pipeline on it.

A draft ships when every HARD check passes and fewer than three soft checks fail. Run the battery at most twice, because looping a draft against it more than that over-fits to the battery itself, and the battery then becomes its own signature.

Two checks (colon-restatement and perplexity-anchor coverage) need judgment and are deliberately left to the model rather than faked in regex.

## The optional model-based scorers

`score.py` measures structure and lexicon. It can't see *perplexity*, which is the axis trained detectors actually score: how predictable each token is under a reference model, and how much that predictability varies sentence to sentence. Two scripts fill that gap. Both work, and both need PyTorch:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python perplexity.py <draft>
.venv/bin/python binoculars.py <draft>
```

First run downloads weights (~500 MB for GPT-2, ~2 GB for the Qwen pair).

**`perplexity.py`** loads GPT-2 and reports document perplexity, per-sentence perplexity, and burstiness, ranking sentences from most to least predictable.

**`binoculars.py`** implements Binoculars ([Hans et al., 2024](https://arxiv.org/abs/2401.12070)), dividing log-perplexity under an observer model by cross-perplexity against a sibling performer model. Content that surprises both models cancels out, which matters in number-heavy writing where a figure like `$320m` inflates raw perplexity no matter who wrote it.

**Trust the ranking. Ignore the score at the top.** The controlled study in [references/DETECTION-LIMITS.md](references/DETECTION-LIMITS.md) tested both tools against GPTZero, and neither reproduced its document-level judgment. GPT-2 rated the target text more human than a 1946 Orwell passage. So don't build a rewrite loop that optimizes against these numbers and expect the result to transfer to a commercial detector, because on the evidence available it doesn't.

The rankings are a different matter. Run either tool on a paragraph and the sentences at the bottom of the list are where your prose has gone predictable, which is what D2 and D4 reach for indirectly. I use it that way and it earns its keep, even though the number at the top of the output travels nowhere.

## Portability

`SKILL.md` conforms to the [Agent Skills](https://agentskills.io) open standard, which more than 40 tools now read, among them Cursor, Gemini CLI, OpenAI Codex, GitHub Copilot, VS Code, Goose, OpenCode, Roo Code, and Amp. The frontmatter sets only `name`, `description`, `license`, and `metadata`, so nothing in it is tied to one product. `allowed-tools` is deliberately absent, because the spec marks that field experimental with support that varies by agent.

`score.py` is stdlib Python and needs no agent at all. You can run it on a text file with no LLM involved.

So the rules travel: point any skills-compatible agent at this directory, or paste `SKILL.md` into a system prompt and it works the same way.

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
| `perplexity.py`, `binoculars.py` | Optional model-based scorers. They work; see below. Require PyTorch. |
| `requirements.txt` | Deps for those two only. `score.py` needs nothing. |

## License

MIT. See `LICENSE`.
