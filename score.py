#!/usr/bin/env python3
"""
humanizer/score.py — Humanizer Self-Scoring Battery
Analyzes prose for AI-detection tells and scores against the check battery
defined in the Humanizer Skill design doc (§3 / Self-Scoring Battery).

Checks #11 (colon-restatement) and #13 (perplexity-anchor coverage) are
MODEL-JUDGMENT checks and are intentionally omitted from this script;
the skill routes them through a model self-review pass.

Usage:
  python3 score.py <textfile> [--mode full|light]
  cat file.txt | python3 score.py --mode light

Interface:
  Each check prints: "= <name> | <value> | <threshold> | GATE(<HARD|soft>) | <PASS|FAIL|SKIPPED (light)>"
  Final two lines: "MODE: <full|light>" and "RESULT: PASS" or "RESULT: FAIL"
  Exit code: 0 = PASS, 1 = FAIL
"""

import re
import sys
import math
import argparse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANNED_VOCAB = {
    "delve", "tapestry", "robust", "leverage", "pivotal", "intricate",
    "foster", "navigate", "landscape", "underscore", "realm", "testament",
    "crucial", "comprehensive", "multifaceted", "nuanced", "seamless",
    "vibrant", "harness", "beacon", "paramount", "myriad", "plethora",
    "garner", "bolster", "encompass", "intricacies", "holistic", "synergy",
}

SIGNPOST_WORDS = [
    r"\bmoreover\b", r"\bfurthermore\b", r"\bnevertheless\b",
    r"\bnotwithstanding\b", r"\bhenceforth\b", r"\btherefore\b",
    r"\bthus\b", r"\bconsequently\b", r"\bsubsequently\b",
    r"\badditionally\b", r"\bspecifically\b", r"\bnotably\b",
    r"\bsignificantly\b", r"\bimportantly\b", r"\bindeed\b",
    r"\bultimately\b", r"\baccordingly\b", r"\boverall\b",
    r"\bto summarize\b", r"\bto conclude\b",
    r"\bit is worth noting\b", r"\bit should be noted\b",
    r"\bof course\b",
]

# Openers that get a dedicated zero-tolerance sub-check
BAD_OPENERS = [
    r"^in conclusion[,\s]",
    r"^in summary[,\s]",
    r"^in today'?s world[,\s]",
]

HEDGE_WORDS = [
    r"\bmight\b", r"\bmay\b", r"\bcould\b", r"\bperhaps\b",
    r"\bpossibly\b", r"\bpotentially\b", r"\bseems?\b", r"\bappears?\b",
    r"\bsuggests?\b", r"\bindicates?\b", r"\btends?\b", r"\bgenerally\b",
    r"\btypically\b", r"\busually\b", r"\boften\b", r"\bsomewhat\b",
    r"\brelatively\b",
]

DOUBLE_HEDGE_PAIRS = [
    (r"\bmay potentially\b", "may potentially"),
    (r"\bmight possibly\b", "might possibly"),
    (r"\bcould potentially\b", "could potentially"),
    (r"\bmight potentially\b", "might potentially"),
    (r"\bmay possibly\b", "may possibly"),
    (r"\bcould possibly\b", "could possibly"),
    (r"\bperhaps possibly\b", "perhaps possibly"),
    (r"\bseems? to suggest\b", "seems to suggest"),
]

# Common English abbreviations to guard against false sentence splits
ABBREV_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|et al|viz|"
    r"U\.S|U\.K|approx|dept|vol|ed|pp|fig|sect|eq|no)\.",
    re.IGNORECASE,
)

CONTRACTION_RE = re.compile(
    r"\b\w+n't\b"                        # don't, can't, won't, ...
    r"|\b\w+'(?:s|re|ll|ve|d|m)\b"       # it's, they're, I'll, I've, I'd, I'm
    r"|\blet's\b"
    r"|\bwon't\b"
    r"|\bshan't\b",
    re.IGNORECASE,
)

NEGATION_REVERSAL_RE = re.compile(
    # --- inline forms ---
    r"\bnot just .{1,60} but\b"
    r"|\b\w[\w\s]{0,30} is not .{1,60},? it is\b"
    r"|\b\w[\w\s]{0,30} are not .{1,60},? they are\b"
    # --- cross-sentence predicate-nominal reversal (B4): ---
    #   "That isn't a LAPSE. It might be B."  /  "That's not a footnote. It's B."
    #   negate "a/the/just <noun>", end the sentence, then a pronoun re-asserts the positive.
    #   Article list kept tight (a|an|the|just|merely|simply|only) to avoid firing on
    #   ordinary "I don't really know. It's complicated." style sequences.
    r"|(?:n't|\bnot)\s+(?:a|an|the|just|merely|simply|only)\b[^.!?]{0,60}[.!?]+\s+"
    r"(?:it|that|this|they|instead|rather)\b(?:'s|'re|\s+(?:is|are|was|were|might|may|should))"
    # --- cross-sentence "X doesn't VERB like A. It VERBs like B." ---
    r"|(?:n't|\bnot)\s+\w+\s+like\b[^.!?]{0,50}[.!?]+\s+(?:it|they)\b[^.!?]{0,25}\blike\b",
    re.IGNORECASE,
)

# Approximate tricolon: "X, Y, and Z" or "X, Y and Z"
TRICOLON_RE = re.compile(
    r"\b\w+,\s+\w+,?\s+and\s+\w+\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def strip_non_prose(text: str) -> str:
    """
    Strip markdown headings, table rows, fenced code blocks, and blank lines
    that are purely structural.  Returns the reduced text preserving prose.
    """
    lines = text.splitlines()
    output = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        # Toggle fenced code
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Drop markdown headings
        if stripped.startswith("#"):
            continue
        # Drop table rows (lines starting with |)
        if stripped.startswith("|"):
            continue
        # Drop horizontal rules
        if re.match(r"^[-*_]{3,}$", stripped):
            continue
        output.append(line)
    return "\n".join(output)


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using [.!?]+ as delimiters, with basic
    abbreviation guarding so 'U.S. Army' doesn't split mid-sentence.
    """
    # Temporarily mask abbreviations by replacing dots with a sentinel
    masked = ABBREV_PATTERN.sub(lambda m: m.group(0).replace(".", "\x00"), text)

    # Split on sentence-ending punctuation followed by whitespace/EOL
    parts = re.split(r"(?<=[.!?])\s+", masked)

    # Restore sentinels and clean
    sentences = []
    for part in parts:
        restored = part.replace("\x00", ".")
        cleaned = restored.strip()
        if cleaned:
            sentences.append(cleaned)
    return sentences


# ---------------------------------------------------------------------------
# Paragraph splitting
# ---------------------------------------------------------------------------

def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; return non-empty paragraph strings."""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


# ---------------------------------------------------------------------------
# Word count helpers
# ---------------------------------------------------------------------------

def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def sentence_word_counts(sentences: list[str]) -> list[int]:
    return [word_count(s) for s in sentences]


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def population_stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def cv(values: list[float]) -> float:
    """Coefficient of variation = population stdev / mean."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    return population_stdev(values) / mean


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------

def check_cv(sentences: list[str]) -> tuple[float, float, bool]:
    """#1 — Sentence-length CV >= 0.45 (HARD)"""
    counts = sentence_word_counts(sentences)
    if len(counts) < 3:
        # Too short to measure; default pass to avoid false-failing tiny excerpts
        return (0.0, 0.45, True)
    value = cv(counts)
    return (round(value, 3), 0.45, value >= 0.45)


def check_short_sentences(sentences: list[str], total_words: int) -> tuple[str, str, bool]:
    """#2 — >= 2 sub-10-word sentences per 400 words (HARD)"""
    required = max(1, math.ceil(total_words / 400 * 2))
    count = sum(1 for s in sentences if word_count(s) < 10)
    threshold_str = f">={required}/400w-scaled"
    return (str(count), threshold_str, count >= required)


def check_long_sentences(sentences: list[str], total_words: int) -> tuple[str, str, bool]:
    """#3 — >= 1 sentence >=30 words per 400 words (soft)"""
    required = max(1, math.ceil(total_words / 400 * 1))
    count = sum(1 for s in sentences if word_count(s) >= 30)
    threshold_str = f">={required}/400w-scaled"
    return (str(count), threshold_str, count >= required)


def check_paragraph_ratio(paragraphs: list[str]) -> tuple[str, str, bool]:
    """#4 — Paragraph max/min word ratio >= 2.5 (HARD)"""
    if len(paragraphs) < 2:
        return ("n/a", ">=2.5x", True)
    counts = [word_count(p) for p in paragraphs if word_count(p) > 0]
    if len(counts) < 2:
        return ("n/a", ">=2.5x", True)
    max_c = max(counts)
    min_c = min(counts)
    if min_c == 0:
        return ("inf", ">=2.5x", True)
    ratio = max_c / min_c
    return (f"{ratio:.2f}x", ">=2.5x", ratio >= 2.5)


def check_paragraph_clustering(paragraphs: list[str]) -> tuple[str, str, bool]:
    """#5 — No 3 consecutive paragraphs within 15 words of each other (soft)"""
    if len(paragraphs) < 3:
        return ("0", "0 clusters", True)
    counts = [word_count(p) for p in paragraphs]
    clusters = 0
    for i in range(len(counts) - 2):
        a, b, c = counts[i], counts[i + 1], counts[i + 2]
        if abs(a - b) <= 15 and abs(b - c) <= 15 and abs(a - c) <= 15:
            clusters += 1
    return (str(clusters), "0 clusters", clusters == 0)


def check_banned_vocab(text: str) -> tuple[str, str, bool, list[str]]:
    """#6 — Banned vocab: 0 occurrences (HARD)"""
    text_lower = text.lower()
    found = []
    for word in BANNED_VOCAB:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, text_lower):
            found.append(word)
    found.sort()
    value_str = str(len(found)) + (f" ({', '.join(found)})" if found else "")
    return (value_str, "0 hits", len(found) == 0, found)


def check_em_dash(text: str) -> tuple[str, str, bool]:
    """#7 — Em dashes: 0 (HARD)"""
    # Unicode em-dash U+2014, and also -- double-hyphen used as em-dash
    count = text.count("—") + len(re.findall(r"(?<!\-)\-\-(?!\-)", text))
    return (str(count), "0", count == 0)


def check_signpost_density(text: str, total_words: int) -> tuple[str, str, bool]:
    """#8 — Signpost density <= 1/300w AND 0 bad openers (HARD)"""
    text_lower = text.lower()
    signpost_count = 0
    for pattern in SIGNPOST_WORDS:
        signpost_count += len(re.findall(pattern, text_lower))

    allowed = max(0, total_words / 300)
    # Check bad openers (per paragraph)
    paragraphs = split_paragraphs(text_lower)
    bad_opener_count = 0
    for para in paragraphs:
        first_words = para.strip()
        for opener_re in BAD_OPENERS:
            if re.match(opener_re, first_words, re.IGNORECASE):
                bad_opener_count += 1
                break

    density_ok = signpost_count <= allowed
    openers_ok = bad_opener_count == 0
    passed = density_ok and openers_ok

    threshold_str = f"<={allowed:.1f}/300w-scaled, 0 bad-openers"
    value_str = f"{signpost_count} signposts, {bad_opener_count} bad-openers"
    return (value_str, threshold_str, passed)


def check_tricolon(text: str, total_words: int) -> tuple[str, str, bool]:
    """#9 — Tricolon density <= 1/200w (soft)"""
    matches = TRICOLON_RE.findall(text)
    count = len(matches)
    allowed = max(1, total_words / 200)
    return (str(count), f"<={allowed:.1f}/200w-scaled", count <= allowed)


def check_negation_reversal(text: str, total_words: int) -> tuple[str, str, bool]:
    """#10 — Negation-reversal <= 1/500w (HARD)"""
    count = len(NEGATION_REVERSAL_RE.findall(text))
    allowed = max(1, total_words / 500)
    return (str(count), f"<={allowed:.1f}/500w-scaled", count <= allowed)


def check_hedge_density(text: str, total_words: int) -> tuple[str, str, bool]:
    """#12 — Hedge density <= 3/200w AND no double-hedges (soft)"""
    text_lower = text.lower()
    hedge_count = 0
    for pattern in HEDGE_WORDS:
        hedge_count += len(re.findall(pattern, text_lower))

    allowed = max(3, total_words / 200 * 3)
    density_ok = hedge_count <= allowed

    double_hedge_found = []
    for dh_re, label in DOUBLE_HEDGE_PAIRS:
        if re.search(dh_re, text_lower):
            double_hedge_found.append(label)

    double_ok = len(double_hedge_found) == 0
    passed = density_ok and double_ok

    threshold_str = f"<={allowed:.0f}/200w-scaled, no double-hedges"
    value_str = (
        f"{hedge_count} hedges"
        + (f", double-hedges: {', '.join(double_hedge_found)}" if double_hedge_found else "")
    )
    return (value_str, threshold_str, passed)


def check_contractions(text: str, total_words: int) -> tuple[str, str, bool]:
    """#14 — Contractions >= 1/200w (alibi presence) (HARD)"""
    count = len(CONTRACTION_RE.findall(text))
    required = max(1, math.ceil(total_words / 200))
    return (str(count), f">={required}/200w-scaled", count >= required)


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def fmt_line(name: str, value: str, threshold: str, gate: str, result: str) -> str:
    return f"= {name:<38} | {value:<30} | {threshold:<28} | GATE({gate:<4}) | {result}"


def skipped_line(name: str, gate: str) -> str:
    return f"= {name:<38} | {'SKIPPED (light)':<30} | {'—':<28} | GATE({gate:<4}) | SKIPPED (light)"


# ---------------------------------------------------------------------------
# Main scoring logic
# ---------------------------------------------------------------------------

def score(text: str, mode: str) -> int:
    """
    Run the battery and print the per-check report.
    Returns 0 for PASS, 1 for FAIL.
    """
    prose = strip_non_prose(text)

    if not prose.strip():
        print("ERROR: no prose content found after stripping non-prose markup.")
        return 1

    sentences = split_sentences(prose)
    paragraphs = split_paragraphs(prose)
    total_words = word_count(prose)

    print(f"# humanizer score.py — mode: {mode}")
    print(f"# prose words: {total_words}  |  sentences: {len(sentences)}  |  paragraphs: {len(paragraphs)}")
    print(f"# Checks #11 (colon-restatement) and #13 (perplexity-anchor) are MODEL-JUDGMENT — intentionally omitted.")
    print("#")

    hard_fails = 0
    soft_fails = 0
    lines = []

    def record(name, value, threshold, gate_type, passed):
        nonlocal hard_fails, soft_fails
        result = "PASS" if passed else "FAIL"
        lines.append(fmt_line(name, value, threshold, gate_type, result))
        if not passed:
            if gate_type == "HARD":
                hard_fails += 1
            else:
                soft_fails += 1

    def skip(name, gate_type):
        lines.append(skipped_line(name, gate_type))

    # --- Full-mode-only checks ---
    if mode == "full":
        # #1 CV
        cv_val, cv_thresh, cv_ok = check_cv(sentences)
        record("cv-sentence-length", str(cv_val), f">={cv_thresh}", "HARD", cv_ok)

        # #2 short sentences
        s_val, s_thresh, s_ok = check_short_sentences(sentences, total_words)
        record("short-sentences-<10w", s_val, s_thresh, "HARD", s_ok)

        # #3 long sentences
        l_val, l_thresh, l_ok = check_long_sentences(sentences, total_words)
        record("long-sentences->=30w", l_val, l_thresh, "soft", l_ok)

        # #4 paragraph ratio
        pr_val, pr_thresh, pr_ok = check_paragraph_ratio(paragraphs)
        record("paragraph-max-min-ratio", pr_val, pr_thresh, "HARD", pr_ok)

        # #5 paragraph clustering
        pc_val, pc_thresh, pc_ok = check_paragraph_clustering(paragraphs)
        record("paragraph-clustering", pc_val, pc_thresh, "soft", pc_ok)
    else:
        # light mode: skip these
        skip("cv-sentence-length", "HARD")
        skip("short-sentences-<10w", "HARD")
        skip("long-sentences->=30w", "soft")
        skip("paragraph-max-min-ratio", "HARD")
        skip("paragraph-clustering", "soft")

    # --- Always active ---
    # #6 banned vocab
    bv_val, bv_thresh, bv_ok, _ = check_banned_vocab(prose)
    record("banned-vocab", bv_val, bv_thresh, "HARD", bv_ok)

    # #7 em-dash
    em_val, em_thresh, em_ok = check_em_dash(prose)
    record("em-dash", em_val, em_thresh, "HARD", em_ok)

    # #8 signpost density
    sp_val, sp_thresh, sp_ok = check_signpost_density(prose, total_words)
    record("signpost-density", sp_val, sp_thresh, "HARD", sp_ok)

    # --- Full-mode-only (post-#8) ---
    if mode == "full":
        # #9 tricolon
        tc_val, tc_thresh, tc_ok = check_tricolon(prose, total_words)
        record("tricolon-density", tc_val, tc_thresh, "soft", tc_ok)

        # #10 negation-reversal
        nr_val, nr_thresh, nr_ok = check_negation_reversal(prose, total_words)
        record("negation-reversal", nr_val, nr_thresh, "HARD", nr_ok)

        # #11 colon-restatement — MODEL-JUDGMENT, skip
        lines.append(
            fmt_line(
                "colon-restatement-#11",
                "MODEL-JUDGMENT",
                "<=1/600w",
                "soft",
                "SKIPPED",
            ).replace("| PASS", "| SKIPPED").replace("| FAIL", "| SKIPPED")
        )
        # Rewrite cleanly:
        lines[-1] = (
            f"= {'colon-restatement-#11':<38} | {'MODEL-JUDGMENT':<30} | {'<=1/600w':<28} | GATE({'soft':<4}) | SKIPPED (model)"
        )

        # #12 hedge density
        hd_val, hd_thresh, hd_ok = check_hedge_density(prose, total_words)
        record("hedge-density", hd_val, hd_thresh, "soft", hd_ok)

        # #13 perplexity-anchor — MODEL-JUDGMENT, skip
        lines.append(
            f"= {'perplexity-anchor-#13':<38} | {'MODEL-JUDGMENT':<30} | {'>=1/paragraph':<28} | GATE({'soft':<4}) | SKIPPED (model)"
        )

        # #14 contractions
        ct_val, ct_thresh, ct_ok = check_contractions(prose, total_words)
        record("contractions-alibi", ct_val, ct_thresh, "HARD", ct_ok)
    else:
        # light mode: skip #9-#14 except already done #6-#8
        skip("tricolon-density", "soft")
        skip("negation-reversal", "HARD")
        lines.append(
            f"= {'colon-restatement-#11':<38} | {'SKIPPED (light)':<30} | {'—':<28} | GATE({'soft':<4}) | SKIPPED (light)"
        )
        skip("hedge-density", "soft")
        lines.append(
            f"= {'perplexity-anchor-#13':<38} | {'SKIPPED (light)':<30} | {'—':<28} | GATE({'soft':<4}) | SKIPPED (light)"
        )
        skip("contractions-alibi", "HARD")

    for line in lines:
        print(line)

    print()
    print(f"MODE: {mode}")

    # Ship-eligibility: ALL HARD pass AND <= 2 soft fail
    if mode == "light":
        # Only HARD gates #6/#7/#8 are active; no soft gate counting
        passed = hard_fails == 0
    else:
        passed = hard_fails == 0 and soft_fails <= 2

    result_str = "PASS" if passed else "FAIL"
    if not passed:
        reasons = []
        if hard_fails > 0:
            reasons.append(f"{hard_fails} HARD gate(s) failed")
        if soft_fails > 2:
            reasons.append(f"{soft_fails} soft gates failed (limit 2)")
        print(f"RESULT: {result_str}  [{'; '.join(reasons)}]")
    else:
        print(f"RESULT: {result_str}")

    return 0 if passed else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Humanizer Self-Scoring Battery.\n\n"
            "Analyzes PROSE for AI-detection tells. Caller is responsible for "
            "stripping tables/code/references/headings before piping; the script "
            "also drops markdown headings, table rows (|...|), and fenced code "
            "blocks as a courtesy.\n\n"
            "Checks #11 (colon-restatement) and #13 (perplexity-anchor coverage) "
            "are MODEL-JUDGMENT checks — intentionally omitted from this script; "
            "the skill routes them through a model self-review pass.\n\n"
            "Output format (per check):\n"
            "  = check-name | value | threshold | GATE(HARD/soft) | PASS/FAIL\n\n"
            "Final two lines: 'MODE: <full|light>' and 'RESULT: PASS' or 'RESULT: FAIL'\n"
            "Exit code: 0 = PASS, 1 = FAIL\n\n"
            "Ship-eligibility: ALL HARD gates pass AND <=2 soft gates fail.\n"
            "--mode light activates ONLY checks #6 (banned-vocab), #7 (em-dash), "
            "#8 (signpost-density). All other checks are SKIPPED."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "textfile",
        nargs="?",
        help="Path to text file. Reads from stdin if omitted.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "light"],
        default="full",
        help="Scoring mode: 'full' (all checks) or 'light' (#6/#7/#8 only). Default: full.",
    )
    args = parser.parse_args()

    if args.textfile:
        try:
            with open(args.textfile, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"ERROR: file not found: {args.textfile}", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = sys.stdin.read()

    sys.exit(score(text, args.mode))


if __name__ == "__main__":
    main()
