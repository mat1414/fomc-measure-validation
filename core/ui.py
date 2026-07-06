"""Shared UI components for the three validation apps."""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import streamlit as st

from core import export
from core.quotes import find_quote_ranges
from core.specs import ACCURACY_OPTIONS, CONFIDENCE_LEVELS

_SCROLLBOX_STYLE = (
    "height:{height}px;overflow-y:auto;border:1px solid #d0d0d0;border-radius:6px;"
    "padding:14px;background:#fcfcfc;white-space:pre-wrap;line-height:1.5;"
    "font-size:0.92rem;"
)


def _escape_with_marks(text: str, ranges: list[tuple[int, int]]) -> str:
    """HTML-escape text, wrapping the given character ranges in <mark>."""
    parts: list[str] = []
    cursor = 0
    for lo, hi in ranges:
        parts.append(html.escape(text[cursor:lo]))
        parts.append(f"<mark>{html.escape(text[lo:hi])}</mark>")
        cursor = hi
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def render_speeches(text: str, evidences: list[str], height: int = 460) -> None:
    """Scrollable speech panel with Claude's evidence quotes highlighted."""
    ranges = find_quote_ranges(text, evidences)
    body = _escape_with_marks(text, ranges)
    st.markdown(
        f'<div style="{_SCROLLBOX_STYLE.format(height=height)}">{body}</div>',
        unsafe_allow_html=True,
    )
    if evidences and not ranges:
        st.caption("No evidence quotes could be located verbatim in this text.")


QUOTE_BADGES = {
    "found": ("✔ Quote found verbatim in the speeches (highlighted).", "green"),
    "partial": ("◐ Only part of the quote was found verbatim — check the rest.", "orange"),
    "not_found": ("✘ Quote NOT found verbatim in the speeches — verify carefully.", "red"),
}


def render_quote_badge(quote_match_value) -> None:
    if quote_match_value is None or pd.isna(quote_match_value):
        return
    badge = QUOTE_BADGES.get(str(quote_match_value))
    if badge:
        text, color = badge
        st.markdown(f":{color}[{text}]")


def render_scale_reference(spec: dict) -> None:
    with st.expander("Scale reference", expanded=False):
        for score in spec["score_options"]:
            label = spec["scale"][score]
            st.markdown(f"**{score:+d} — {label}**" if score < 0 else f"**{score} — {label}**")
            for item in spec["scale_detail"][score]:
                st.caption(f"- {item}")
        st.markdown(f"*Evidence rule:* {spec['evidence_rule']}")


def render_instruction_prompt(prompt_text: str) -> None:
    with st.expander("Claude's full instructions (verbatim)", expanded=False):
        st.markdown(
            f'<pre style="white-space:pre-wrap;font-size:0.82rem;">{html.escape(prompt_text)}</pre>',
            unsafe_allow_html=True,
        )


def render_transcript_viewer(ymd: str, transcript_df: pd.DataFrame, key_prefix: str,
                             note: str) -> None:
    """Full-meeting transcript expander. Clearly labeled as context Claude
    did not see (or did not see in full)."""
    with st.expander(f"Full meeting transcript — {ymd}", expanded=False):
        st.caption(note)
        col1, col2 = st.columns([3, 2])
        with col1:
            search = st.text_input("Search transcript", key=f"{key_prefix}_search",
                                   placeholder="Enter search term...")
        with col2:
            speakers = ["All speakers"] + sorted(
                s for s in transcript_df["stablespeaker"].unique() if s
            )
            who = st.selectbox("Speaker", speakers, key=f"{key_prefix}_who")

        view = transcript_df
        if who != "All speakers":
            view = view[view["stablespeaker"] == who]
        if search:
            view = view[view["text"].str.contains(search, case=False, regex=False)]
            st.caption(f"{len(view)} matching statements")

        if len(view) > 400 and not search and who == "All speakers":
            st.caption(f"Showing all {len(view)} statements.")

        lines = []
        for _, row in view.iterrows():
            marker = "§ " if row["is_policy"] else ""
            body = html.escape(row["text"])
            if search:
                # best-effort case-insensitive highlight
                low = row["text"].lower()
                needle = search.lower()
                idx = low.find(needle)
                if idx >= 0:
                    body = (html.escape(row["text"][:idx]) + "<mark>"
                            + html.escape(row["text"][idx:idx + len(search)])
                            + "</mark>" + html.escape(row["text"][idx + len(search):]))
            lines.append(f"<b>{marker}{html.escape(row['speaker_label'])}:</b> {body}")
        st.markdown(
            f'<div style="{_SCROLLBOX_STYLE.format(height=420)}">' + "<br><br>".join(lines) + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("§ = statement is inside the policy-go-round section of the meeting.")


def radio_index(options: list, value) -> int | None:
    """Index of a previously saved value, or None (unselected)."""
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return None


def assessment_form(key_prefix: str, spec: dict, existing: dict | None) -> dict:
    """Render the human-assessment widgets; returns current values."""
    existing = existing or {}

    supports = st.radio(
        "Does Claude's evidence support the score?",
        options=[o.capitalize() for o in ACCURACY_OPTIONS],
        index=radio_index(ACCURACY_OPTIONS, existing.get("supports_evidence")),
        key=f"{key_prefix}_supports",
        horizontal=True,
    )

    score = st.radio(
        spec["score_question"],
        options=spec["score_options"],
        index=radio_index(spec["score_options"], existing.get("human_score")),
        format_func=lambda x: f"{x}  ({spec['scale'][x]})",
        key=f"{key_prefix}_score",
        horizontal=True,
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        confidence = st.radio(
            "Your confidence",
            options=[o.capitalize() for o in CONFIDENCE_LEVELS],
            index=radio_index(CONFIDENCE_LEVELS, existing.get("confidence")),
            key=f"{key_prefix}_confidence",
            horizontal=True,
        )
    with col2:
        notes = st.text_input(
            "Notes (optional)",
            value=existing.get("notes", "") or "",
            key=f"{key_prefix}_notes",
            placeholder="Observations, concerns, borderline calls...",
        )

    return {
        "supports_evidence": supports.lower() if supports else None,
        "human_score": score,
        "confidence": confidence.lower() if confidence else None,
        "notes": notes,
    }


def missing_fields(values: dict) -> list[str]:
    missing = []
    if values.get("supports_evidence") is None:
        missing.append("evidence supports")
    if values.get("human_score") is None:
        missing.append("your score")
    if values.get("confidence") is None:
        missing.append("confidence")
    return missing


# ---------------------------------------------------------------------------
# Sidebar sections shared by all apps
# ---------------------------------------------------------------------------
def sidebar_coder_and_restore(spec: dict, key_fields: list[str]) -> None:
    st.header("Coder ID")
    coder_id = st.text_input(
        "Enter your ID", value=st.session_state.coder_id,
        placeholder="Your initials", label_visibility="collapsed",
    )
    if coder_id != st.session_state.coder_id:
        st.session_state.coder_id = coder_id.strip()

    st.divider()
    st.header("Resume previous work")
    uploaded = st.file_uploader(
        "Upload a saved JSON file", type=["json"],
        help="Upload a save file you downloaded earlier to continue where you left off.",
    )
    if uploaded is not None:
        if st.button("Restore progress", use_container_width=True):
            ok, message, restored = export.restore_from_uploaded_json(
                uploaded, spec["tool"], key_fields
            )
            if ok and restored:
                if restored["coder_id"]:
                    st.session_state.coder_id = restored["coder_id"]
                if restored["started_at"]:
                    st.session_state.started_at = restored["started_at"]
                st.session_state.records.update(restored["records"])
                st.session_state.unsaved_count = 0
                st.session_state.jump_to_incomplete = True
                st.success(message)
                st.rerun()
            else:
                st.error(message)


def sidebar_downloads(spec: dict, columns: list[str], data_version: str) -> None:
    st.divider()
    st.header("Save / download results")
    records = st.session_state.records
    n_completed = sum(1 for r in records.values() if r.get("completed"))

    if st.session_state.coder_id and records:
        json_data, json_name = export.generate_results_json(
            spec["tool"], data_version, st.session_state.coder_id, records,
            st.session_state.started_at or datetime.now().isoformat(timespec="seconds"),
            columns,
        )
        csv_data, csv_name = export.generate_results_csv(
            spec["tool"], data_version, st.session_state.coder_id, records, columns,
        )
        clicked_json = st.download_button(
            f"Download JSON save file ({n_completed} completed)",
            data=json_data, file_name=json_name, mime="application/json",
            use_container_width=True,
        )
        clicked_csv = st.download_button(
            "Download CSV (for analysis)",
            data=csv_data, file_name=csv_name, mime="text/csv",
            use_container_width=True,
        )
        if clicked_json or clicked_csv:
            st.session_state.unsaved_count = 0
    else:
        st.info("Complete some assessments to enable downloads.")

    if st.session_state.unsaved_count >= 10:
        st.warning(
            f"{st.session_state.unsaved_count} assessments since your last download. "
            "Download the JSON save file now — progress is lost if the connection drops."
        )
    st.caption(f"Data version {data_version} - app 1.0")


def init_common_state() -> None:
    defaults = {
        "coder_id": "",
        "records": {},
        "started_at": None,
        "unsaved_count": 0,
        "jump_to_incomplete": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.started_at is None:
        st.session_state.started_at = datetime.now().isoformat(timespec="seconds")
