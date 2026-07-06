"""App engine for the two static tools (position alignment and adoption
contribution). One screen per speaker: the coder sees the speaker's
policy-section speeches (exactly what Claude saw) and assesses Claude's score
for every decision adopted at the meeting."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core import ui
from core.data import load_meta, load_prompts, load_static_bundle, load_transcript_view
from core.export import record_key
from core.specs import STATIC_KEY_FIELDS, STATIC_RECORD_COLUMNS

TRANSCRIPT_NOTE = (
    "Claude did NOT see this full transcript for this measure — it saw only the focus "
    "speaker's policy-section speeches shown above. Use it for your own context "
    "(e.g., what proposal a speaker is reacting to)."
)


def _meeting_speakers(bundle: dict, ymd: str) -> list[str]:
    sp = bundle["speeches"]
    sp = sp[sp["ymd"] == ymd].sort_values("speaker_order")
    return list(sp["stablespeaker"])


def _meeting_decisions(bundle: dict, ymd: str) -> pd.DataFrame:
    d = bundle["decisions"]
    return d[d["ymd"] == ymd].sort_values("decision_index")


def _score_row(bundle: dict, ymd: str, speaker: str, decision_id: str):
    s = bundle["scores"]
    rows = s[(s["ymd"] == ymd) & (s["stablespeaker"] == speaker)
             & (s["decision_id"] == decision_id)]
    return rows.iloc[0] if len(rows) else None


def _speaker_complete(ymd: str, speaker: str, decision_ids: list[str]) -> tuple[int, int]:
    records = st.session_state.records
    done = 0
    for did in decision_ids:
        key = f"{ymd}|{speaker}|{did}"
        if records.get(key, {}).get("completed"):
            done += 1
    return done, len(decision_ids)


def _find_first_incomplete(bundle: dict, meetings: pd.DataFrame):
    for _, mrow in meetings.iterrows():
        ymd = mrow["ymd"]
        decision_ids = list(_meeting_decisions(bundle, ymd)["decision_id"])
        for idx, speaker in enumerate(_meeting_speakers(bundle, ymd)):
            done, total = _speaker_complete(ymd, speaker, decision_ids)
            if done < total:
                return ymd, idx
    return None, None


def _render_decision_context(spec: dict, bundle: dict, ymd: str, meeting_row) -> None:
    decisions = _meeting_decisions(bundle, ymd)
    with st.expander(f"Adopted decisions at this meeting ({len(decisions)})", expanded=False):
        st.caption(
            "These are the decision blocks Claude received (metadata + description + "
            "evidence of the adopted policy)."
        )
        for _, row in decisions.iterrows():
            st.markdown(f"**{row['decision_id']}** — {row['description']}")
            st.caption(
                f"Type: {row['type']} | Communication subtype: {row['communication_subtype']} | "
                f"Policy direction: {row['policy_direction']} | "
                f"Accommodation score: {row['decision_score']}"
            )
            st.markdown(f"*Adopted-policy evidence:* {row['adopted_policy_evidence']}")
            st.caption(
                f"Matched alternatives (metadata, NOT shown to Claude): {row['matched_alternatives']}"
            )
            st.divider()

    alts = bundle["alternatives"]
    alts = alts[alts["ymd"] == ymd]
    with st.expander("Policy alternatives (as shown to Claude)", expanded=False):
        if len(alts) == 0:
            st.markdown("*No policy alternatives found for this meeting.* "
                        "(This is exactly what Claude was told.)")
        for i, (_, row) in enumerate(alts.iterrows()):
            st.markdown(f"**{row['label']}**")
            if row["description"]:
                st.caption(row["description"])
            if row["policy_statement"]:
                st.text_area("Policy statement", value=row["policy_statement"], height=130,
                             disabled=True, key=f"alt_ps_{ymd}_{i}",
                             label_visibility="visible")
            if row["proposed_directive"]:
                st.text_area("Proposed directive", value=row["proposed_directive"], height=130,
                             disabled=True, key=f"alt_pd_{ymd}_{i}",
                             label_visibility="visible")


def _render_raw_packet(spec: dict, meeting_row, speaker: str, speeches_text: str) -> None:
    meeting_packet = (
        "Meeting packet:\n\n<policy_decisions>\n"
        f"{meeting_row['decision_blocks_xml']}\n</policy_decisions>\n\n"
        f"<alternatives>\n{meeting_row['alternatives_text']}\n</alternatives>\n\n"
        f"meeting_date: {meeting_row['ymd']}{spec['meeting_date_suffix']}"
    )
    speaker_packet = (
        "Speaker packet:\n\n<speeches>\n"
        f"{speeches_text}\n</speeches>\n\n"
        f"<focus_speaker>\n{speaker}\n</focus_speaker>\n\n"
        "Score only this focus speaker and return the XML block only."
    )
    with st.expander("Raw packets (exact text Claude received)", expanded=False):
        import html as _html
        st.markdown(
            f'<pre style="white-space:pre-wrap;font-size:0.78rem;">'
            f'{_html.escape(meeting_packet)}\n\n{_html.escape(speaker_packet)}</pre>',
            unsafe_allow_html=True,
        )


def run_static_app(spec: dict) -> None:
    st.set_page_config(
        page_title=spec["title"], page_icon=spec["icon"],
        layout="wide", initial_sidebar_state="expanded",
    )
    ui.init_common_state()
    if "selected_meeting" not in st.session_state:
        st.session_state.selected_meeting = None
    if "speaker_idx" not in st.session_state:
        st.session_state.speaker_idx = 0

    bundle = load_static_bundle(spec["scores_file"])
    meta = load_meta()
    prompts = load_prompts()
    meetings = bundle["meetings"]

    # ------------------------------------------------------------------ sidebar
    with st.sidebar:
        st.title(f"{spec['icon']} {spec['short_title']}")
        ui.sidebar_coder_and_restore(spec, STATIC_KEY_FIELDS)

        st.divider()
        st.header("Meeting")
        labels = list(meetings["label"])
        ymds = list(meetings["ymd"])
        current = (ymds.index(st.session_state.selected_meeting)
                   if st.session_state.selected_meeting in ymds else None)
        chosen = st.selectbox("Select meeting", labels, index=current,
                              placeholder="Choose a meeting...",
                              label_visibility="collapsed")
        if chosen:
            chosen_ymd = ymds[labels.index(chosen)]
            if chosen_ymd != st.session_state.selected_meeting:
                st.session_state.selected_meeting = chosen_ymd
                st.session_state.speaker_idx = 0
                st.rerun()

        if st.session_state.selected_meeting:
            ymd = st.session_state.selected_meeting
            decision_ids = list(_meeting_decisions(bundle, ymd)["decision_id"])
            speakers = _meeting_speakers(bundle, ymd)

            st.divider()
            st.header("Progress")
            done_pairs = sum(_speaker_complete(ymd, s, decision_ids)[0] for s in speakers)
            total_pairs = len(speakers) * len(decision_ids)
            st.write(f"**This meeting:** {done_pairs} / {total_pairs} assessments")
            if total_pairs:
                st.progress(done_pairs / total_pairs)
            all_completed = sum(1 for r in st.session_state.records.values()
                                if r.get("completed"))
            st.caption(f"All meetings this session: {all_completed} completed")

            if st.button("Jump to next incomplete", use_container_width=True):
                jymd, jidx = _find_first_incomplete(bundle, meetings)
                if jymd is not None:
                    st.session_state.selected_meeting = jymd
                    st.session_state.speaker_idx = jidx
                    st.rerun()

            st.divider()
            st.header("Speakers")
            for idx, speaker in enumerate(speakers):
                done, total = _speaker_complete(ymd, speaker, decision_ids)
                if done == total and total > 0:
                    icon = "+"
                elif idx == st.session_state.speaker_idx:
                    icon = ">"
                elif done > 0:
                    icon = "~"
                else:
                    icon = " "
                if st.button(f"[{icon}] {speaker} ({done}/{total})",
                             key=f"spk_btn_{idx}", use_container_width=True):
                    st.session_state.speaker_idx = idx
                    st.rerun()

        ui.sidebar_downloads(spec, STATIC_RECORD_COLUMNS, meta["data_version"])

    # -------------------------------------------------------------------- main
    if not st.session_state.coder_id:
        st.warning("Please enter your Coder ID in the sidebar to begin.")
        st.stop()

    if st.session_state.jump_to_incomplete:
        st.session_state.jump_to_incomplete = False
        jymd, jidx = _find_first_incomplete(bundle, meetings)
        if jymd is not None:
            st.session_state.selected_meeting = jymd
            st.session_state.speaker_idx = jidx
            st.toast("Progress restored — jumping to the next incomplete speaker.")
            st.rerun()

    if not st.session_state.selected_meeting:
        st.title(spec["title"])
        st.markdown(spec["intro"])
        st.markdown("### Meetings in this validation sample")
        for _, mrow in meetings.iterrows():
            n_dec = len(_meeting_decisions(bundle, mrow["ymd"]))
            n_spk = len(_meeting_speakers(bundle, mrow["ymd"]))
            st.markdown(f"- **{mrow['label']}** — {n_dec} decisions x {n_spk} speakers "
                        f"= {n_dec * n_spk} assessments")
        st.info("Select a meeting in the sidebar to begin.")
        st.stop()

    ymd = st.session_state.selected_meeting
    meeting_row = meetings[meetings["ymd"] == ymd].iloc[0]
    decisions = _meeting_decisions(bundle, ymd)
    speakers = _meeting_speakers(bundle, ymd)
    if st.session_state.speaker_idx >= len(speakers):
        st.session_state.speaker_idx = 0
    speaker = speakers[st.session_state.speaker_idx]

    st.title(f"{meeting_row['label']}")
    st.markdown(spec["intro"])

    _render_decision_context(spec, bundle, ymd, meeting_row)
    ui.render_scale_reference(spec)
    ui.render_instruction_prompt(prompts[spec["prompt_key"]])

    # Speaker navigation
    st.divider()
    idx = st.session_state.speaker_idx
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("< Previous", disabled=(idx == 0), use_container_width=True):
            st.session_state.speaker_idx = idx - 1
            st.rerun()
    with col2:
        st.subheader(f"Speaker {idx + 1} of {len(speakers)}: {speaker}")
    with col3:
        if st.button("Next >", disabled=(idx >= len(speakers) - 1), use_container_width=True):
            st.session_state.speaker_idx = idx + 1
            st.rerun()

    progress = ""
    decision_ids = list(decisions["decision_id"])
    for i, s in enumerate(speakers):
        done, total = _speaker_complete(ymd, s, decision_ids)
        progress += "[+] " if (done == total and total) else ("[>] " if i == idx else "[ ] ")
    st.caption(f"Progress: {progress}")

    # Speeches — what Claude saw
    speech_rows = bundle["speeches"]
    speeches_text = speech_rows[
        (speech_rows["ymd"] == ymd) & (speech_rows["stablespeaker"] == speaker)
    ].iloc[0]["speeches_text"]

    score_rows = {did: _score_row(bundle, ymd, speaker, did) for did in decision_ids}
    evidences = [str(r["claude_evidence"]) for r in score_rows.values()
                 if r is not None and str(r.get("quote_match")) in ("found", "partial")]

    st.markdown(f"#### {speaker}'s policy-section speeches (what Claude saw)")
    st.caption("Highlighted passages are the quotes Claude cited as evidence (all decisions).")
    ui.render_speeches(speeches_text, evidences)

    ui.render_transcript_viewer(ymd, load_transcript_view(ymd),
                                key_prefix=f"tv_{ymd}", note=TRANSCRIPT_NOTE)
    _render_raw_packet(spec, meeting_row, speaker, speeches_text)

    # Assessments, one per decision
    st.divider()
    st.markdown(f"### Assessments for {speaker}")

    forms: dict[str, dict] = {}
    for _, drow in decisions.iterrows():
        did = drow["decision_id"]
        srow = score_rows.get(did)
        st.markdown(f"---\n**{did}** — {drow['description']}")
        st.caption(f"Type: {drow['type']} | Direction: {drow['policy_direction']}")

        if srow is None:
            st.warning("No Claude score for this pair (not in the scored sample) — skipping.")
            continue

        claude_score = int(srow["claude_score"])
        st.markdown(
            f"Claude's score: **{claude_score} ({spec['scale'][claude_score]})**"
        )
        st.markdown(f"*Claude's evidence:* {srow['claude_evidence']}")
        ui.render_quote_badge(srow.get("quote_match"))

        key = f"{ymd}|{speaker}|{did}"
        existing = st.session_state.records.get(key)
        forms[did] = ui.assessment_form(
            f"{spec['tool']}_{ymd}_{speaker}_{did}", spec, existing
        )

    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(f"Submit all assessments for {speaker}", type="primary",
                     use_container_width=True):
            problems = []
            for did, values in forms.items():
                missing = ui.missing_fields(values)
                if missing:
                    problems.append(f"{did}: {', '.join(missing)}")
            if problems:
                st.error("Please complete — " + " | ".join(problems))
            else:
                now = datetime.now().isoformat(timespec="seconds")
                for did, values in forms.items():
                    drow = decisions[decisions["decision_id"] == did].iloc[0]
                    srow = score_rows[did]
                    record = {
                        "ymd": ymd,
                        "stablespeaker": speaker,
                        "decision_id": did,
                        "decision_index": int(drow["decision_index"]),
                        "description": drow["description"],
                        "claude_score": int(srow["claude_score"]),
                        "claude_evidence": srow["claude_evidence"],
                        "quote_match": srow.get("quote_match"),
                        **values,
                        "completed": True,
                        "completed_at": now,
                    }
                    st.session_state.records[record_key(record, STATIC_KEY_FIELDS)] = record
                st.session_state.unsaved_count += len(forms)

                if idx < len(speakers) - 1:
                    st.session_state.speaker_idx = idx + 1
                else:
                    st.balloons()
                    st.toast("Meeting complete! Download your save file, then pick the "
                             "next meeting in the sidebar.")
                st.rerun()
