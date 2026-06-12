#!/usr/bin/env python3
"""
humanizer/perplexity.py — GPT-2 perplexity meter (the inner-loop proxy for GPTZero)

GPTZero and most trained AI detectors score *perplexity* (how predictable each
token is under a reference language model) and *perplexity-burstiness* (how much
that surprise varies sentence to sentence). The stdlib score.py battery measures
structure and lexicon; it cannot see perplexity. This module fills that gap.

It loads GPT-2 (the same lineage GPTZero was originally built on) and reports:
  - document perplexity            (lower = reads more AI)
  - per-sentence perplexity        (the lowest are GPTZero's "most AI sentences")
  - perplexity-burstiness          (stdev of per-sentence perplexity; higher = more human)

Requires torch + transformers. Install once into the skill venv:
  python3 -m venv .venv && . .venv/bin/activate && pip install torch transformers

Usage:
  .venv/bin/python perplexity.py <file> [--model gpt2|distilgpt2] [--json] [--top N]
  .venv/bin/python perplexity.py --sentence "score just this one sentence"
  cat file.txt | .venv/bin/python perplexity.py
"""

import os
import sys
import json
import math
import argparse

# Reuse the exact prose-cleaning + sentence-splitting the gate uses, so the two
# tools never disagree on what a "sentence" is.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import strip_non_prose, split_sentences, word_count  # noqa: E402

_MODEL_CACHE = {}


def _load(model_name: str):
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)
    model.eval()
    torch.set_grad_enabled(False)
    _MODEL_CACHE[model_name] = (tok, model, torch)
    return _MODEL_CACHE[model_name]


def text_nll(text: str, model_name: str = "gpt2"):
    """Mean per-token negative log-likelihood (nats) of `text`, scored standalone.

    Returns (mean_nll, n_tokens). Returns (nan, 0) if the text is too short to
    score (a single token has no preceding context to be predicted from).
    """
    tok, model, torch = _load(model_name)
    ids = tok(text, return_tensors="pt", truncation=True, max_length=1024).input_ids
    if ids.shape[1] < 2:
        return float("nan"), ids.shape[1]
    # Standard causal-LM loss = mean NLL of predicting token i from tokens <i.
    out = model(ids, labels=ids)
    return float(out.loss), ids.shape[1] - 1


def perplexity(text: str, model_name: str = "gpt2") -> float:
    nll, n = text_nll(text, model_name)
    if math.isnan(nll):
        return float("nan")
    return math.exp(nll)


def incontext_sentence_nll(sentences, model_name="gpt2", ctx_tokens=900):
    """Per-sentence mean NLL scored *in context*.

    For sentence i, feed (preceding text + sentence i) to the model but measure
    loss ONLY over sentence i's tokens. This is how a detector reads continuous
    prose: a sentence is "predictable" given everything before it, not in
    isolation. Context is capped to the last `ctx_tokens` tokens (GPT-2 window
    is 1024).
    """
    tok, model, torch = _load(model_name)
    results = []
    running = ""
    for s in sentences:
        prefix = (running + " ") if running else ""
        ctx_ids = tok(prefix, return_tensors="pt").input_ids if prefix else None
        full_ids = tok(prefix + s, return_tensors="pt").input_ids
        n_ctx = ctx_ids.shape[1] if ctx_ids is not None else 0

        # Trim from the left if over the window, but never drop sentence tokens.
        if full_ids.shape[1] > 1024:
            drop = full_ids.shape[1] - 1024
            full_ids = full_ids[:, drop:]
            n_ctx = max(0, n_ctx - drop)

        labels = full_ids.clone()
        if n_ctx > 0:
            labels[:, :n_ctx] = -100  # ignore context tokens in the loss
        n_target = int((labels != -100).sum()) - (1 if n_ctx == 0 else 0)

        if full_ids.shape[1] < 2 or n_target < 1:
            results.append((s, float("nan"), 0))
            running = (running + " " + s).strip()
            continue

        out = model(full_ids, labels=labels)
        results.append((s, float(out.loss), n_target))
        running = (running + " " + s).strip()
        # Cap running context length so the next tokenization stays bounded.
        rids = tok(running, return_tensors="pt").input_ids
        if rids.shape[1] > ctx_tokens:
            running = tok.decode(rids[0, -ctx_tokens:])
    return results


def _stdev(xs):
    xs = [x for x in xs if not math.isnan(x)]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _mean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def analyze(text: str, model_name: str = "gpt2", in_context: bool = True) -> dict:
    prose = strip_non_prose(text)
    sentences = split_sentences(prose)

    per_sentence = []
    if in_context:
        scored = incontext_sentence_nll(sentences, model_name)
        for s, nll, n in scored:
            per_sentence.append({
                "sentence": s,
                "perplexity": (float("nan") if math.isnan(nll) else round(math.exp(nll), 2)),
                "mean_nll": (float("nan") if math.isnan(nll) else round(nll, 4)),
                "tokens": n,
                "words": word_count(s),
            })
    else:
        for s in sentences:
            nll, n = text_nll(s, model_name)
            per_sentence.append({
                "sentence": s,
                "perplexity": (float("nan") if math.isnan(nll) else round(math.exp(nll), 2)),
                "mean_nll": (float("nan") if math.isnan(nll) else round(nll, 4)),
                "tokens": n,
                "words": word_count(s),
            })

    ppls = [r["perplexity"] for r in per_sentence]
    nlls = [r["mean_nll"] for r in per_sentence]
    doc_ppl = perplexity(prose, model_name)

    return {
        "model": model_name,
        "doc_perplexity": round(doc_ppl, 2),
        "sentence_ppl_mean": round(_mean(ppls), 2),
        "sentence_ppl_median": round(sorted([p for p in ppls if not math.isnan(p)])[len([p for p in ppls if not math.isnan(p)]) // 2], 2) if any(not math.isnan(p) for p in ppls) else float("nan"),
        # Perplexity-burstiness — the variance axis GPTZero scores. Higher = more human.
        "ppl_burstiness": round(_stdev(ppls), 2),
        "nll_burstiness": round(_stdev(nlls), 4),
        "n_sentences": len(sentences),
        "per_sentence": per_sentence,
    }


def _print_report(result: dict, top: int):
    print(f"# perplexity.py — model: {result['model']}")
    print(f"# doc perplexity: {result['doc_perplexity']}   (lower = more AI-like)")
    print(f"# sentence ppl  : mean {result['sentence_ppl_mean']}  median {result['sentence_ppl_median']}")
    print(f"# ppl burstiness: {result['ppl_burstiness']}   (stdev of sentence perplexity; higher = more human)")
    print(f"# sentences     : {result['n_sentences']}")
    print("#")
    ranked = sorted(
        [r for r in result["per_sentence"] if not (isinstance(r["perplexity"], float) and math.isnan(r["perplexity"]))],
        key=lambda r: r["perplexity"],
    )
    print(f"# LOWEST-perplexity sentences (these are what a detector flags as 'most AI'):")
    for r in ranked[:top]:
        s = r["sentence"]
        s = (s[:88] + "…") if len(s) > 89 else s
        print(f"  ppl {r['perplexity']:>7}  ({r['words']}w)  {s}")
    print(f"#")
    print(f"# HIGHEST-perplexity sentences (most human-looking):")
    for r in ranked[-3:]:
        s = r["sentence"]
        s = (s[:88] + "…") if len(s) > 89 else s
        print(f"  ppl {r['perplexity']:>7}  ({r['words']}w)  {s}")


def main():
    ap = argparse.ArgumentParser(description="GPT-2 perplexity meter for the humanizer skill.")
    ap.add_argument("textfile", nargs="?", help="Path to text file. Reads stdin if omitted.")
    ap.add_argument("--model", default="gpt2", help="gpt2 (default, faithful) or distilgpt2 (faster).")
    ap.add_argument("--sentence", help="Score a single sentence/string and exit.")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON (for the iteration loop).")
    ap.add_argument("--top", type=int, default=8, help="How many lowest-ppl sentences to list.")
    ap.add_argument("--standalone", action="store_true", help="Score sentences in isolation (default scores in-context).")
    args = ap.parse_args()

    if args.sentence:
        ppl = perplexity(args.sentence, args.model)
        if args.json:
            print(json.dumps({"sentence": args.sentence, "perplexity": round(ppl, 2)}))
        else:
            print(f"perplexity: {ppl:.2f}   model: {args.model}")
        return

    if args.textfile:
        with open(args.textfile, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    result = analyze(text, args.model, in_context=not args.standalone)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result, args.top)


if __name__ == "__main__":
    main()
