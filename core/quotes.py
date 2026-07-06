"""Locate Claude's evidence quotes inside the speech text.

Shared by build_data.py (computes the stored ``quote_match`` flag) and the
apps (highlight quote fragments in the displayed speeches). No streamlit
imports here.
"""

from __future__ import annotations

import re

NO_QUOTE_VALUES = {"", "no explicit statement found.", "none"}

# Length-preserving character substitutions (safe for index mapping).
_CHAR_MAP = str.maketrans({
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "–": "-", "—": "-",
})


def normalize_preserving_length(text: str) -> str:
    """Lowercase + straighten typography without changing string length."""
    return text.translate(_CHAR_MAP).lower()


def _normalize_for_match(text: str) -> str:
    text = normalize_preserving_length(text).replace("…", "...")
    return re.sub(r"\s+", " ", text).strip()


def quote_segments(evidence: str) -> list[str]:
    """Break an evidence string into the quote fragments it claims.

    Claude's evidence is often several quotes joined by ellipses or
    'and "..."', sometimes with trailing commentary after a dash. If the
    string contains double-quoted spans, those spans are the segments;
    otherwise split on ellipses.
    """
    ev = _normalize_for_match(evidence)
    quoted = re.findall(r'"([^"]+)"', ev)
    segments = quoted if quoted else re.split(r"\.\.\.|\[\.\.\.\]", ev)
    segments = [s.strip(" .;:-") for s in segments]
    return [s for s in segments if len(s) >= 20]


def is_no_quote(evidence: str) -> bool:
    return _normalize_for_match(evidence) in NO_QUOTE_VALUES


def quote_match(evidence: str, speeches_text: str) -> str | None:
    """None = no quote expected (zero-score sentinel).
    'found' = every quote fragment appears verbatim in the speeches;
    'partial' = some fragments appear; 'not_found' = none do."""
    if is_no_quote(evidence):
        return None
    hay = _normalize_for_match(speeches_text)
    segments = quote_segments(evidence)
    if not segments:
        return "found" if _normalize_for_match(evidence) in hay else "not_found"
    hits = sum(1 for s in segments if s in hay)
    if hits == len(segments):
        return "found"
    if hits > 0:
        return "partial"
    return "not_found"


def find_quote_ranges(speeches_text: str, evidences: list[str]) -> list[tuple[int, int]]:
    """Character ranges in ``speeches_text`` where quote fragments occur.

    Matching is done against a length-preserving normalization of the text,
    so ranges index directly into the original string. Fragments whose
    internal whitespace was re-flowed will not match here even if
    ``quote_match`` found them after whitespace collapsing; that is fine —
    highlighting is best-effort.
    """
    hay = normalize_preserving_length(speeches_text)
    ranges: list[tuple[int, int]] = []
    for evidence in evidences:
        if not evidence or is_no_quote(evidence):
            continue
        for segment in quote_segments(evidence):
            start = 0
            while True:
                idx = hay.find(segment, start)
                if idx < 0:
                    break
                ranges.append((idx, idx + len(segment)))
                start = idx + len(segment)

    if not ranges:
        return []
    ranges.sort()
    merged = [ranges[0]]
    for lo, hi in ranges[1:]:
        if lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return merged
