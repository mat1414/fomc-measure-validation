"""Validation sample definition.

This file is the single place that defines WHICH meetings, decisions, and
members the human coders validate. To change the sample: edit this file,
rerun ``python build_data.py`` (on a machine with the source data), and
commit the regenerated ``data/`` files.
"""

# ---------------------------------------------------------------------------
# Static tools (position alignment + adoption contribution)
# Five landmark meetings; every scored speaker at each meeting.
# ---------------------------------------------------------------------------
STATIC_MEETINGS = {
    "19791006": "October 6, 1979 (Volcker's Saturday Night Special)",
    "19940816": "August 16, 1994 (Greenspan tightening cycle)",
    "20081216": "December 16, 2008 (Financial crisis ZLB)",
    "20110809": "August 9, 2011 (Calendar guidance introduced)",
    "20190731": "July 31, 2019 (Powell mid-cycle cut)",
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
        # The old paper's 1994 validation context (1994-08-16) has no decision
        # in the dynamic corpus; this is the nearest 1994 landmark — the first
        # public post-meeting statement, adopted at the start of the same
        # Greenspan tightening cycle.
        "decision_ymd": "19940204",
        "decision_id": "d001",
        "short_name": "First policy statement (Feb 1994)",
        "members": ["ANGELL", "MELZER", "BROADDUS", "PHILLIPS", "FORRESTAL", "GREENSPAN"],
        "window": "all",  # 8 meetings: Feb 1993 - Dec 1993
    },
    {
        "decision_ymd": "20081216",
        "decision_id": "d006",
        "short_name": "ZLB established (Dec 2008)",
        "members": ["YELLEN", "KOHN", "LACKER", "EVANS", "HOENIG", "WARSH"],
        "window": "all",  # 8 meetings: Dec 2007 - Oct 2008
    },
    {
        "decision_ymd": "20110809",
        "decision_id": "d002",
        "short_name": "Calendar guidance (Aug 2011)",
        "members": ["KOCHERLAKOTA", "EVANS", "PLOSSER", "YELLEN", "LOCKHART", "BERNANKE"],
        "window": "all",  # 8 meetings: Aug 2010 - Jun 2011
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
