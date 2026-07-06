"""Per-tool definitions: scales, rubrics (distilled from the instruction
prompts Claude received — the verbatim prompt is shown in the app via
data/prompts.json), and export schemas."""

ACCURACY_OPTIONS = ["yes", "partially", "no"]
CONFIDENCE_LEVELS = ["high", "medium", "low"]

ALIGNMENT_SCALE = {
    2: "Clear support",
    1: "Qualified support",
    0: "No clear position",
    -1: "Qualified opposition",
    -2: "Clear opposition",
}

ALIGNMENT_DETAIL = {
    2: [
        "Explicit support for this decision, OR explicit support for a policy choice "
        "(alternative / statement / directive / package) that clearly contains it, OR a "
        "clear stance this decision embodies.",
        "Simple support counts: \"I support Alternative B\" or \"I support the statement as "
        "written\" can be +2 when it validly maps to the decision — no extended reasoning required.",
        "Minor reservations about secondary aspects stay +2.",
    ],
    1: [
        "Supports the decision but with significant reservations, supports only part of it, "
        "or gives conditional / second-best support.",
        "Evidence is indirect and only loosely connects to the decision.",
    ],
    0: [
        "No clear position, ambiguous mapping, or balanced support and opposition.",
        "Procedural acceptance only: a yes vote, \"I can live with it\", or willingness to "
        "join the result without a stated position.",
        "Silence, biography, ideology, clarifying questions.",
    ],
    -1: [
        "Opposes the decision but with significant qualifications, opposes only part of it, "
        "or states an unmet condition for support.",
        "Evidence is indirect and only loosely connects to the decision.",
    ],
    -2: [
        "Explicit opposition to this decision, OR explicit opposition to a policy choice that "
        "clearly contains it, OR a clear stance this decision contradicts.",
        "Minor favorable comments about secondary aspects stay -2.",
    ],
}

DYNAMIC_DETAIL = {
    2: [
        "Explicit support for the decision's action — or a stronger / larger / faster version "
        "of the same action on the same instrument.",
        "Simple support suffices; no extended reasoning required.",
    ],
    1: [
        "Qualified, hedged, conditional, reluctant, or second-best support.",
        "Clearly endorses taking the same action later and treats it as desirable.",
    ],
    0: [
        "Engages the topic but is genuinely undecided or balanced, OR takes no explicit "
        "position on this decision's action.",
        "General outlook / forecast / risk discussion; timing judgments without a stance; "
        "keeping the existing stance; a position on a different instrument or action.",
    ],
    -1: [
        "Qualified / hedged / conditional opposition, including \"not now\" or "
        "conditions-not-met.",
    ],
    -2: [
        "Explicit opposition to the action, or advocating the opposite direction on the "
        "same instrument.",
    ],
}

ADOPTION_SCALE = {
    3: "Adopted content (near-verbatim)",
    2: "Support + decision-specific reasoning",
    1: "Explicit support, no reasoning",
    0: "No positive contribution",
}

ADOPTION_DETAIL = {
    3: [
        "Proposed a concrete item copied exactly or near-verbatim into the adopted decision "
        "or communication (number, range, phrase, wording).",
        "Use sparingly: similar themes, broad direction, partial or rejected wording, and "
        "approximate matches do NOT qualify.",
    ],
    2: [
        "Affirmatively supported this adopted decision/component AND gave decision-specific "
        "reasoning, evidence, or defense in the quote.",
    ],
    1: [
        "Explicitly supported this adopted decision/component without added reasoning.",
        "Backing the adopted action while preferring a somewhat different calibration can "
        "still count at the 1-2 level.",
    ],
    0: [
        "No positive decision-specific contribution.",
        "Whole-alternative / package / statement endorsement with nothing about this "
        "component (\"I support Alternative B\" alone is 0 — even when that alternative "
        "contains the component).",
        "A yes vote, lack of objection, \"not opposed\", reluctant acceptance, generic "
        "agreement with the broad direction, implementation questions, or criticism of the "
        "adopted mechanism.",
        "If the same quote could be copied unchanged to several decisions, it is not "
        "decision-specific and must be 0.",
    ],
}

EVIDENCE_RULE_STATIC = (
    "Every nonzero score requires an exact quote from the focus speaker stated at this "
    "meeting. If there is no usable quote, the score is 0 and the evidence reads "
    "\"No explicit statement found.\""
)
EVIDENCE_RULE_ADOPTION = (
    "Every positive score requires an exact quote from the focus speaker that directly "
    "concerns this decision's component, number, wording, instrument, or communication "
    "content. Otherwise the score is 0."
)
EVIDENCE_RULE_DYNAMIC = (
    "Every nonzero score requires an exact quote stating the speaker's current position on "
    "THIS decision's action. The sign is scored relative to the LATER adopted action. "
    "Alternative labels and votes are meeting-specific and do not count as evidence."
)

STATIC_KEY_FIELDS = ["ymd", "stablespeaker", "decision_id"]
DYNAMIC_KEY_FIELDS = ["decision_ymd", "decision_id", "meeting_ymd", "stablespeaker"]

STATIC_RECORD_COLUMNS = [
    "tool", "data_version", "coder_id",
    "ymd", "stablespeaker", "decision_id", "decision_index", "description",
    "claude_score", "claude_evidence", "quote_match",
    "supports_evidence", "human_score", "confidence", "notes",
    "completed", "completed_at",
]

DYNAMIC_RECORD_COLUMNS = [
    "tool", "data_version", "coder_id",
    "decision_ymd", "decision_id", "decision_label", "meeting_ymd", "meetings_back",
    "seq", "stablespeaker", "description",
    "claude_score", "claude_evidence", "claude_reasoning", "quote_match",
    "supports_evidence", "human_score", "confidence", "notes",
    "completed", "completed_at",
]

STATIC_SPECS = {
    "position_alignment": {
        "tool": "position_alignment",
        "title": "FOMC Position Alignment Validation",
        "short_title": "Position Alignment",
        "icon": "📊",
        "scores_file": "scores_alignment.parquet",
        "score_options": [2, 1, 0, -1, -2],
        "scale": ALIGNMENT_SCALE,
        "scale_detail": ALIGNMENT_DETAIL,
        "evidence_rule": EVIDENCE_RULE_STATIC,
        "prompt_key": "position_alignment",
        "score_question": "Your alignment score",
        "meeting_date_suffix": "",
        "intro": (
            "For each policy decision adopted at this meeting, Claude scored how strongly "
            "the speaker's stated position supports or opposes it (-2..+2), using only the "
            "speaker's policy-section speeches shown below. Review each score and give "
            "your own."
        ),
    },
    "adoption_contribution": {
        "tool": "adoption_contribution",
        "title": "FOMC Adoption Contribution Validation",
        "short_title": "Adoption Contribution",
        "icon": "🧩",
        "scores_file": "scores_adoption.parquet",
        "score_options": [0, 1, 2, 3],
        "scale": ADOPTION_SCALE,
        "scale_detail": ADOPTION_DETAIL,
        "evidence_rule": EVIDENCE_RULE_ADOPTION,
        "prompt_key": "adoption_contribution",
        "score_question": "Your contribution score",
        "meeting_date_suffix": "   (this is the ADOPTION meeting for all decisions listed)",
        "intro": (
            "For each policy decision adopted at this meeting, Claude scored whether the "
            "speaker supplied decision-specific support, reasoning, or adopted content "
            "(0..3), using only the speaker's policy-section speeches shown below. This "
            "measure is stricter than position alignment: package-level or "
            "alternative-level endorsement alone is 0. Review each score and give your own."
        ),
    },
}

DYNAMIC_SPEC = {
    "tool": "dynamic_position_alignment",
    "title": "FOMC Dynamic Position Alignment Validation",
    "short_title": "Dynamic Alignment",
    "icon": "📈",
    "score_options": [2, 1, 0, -1, -2],
    "scale": ALIGNMENT_SCALE,
    "scale_detail": DYNAMIC_DETAIL,
    "evidence_rule": EVIDENCE_RULE_DYNAMIC,
    "prompt_key": "dynamic_position_alignment",
    "score_question": "Your alignment score",
    "intro": (
        "Claude scored this member's stated position at a meeting BEFORE the decision was "
        "adopted (-2..+2, relative to the later adopted action), reading ALL of the "
        "member's speeches at that meeting. Work through the member's meetings oldest "
        "first and give your own score for each."
    ),
}
