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
import os


# ---------------------------------------------------------------------------
# Constants (hardcoded defaults — unchanged when --config is absent)
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

# ---------------------------------------------------------------------------
# Config loader — optional --config <path> support
# ---------------------------------------------------------------------------
# CONTRACT:
#   Absent → byte-for-byte identical behavior to today (hardcoded defaults used).
#   Present → loads YAML/JSON config; config may EXTEND/OVERRIDE hardcoded defaults
#             but CANNOT weaken strictness below current levels.
#   Missing/malformed config file → warn to stderr, fall back to hardcoded defaults.
#   score.py is PROJECT-AGNOSTIC: it accepts a path from the caller; it never
#   calls resolve-standard.sh or reads any Historiai-specific paths.
# ---------------------------------------------------------------------------

def _load_config(config_path: str) -> dict:
    """
    Load a YAML or JSON config file and return it as a dict.
    Returns {} (empty dict) on any error, after printing a warning to stderr.
    Uses PyYAML if available, else falls back to json (for JSON-subset configs).
    """
    if not os.path.isfile(config_path):
        print(
            f"humanizer/score.py: WARNING — config file not found: {config_path}; "
            "falling back to hardcoded defaults.",
            file=sys.stderr,
        )
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        print(
            f"humanizer/score.py: WARNING — could not read config file: {exc}; "
            "falling back to hardcoded defaults.",
            file=sys.stderr,
        )
        return {}

    # If the file is a markdown doc (starts with <!-- or #), extract the
    # fenced ```yaml block first before parsing. This handles compiled
    # standards docs like humanizer-instructions.md which embed the
    # machine-readable block inside a markdown file.
    stripped = raw.lstrip()
    if stripped.startswith("<!--") or stripped.startswith("#"):
        import re as _re
        yaml_match = _re.search(r"```yaml\n(.*?)\n```", raw, _re.DOTALL)
        if yaml_match:
            raw = yaml_match.group(1)
        else:
            print(
                f"humanizer/score.py: WARNING — config file looks like markdown but "
                "contains no ```yaml block; falling back to hardcoded defaults.",
                file=sys.stderr,
            )
            return {}

    # Try PyYAML first (handles YAML and JSON); fall back to stdlib json.
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw)
    except ImportError:
        try:
            import json
            data = json.loads(raw)
        except Exception as exc:
            print(
                f"humanizer/score.py: WARNING — config parse failed (yaml unavailable, json failed: {exc}); "
                "falling back to hardcoded defaults.",
                file=sys.stderr,
            )
            return {}
    except Exception as exc:
        print(
            f"humanizer/score.py: WARNING — config parse failed: {exc}; "
            "falling back to hardcoded defaults.",
            file=sys.stderr,
        )
        return {}

    if not isinstance(data, dict):
        print(
            f"humanizer/score.py: WARNING — config root is not a mapping (got {type(data).__name__}); "
            "falling back to hardcoded defaults.",
            file=sys.stderr,
        )
        return {}
    return data


def _apply_config(config: dict, mode: str = "light") -> None:
    """
    Apply config parameters to the module-level constants (mutates in-place).
    CONTRACT: config may only EXTEND or TIGHTEN defaults — it cannot:
      - Remove entries from BANNED_VOCAB (it can only add more)
      - Lower the em-dash count threshold (it is always 0 — config cannot raise it)
      - Reduce SIGNPOST_WORDS (only extend)
      - Reduce HEDGE_WORDS (only extend)
    These invariants prevent a config from weakening the scorer below current strictness.

    Primary schema — voice/house-style standard's surface_tells[] (the canonical form):
      surface_tells:
        - pattern: "transition_meta_commentary"
          examples: ["It is worth noting that", ...]
          scrub_in: [FULL, LIGHT]
        ...

      Each tell's examples[] entries are added to BANNED_VOCAB when the active
      scoring mode is in scrub_in. Mapping: FULL→"full", LIGHT→"light",
      NONE→never applied. A tell with scrub_in:[FULL] is only applied for mode=="full";
      a tell with scrub_in:[FULL,LIGHT] is applied for both modes.
      This is the primary way the voice standard drives the scorer.

    Secondary schema — explicit extend keys (still supported; for callers adding custom patterns):
      banned_vocab_extend: [word, ...]          — adds words to BANNED_VOCAB (no removes)
      signpost_words_extend: [pattern, ...]     — adds regex patterns to SIGNPOST_WORDS
      hedge_words_extend: [pattern, ...]        — adds regex patterns to HEDGE_WORDS
      bad_openers_extend: [pattern, ...]        — adds regex patterns to BAD_OPENERS
    """
    global BANNED_VOCAB, SIGNPOST_WORDS, HEDGE_WORDS, BAD_OPENERS

    # --- Primary schema: surface_tells[] from the voice standard ---
    # Map scoring mode strings to standard tier names.
    # "full" matches both FULL and LIGHT scrub_in tiers.
    # "light" matches only LIGHT scrub_in tier.
    _mode_tiers = {"full": {"FULL", "LIGHT"}, "light": {"LIGHT"}}
    active_tiers = _mode_tiers.get(mode, {"LIGHT"})

    surface_tells = config.get("surface_tells", [])
    if surface_tells and isinstance(surface_tells, list):
        for tell in surface_tells:
            if not isinstance(tell, dict):
                continue
            scrub_in = tell.get("scrub_in", [])
            if not isinstance(scrub_in, list):
                continue
            # Only apply this tell if the active mode's tiers intersect with scrub_in.
            if not active_tiers.intersection(set(scrub_in)):
                continue
            # Apply examples[] as literal banned phrases (added to BANNED_VOCAB as
            # lowercased multi-word phrases; check_banned_vocab uses word-boundary regex
            # for single words but multi-word phrases need substring search — handled below
            # via the _SURFACE_TELL_PHRASES set which uses substring matching).
            examples = tell.get("examples", [])
            if examples and isinstance(examples, list):
                for phrase in examples:
                    if isinstance(phrase, str) and phrase.strip():
                        _SURFACE_TELL_PHRASES.add(phrase.strip().lower())

    # --- Secondary schema: explicit extend keys (backward-compatible) ---
    # banned_vocab_extend: extend-only, no removes (hardcoded + configured = union)
    extend_vocab = config.get("banned_vocab_extend", [])
    if extend_vocab and isinstance(extend_vocab, list):
        for w in extend_vocab:
            if isinstance(w, str) and w.strip():
                BANNED_VOCAB.add(w.strip().lower())

    # signpost_words_extend: adds regex patterns
    extend_signpost = config.get("signpost_words_extend", [])
    if extend_signpost and isinstance(extend_signpost, list):
        for p in extend_signpost:
            if isinstance(p, str) and p.strip():
                SIGNPOST_WORDS.append(p.strip())

    # hedge_words_extend: adds regex patterns
    extend_hedge = config.get("hedge_words_extend", [])
    if extend_hedge and isinstance(extend_hedge, list):
        for p in extend_hedge:
            if isinstance(p, str) and p.strip():
                HEDGE_WORDS.append(p.strip())

    # bad_openers_extend: adds regex patterns for paragraph opener checks
    extend_openers = config.get("bad_openers_extend", [])
    if extend_openers and isinstance(extend_openers, list):
        for p in extend_openers:
            if isinstance(p, str) and p.strip():
                BAD_OPENERS.append(p.strip())


# Module-level set for surface-tell phrases loaded from config.
# Populated by _apply_config when --config is given; empty otherwise.
# Uses substring matching (not word-boundary regex) because phrases like
# "it is worth noting that" span multiple words and regex word-boundary
# doesn't apply cleanly to multi-word expressions.
_SURFACE_TELL_PHRASES: set = set()


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


def check_surface_tell_phrases(text: str) -> tuple[str, str, bool, list[str]]:
    """#6b — Surface-tell phrases from voice standard: 0 occurrences (HARD).
    Only active when _SURFACE_TELL_PHRASES is non-empty (i.e. --config was given
    and the standard's surface_tells contained examples for the active mode).
    Uses substring matching (case-insensitive) — multi-word phrases like
    'it is worth noting that' are not amenable to word-boundary regex.
    Returns passed=True (no-op) when _SURFACE_TELL_PHRASES is empty, so the
    check is invisible when no config is loaded (backward-compat preserved).
    """
    if not _SURFACE_TELL_PHRASES:
        return ("0", "0 hits", True, [])
    text_lower = text.lower()
    found = []
    for phrase in _SURFACE_TELL_PHRASES:
        if phrase in text_lower:
            found.append(phrase)
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

    # #6b surface-tell phrases from voice standard (no-op when config absent)
    st_val, st_thresh, st_ok, _ = check_surface_tell_phrases(prose)
    if _SURFACE_TELL_PHRASES:
        # Only emit the check row when the config actually loaded phrases.
        # Absent config → invisible (backward-compat: no new SKIPPED line in output).
        record("surface-tell-phrases", st_val, st_thresh, "HARD", st_ok)

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
            "#8 (signpost-density). All other checks are SKIPPED.\n\n"
            "--config <path> (optional): load a YAML/JSON config file to extend the\n"
            "  hardcoded defaults. Config may only ADD tells/vocab — it cannot remove\n"
            "  or weaken existing checks. Absent/missing/malformed config → falls back\n"
            "  to hardcoded defaults (never crashes; never weakens the scorer).\n"
            "  This script is PROJECT-AGNOSTIC: it reads the path you hand it."
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
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help=(
            "Optional path to a YAML/JSON config file that extends (but never weakens) "
            "the hardcoded scoring defaults. Absent → hardcoded defaults used unchanged. "
            "Missing/malformed → warning to stderr, fall back to hardcoded defaults."
        ),
    )
    args = parser.parse_args()

    # Apply config if provided — must happen before any scoring logic runs.
    # Pass mode so surface_tells are tier-filtered correctly before scoring.
    if args.config is not None:
        cfg = _load_config(args.config)
        if cfg:
            _apply_config(cfg, mode=args.mode)

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
