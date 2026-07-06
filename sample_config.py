"""Validation sample definition.

This file is the single place that defines WHICH meetings, decisions, and
members the human coders validate. To change the sample: edit this file,
rerun ``python build_data.py`` (on a machine with the source data), and
commit the regenerated ``data/`` files.
"""

# ---------------------------------------------------------------------------
# Static tools (position alignment + adoption contribution)
# The three meetings used for the old paper's human-coding validation;
# every scored speaker at each meeting.
# ---------------------------------------------------------------------------
STATIC_MEETINGS = {
    "19940816": "August 16, 1994 (Greenspan tightening cycle)",
    "20081216": "December 16, 2008 (Financial crisis ZLB)",
    "20110809": "August 9, 2011 (Calendar guidance introduced)",
}

# ---------------------------------------------------------------------------
# Dynamic tool (dynamic position alignment)
# Per decision: selected members coded at every meeting in the window,
# oldest first. "window" is "all" or "lastN" (N most recent pre-adoption
# meetings present in the Claude output).
# Members are stratified on Claude's score patterns: consistent supporters,
# consistent opponents, movers, and low/zero-signal members.
# ---------------------------------------------------------------------------
DYNAMIC_SAMPLE = [
    {
        "decision_ymd": "20081216",
        "decision_id": "d006",
        "short_name": "ZLB established (Dec 2008)",
        "members": ["YELLEN", "KOHN", "LACKER", "EVANS", "HOENIG", "WARSH"],
        "window": "all",  # 8 meetings: Dec 2007 - Oct 2008
    },
    {
        "decision_ymd": "20121212",
        "decision_id": "d003",
        "short_name": "Evans rule (Dec 2012)",
        "members": ["EVANS", "YELLEN", "KOCHERLAKOTA", "LACKER", "PLOSSER", "BERNANKE"],
        "window": "last8",  # Dec 2011 - Oct 2012 (full window is 10)
    },
    {
        "decision_ymd": "20151216",
        "decision_id": "d008",
        "short_name": "Liftoff (Dec 2015)",
        "members": ["GEORGE", "KOCHERLAKOTA", "BRAINARD", "DUDLEY", "EVANS", "YELLEN"],
        "window": "last8",  # Oct 2014 - Oct 2015 (full window is 12)
    },
    {
        # Audit slice: Claude scored every member 0 at every prior meeting for
        # this decision. Spot-check for false negatives.
        "decision_ymd": "20081216",
        "decision_id": "d005",
        "short_name": "QE1 MBS audit (Dec 2008)",
        "members": ["BERNANKE", "ROSENGREN", "YELLEN"],
        "window": "last3",  # Aug - Oct 2008
    },
]

APP_VERSION = "1.0"
