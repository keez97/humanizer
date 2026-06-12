#!/usr/bin/env python3
"""
humanizer/binoculars.py — Binoculars AI-text detector (the iteration-loop oracle)

Why this and not raw perplexity: single-model perplexity is confounded in
number-heavy genres (finance, data). A `$320m` figure is unpredictable to ANY
model, so it inflates perplexity regardless of who wrote the text. Binoculars
(Hans et al., 2024, arXiv:2401.12070) fixes this by dividing a text's
log-perplexity under an *observer* model by its *cross-perplexity* between the
observer and a sibling *performer* model. Content that is surprising to both
models cancels in the ratio, isolating the signal that actually separates human
from machine: how predictable the text is *relative to* how much two related
models agree about it.

    score(s) = logPPL_observer(s) / X-PPL(observer, performer, s)

LOW score  -> machine-generated (AI text is predictable relative to the baseline)
HIGH score -> human-written

Default model pair (small, open, ~1GB each, share a tokenizer):
  observer  = Qwen/Qwen2.5-0.5B            (base)
  performer = Qwen/Qwen2.5-0.5B-Instruct   (chat finetune)

Requires torch + transformers (skill .venv). Usage:
  .venv/bin/python binoculars.py <file> [--json] [--top N]
  .venv/bin/python binoculars.py --calibrate fileA.md fileB.md ...
  cat file.txt | .venv/bin/python binoculars.py
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import strip_non_prose, split_sentences, word_count  # noqa: E402

OBSERVER = "Qwen/Qwen2.5-0.5B"
PERFORMER = "Qwen/Qwen2.5-0.5B-Instruct"

# Calibrated for the Qwen-0.5B pair on the humanizer calibration set (see
# --calibrate). Texts at or below this read as machine-generated. The Falcon
# pair in the paper optimizes near 0.901; the Qwen pair sits lower, so this is
# set empirically, not copied from the paper.
DEFAULT_THRESHOLD = 0.90

_PAIR = None


def _load_pair(observer=OBSERVER, performer=PERFORMER):
    global _PAIR
    if _PAIR is not None:
        return _PAIR
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(observer)
    m_obs = AutoModelForCausalLM.from_pretrained(observer, torch_dtype=torch.float32).eval()
    m_perf = AutoModelForCausalLM.from_pretrained(performer, torch_dtype=torch.float32).eval()
    torch.set_grad_enabled(False)
    _PAIR = (tok, m_obs, m_perf, torch)
    return _PAIR


def _token_scores(text, observer=OBSERVER, performer=PERFORMER):
    """Return (offsets, nll, xent) per predicted token for the full text.

    nll[i]  = observer's negative log-likelihood (nats) of predicting token i+1
    xent[i] = cross-entropy H(performer_dist, observer_dist) at position i (nats)
    offsets[i] = char span of the *predicted* token (token i+1) in `text`
    """
    tok, m_obs, m_perf, torch = _load_pair(observer, performer)
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True,
              truncation=True, max_length=2048)
    ids = enc.input_ids
    offsets = enc["offset_mapping"][0].tolist()
    if ids.shape[1] < 2:
        return [], None, None, torch

    logits_obs = m_obs(ids).logits[0]      # [n, V]
    logits_perf = m_perf(ids).logits[0]    # [n, V]

    # Positions 0..n-2 predict tokens 1..n-1.
    lo = logits_obs[:-1]                    # [n-1, V]
    lp = logits_perf[:-1]                   # [n-1, V]
    targets = ids[0, 1:]                    # [n-1]

    logprobs_obs = torch.log_softmax(lo, dim=-1)
    nll = -logprobs_obs[range(lo.shape[0]), targets]            # [n-1]

    probs_perf = torch.softmax(lp, dim=-1)
    xent = -(probs_perf * logprobs_obs).sum(dim=-1)            # [n-1]

    pred_offsets = offsets[1:]             # char span of each predicted token
    return pred_offsets, nll, xent, torch


def binoculars_score(text, observer=OBSERVER, performer=PERFORMER):
    """Document-level Binoculars score. Lower = more machine-like."""
    offsets, nll, xent, torch = _token_scores(text, observer, performer)
    if nll is None or nll.numel() == 0:
        return float("nan")
    return float(nll.mean() / xent.mean())


def _sentence_spans(prose, sentences):
    """Locate each sentence's [start,end) char span in prose, scanning in order."""
    spans = []
    cursor = 0
    for s in sentences:
        idx = prose.find(s, cursor)
        if idx == -1:
            idx = prose.find(s[:20], cursor)  # fall back to a prefix match
            if idx == -1:
                spans.append((cursor, cursor))
                continue
        spans.append((idx, idx + len(s)))
        cursor = idx + len(s)
    return spans


def analyze(text, observer=OBSERVER, performer=PERFORMER):
    prose = strip_non_prose(text)
    sentences = split_sentences(prose)
    offsets, nll, xent, torch = _token_scores(prose, observer, performer)

    result = {
        "observer": observer,
        "performer": performer,
        "doc_score": float("nan"),
        "threshold": DEFAULT_THRESHOLD,
        "verdict": "n/a",
        "n_sentences": len(sentences),
        "per_sentence": [],
    }
    if nll is None or nll.numel() == 0:
        return result

    doc = float(nll.mean() / xent.mean())
    result["doc_score"] = round(doc, 4)
    result["verdict"] = "MACHINE" if doc <= DEFAULT_THRESHOLD else "HUMAN"

    # Attribute each predicted token to a sentence and aggregate.
    spans = _sentence_spans(prose, sentences)
    nll_l = nll.tolist()
    xent_l = xent.tolist()
    sums = [[0.0, 0.0, 0] for _ in sentences]  # nll_sum, xent_sum, count
    for k, (cs, ce) in enumerate(offsets):
        # find sentence containing char start cs
        for si, (a, b) in enumerate(spans):
            if a <= cs < b:
                sums[si][0] += nll_l[k]
                sums[si][1] += xent_l[k]
                sums[si][2] += 1
                break

    per = []
    for s, (nsum, xsum, cnt) in zip(sentences, sums):
        sc = (nsum / xsum) if xsum > 0 and cnt > 0 else float("nan")
        per.append({
            "sentence": s,
            "score": (round(sc, 4) if sc == sc else float("nan")),
            "tokens": cnt,
            "words": word_count(s),
        })
    result["per_sentence"] = per
    return result


def _print_report(r, top):
    print(f"# binoculars.py — {r['observer'].split('/')[-1]} / {r['performer'].split('/')[-1]}")
    print(f"# DOC SCORE: {r['doc_score']}   threshold {r['threshold']}   -> {r['verdict']}")
    print(f"#   (lower = more machine-like; raise this number to look more human)")
    print(f"# sentences: {r['n_sentences']}")
    print("#")
    rows = [x for x in r["per_sentence"] if x["score"] == x["score"]]
    rows.sort(key=lambda x: x["score"])
    print("# MOST machine-like sentences (lowest score — fix these first):")
    for x in rows[:top]:
        s = x["sentence"]; s = (s[:78] + "…") if len(s) > 79 else s
        print(f"  {x['score']:>8}  ({x['words']}w)  {s}")
    print("#")
    print("# MOST human-like sentences (highest score):")
    for x in rows[-3:]:
        s = x["sentence"]; s = (s[:78] + "…") if len(s) > 79 else s
        print(f"  {x['score']:>8}  ({x['words']}w)  {s}")


def main():
    ap = argparse.ArgumentParser(description="Binoculars AI-text detector for the humanizer skill.")
    ap.add_argument("textfile", nargs="?")
    ap.add_argument("--observer", default=OBSERVER)
    ap.add_argument("--performer", default=PERFORMER)
    ap.add_argument("--sentence", help="Score a single string and exit.")
    ap.add_argument("--calibrate", nargs="+", help="Score several files and print a comparison table.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    if args.sentence:
        sc = binoculars_score(args.sentence, args.observer, args.performer)
        print(json.dumps({"sentence": args.sentence, "score": round(sc, 4)}) if args.json
              else f"binoculars score: {sc:.4f}")
        return

    if args.calibrate:
        print(f"# calibration — {args.observer.split('/')[-1]} / {args.performer.split('/')[-1]}")
        print(f"# {'file':<28} {'doc_score':>10}   verdict @ {DEFAULT_THRESHOLD}")
        for f in args.calibrate:
            with open(f, "r", encoding="utf-8") as fh:
                txt = fh.read()
            sc = binoculars_score(strip_non_prose(txt), args.observer, args.performer)
            verdict = "MACHINE" if sc <= DEFAULT_THRESHOLD else "HUMAN"
            print(f"  {os.path.basename(f):<28} {sc:>10.4f}   {verdict}")
        return

    text = open(args.textfile, encoding="utf-8").read() if args.textfile else sys.stdin.read()
    r = analyze(text, args.observer, args.performer)
    print(json.dumps(r, indent=2) if args.json else None) if args.json else _print_report(r, args.top)


if __name__ == "__main__":
    main()
