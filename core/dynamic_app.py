"""App engine for the dynamic position alignment tool.

Unit of work: one (decision, member, prior meeting) cell. The coder works
through a member's run-up trajectory oldest-meeting-first, seeing ALL of the
member's speeches at each meeting (exactly what Claude saw) and one decision
packet."""

from __future__ import annotations

import html as _html
from datetime import datetime

import pandas as pd
import streamlit as st

from core import ui
from core.data import load_dynamic_cells, load_meta, load_prompts, load_transcript_view
from core.export import record_key
from core.specs import DYNAMIC_KEY_FIELDS, DYNAMIC_RECORD_COLUMNS, DYNAMIC_SPEC

TRANSCRIPT_NOTE = (
    "Claude did NOT see this full transcript — it saw ONLY the focus member's speeches "
    "shown above (all sections of the meeting). Use it for your own context."
)


def _fmt_ymd(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"


def _task_key(row) -> str:
    return f"{row['decision_ymd']}|{row['decision_id']}"


def _cell_key(row) -> str:
    return (f"{row['decision_ymd']}|{row['decision_id']}|"
            f"{row['meeting_ymd']}|{row['stablespeaker']}")


def _member_progress(cells: pd.DataFrame) -> tuple[int, int]:
    records = st.session_state.records
    done = sum(1 for _, r in cells.iterrows()
               if records.get(_cell_key(r), {}).get("completed"))
    return done, len(cells)


def _find_first_incomplete(all_cells: pd.DataFrame):
    for _, row in all_cells.iterrows():
        if not st.session_state.records.get(_cell_key(row), {}).get("completed"):
            return row
    return None


def run_dynamic_app() -> None:
    spec = DYNAMIC_SPEC
    st.set_page_config(
        page_title=spec["title"], page_icon=spec["icon"],
        layout="wide", initial_sidebar_state="expanded",
    )
    ui.init_common_state()
    for key, default in (("dyn_task", None), ("dyn_member", None), ("dyn_seq", 1)):
        if key not in st.session_state:
            st.session_state[key] = default

    all_cells = load_dynamic_cells()
    meta = load_meta()
    prompts = load_prompts()

    tasks = all_cells.drop_duplicates(["decision_ymd", "decision_id"])[
        ["decision_ymd", "decision_id", "short_name", "decision_label"]
    ]
    task_keys = [_task_key(r) for _, r in tasks.iterrows()]
    task_labels = {_task_key(r): r["short_name"] for _, r in tasks.iterrows()}

    ui.show_flash()

    # ------------------------------------------------------------------ sidebar
    with st.sidebar:
        st.title(f"{spec['icon']} {spec['short_title']}")
        ui.sidebar_coder_and_restore(spec, DYNAMIC_KEY_FIELDS, meta["data_version"])

        st.divider()
        st.header("Decision")
        current = (task_keys.index(st.session_state.dyn_task)
                   if st.session_state.dyn_task in task_keys else None)
        chosen = st.selectbox(
            "Select decision", task_keys, index=current,
            format_func=lambda k: task_labels[k],
            placeholder="Choose a decision...", label_visibility="collapsed",
        )
        if chosen and chosen != st.session_state.dyn_task:
            st.session_state.dyn_task = chosen
            st.session_state.dyn_member = None
            st.session_state.dyn_seq = 1
            st.rerun()

        if st.session_state.dyn_task:
            dymd, did = st.session_state.dyn_task.split("|")
            task_cells = all_cells[
                (all_cells["decision_ymd"] == dymd) & (all_cells["decision_id"] == did)
            ]
            members = list(pd.unique(task_cells["stablespeaker"]))

            st.divider()
            st.header("Members")
            for member in members:
                mcells = task_cells[task_cells["stablespeaker"] == member]
                done, total = _member_progress(mcells)
                if done == total and total > 0:
                    icon = "+"
                elif member == st.session_state.dyn_member:
                    icon = ">"
                elif done > 0:
                    icon = "~"
                else:
                    icon = " "
                if st.button(f"[{icon}] {member} ({done}/{total})",
                             key=f"mem_btn_{member}", use_container_width=True):
                    st.session_state.dyn_member = member
                    # resume at first incomplete meeting for this member
                    nxt = _find_first_incomplete(mcells)
                    st.session_state.dyn_seq = int(nxt["seq"]) if nxt is not None else 1
                    st.rerun()

            done_all, total_all = _member_progress(task_cells)
            st.divider()
            st.header("Progress")
            st.write(f"**This decision:** {done_all} / {total_all} cells")
            if total_all:
                st.progress(done_all / total_all)
            session_done = sum(1 for r in st.session_state.records.values()
                               if r.get("completed"))
            st.caption(f"All decisions this session: {session_done} completed")

        ui.sidebar_downloads(spec, DYNAMIC_RECORD_COLUMNS, meta["data_version"])

    # -------------------------------------------------------------------- main
    if not st.session_state.coder_id:
        st.warning("Please enter your Coder ID in the sidebar to begin.")
        st.stop()

    if st.session_state.jump_to_incomplete:
        st.session_state.jump_to_incomplete = False
        nxt = _find_first_incomplete(all_cells)
        if nxt is not None:
            st.session_state.dyn_task = _task_key(nxt)
            st.session_state.dyn_member = nxt["stablespeaker"]
            st.session_state.dyn_seq = int(nxt["seq"])
            ui.flash("Jumping to the next incomplete cell.")
            st.rerun()

    if not st.session_state.dyn_task:
        st.title(spec["title"])
        st.markdown(spec["intro"])
        st.markdown("### Decisions in this validation sample")
        for _, trow in tasks.iterrows():
            tcells = all_cells[(all_cells["decision_ymd"] == trow["decision_ymd"])
                               & (all_cells["decision_id"] == trow["decision_id"])]
            n_members = tcells["stablespeaker"].nunique()
            n_meetings = tcells["meeting_ymd"].nunique()
            st.markdown(
                f"- **{trow['short_name']}** — adopted {_fmt_ymd(trow['decision_ymd'])}; "
                f"{n_members} members x {n_meetings} run-up meetings = {len(tcells)} cells"
            )
        st.info("Select a decision in the sidebar to begin.")
        st.stop()

    dymd, did = st.session_state.dyn_task.split("|")
    task_cells = all_cells[
        (all_cells["decision_ymd"] == dymd) & (all_cells["decision_id"] == did)
    ]

    if not st.session_state.dyn_member:
        st.title(task_labels[st.session_state.dyn_task])
        st.markdown(spec["intro"])
        st.info("Select a member in the sidebar. You will code that member's meetings "
                "oldest-first, following their position through the run-up.")
        st.stop()

    member = st.session_state.dyn_member
    mcells = task_cells[task_cells["stablespeaker"] == member].sort_values("seq")
    seqs = list(mcells["seq"])
    if st.session_state.dyn_seq not in seqs:
        st.session_state.dyn_seq = seqs[0]
    cell = mcells[mcells["seq"] == st.session_state.dyn_seq].iloc[0]

    # ---- decision context
    st.title(f"{cell['short_name']} — {member}")
    st.markdown(spec["intro"])

    with st.expander("Decision packet (what Claude saw for this decision)", expanded=True):
        st.info(ui.md_escape(cell["description"]))
        st.caption(
            f"Adopted: {_fmt_ymd(dymd)} | Type: {cell['type']} | "
            f"Communication subtype: {cell['communication_subtype']} | "
            f"Policy direction: {cell['policy_direction']}"
        )
        st.markdown("*Adopted-policy evidence:*")
        ui.render_verbatim(cell["adopted_policy_evidence"])

    ui.render_scale_reference(spec)
    ui.render_instruction_prompt(prompts[spec["prompt_key"]])

    # ---- timeline navigation
    st.divider()
    pos = seqs.index(st.session_state.dyn_seq)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("< Earlier meeting", disabled=(pos == 0), use_container_width=True):
            st.session_state.dyn_seq = seqs[pos - 1]
            st.rerun()
    with col2:
        st.subheader(
            f"Meeting {pos + 1} of {len(seqs)}: {_fmt_ymd(cell['meeting_ymd'])} "
            f"({int(cell['meetings_back'])} meeting(s) before adoption)"
        )
    with col3:
        if st.button("Later meeting >", disabled=(pos >= len(seqs) - 1),
                     use_container_width=True):
            st.session_state.dyn_seq = seqs[pos + 1]
            st.rerun()

    strip = ""
    records = st.session_state.records
    for _, r in mcells.iterrows():
        if records.get(_cell_key(r), {}).get("completed"):
            strip += "[+] "
        elif r["seq"] == st.session_state.dyn_seq:
            strip += "[>] "
        else:
            strip += "[ ] "
    st.caption(f"Timeline (oldest → newest): {strip}")

    # ---- speeches
    st.markdown(f"#### {member}'s speeches at {_fmt_ymd(cell['meeting_ymd'])} "
                "(what Claude saw — ALL sections)")
    evidence = str(cell["claude_evidence"])
    highlight = [evidence] if str(cell.get("quote_match")) in ("found", "partial") else []
    ui.render_speeches(cell["speeches_text"], highlight)

    ui.render_transcript_viewer(
        cell["meeting_ymd"], load_transcript_view(cell["meeting_ymd"]),
        key_prefix=f"tv_{dymd}_{did}_{cell['meeting_ymd']}", note=TRANSCRIPT_NOTE,
    )
    with st.expander("Raw packets (exact text Claude received)", expanded=False):
        speaker_packet = (
            "Speaker packet:\n\n<speeches>\n"
            f"{cell['speeches_text']}\n</speeches>\n\n"
            f"<focus_speaker>\n{member}\n</focus_speaker>\n\n"
            "Score only this focus speaker and return the XML block only."
        )
        st.markdown(
            f'<pre style="white-space:pre-wrap;font-size:0.78rem;">'
            f'{_html.escape(cell["packet_text"])}\n\n{_html.escape(speaker_packet)}</pre>',
            unsafe_allow_html=True,
        )

    # ---- Claude's assessment + human form
    st.divider()
    claude_score = int(cell["claude_score"])
    st.markdown("### Claude's assessment")
    st.markdown(f"Score: **{claude_score} ({spec['scale'][claude_score]})**")
    st.markdown("*Evidence:*")
    ui.render_verbatim(cell["claude_evidence"])
    if cell["claude_reasoning"]:
        st.markdown("*Reasoning:*")
        ui.render_verbatim(cell["claude_reasoning"])
    ui.render_quote_badge(cell.get("quote_match"))

    st.markdown("### Your assessment")
    key = _cell_key(cell)
    existing = st.session_state.records.get(key)
    values = ui.assessment_form(
        f"dyn_{dymd}_{did}_{cell['meeting_ymd']}_{member}", spec, existing
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Submit & next", type="primary", use_container_width=True):
            missing = ui.missing_fields(values)
            if missing:
                st.error(f"Please complete: {', '.join(missing)}")
            else:
                record = {
                    "decision_ymd": dymd,
                    "decision_id": did,
                    "decision_label": cell["decision_label"],
                    "meeting_ymd": cell["meeting_ymd"],
                    "meetings_back": int(cell["meetings_back"]),
                    "seq": int(cell["seq"]),
                    "stablespeaker": member,
                    "description": cell["description"],
                    "claude_score": claude_score,
                    "claude_evidence": cell["claude_evidence"],
                    "claude_reasoning": cell["claude_reasoning"],
                    "quote_match": (None if pd.isna(cell.get("quote_match"))
                                    else str(cell.get("quote_match"))),
                    **values,
                    "completed": True,
                    "completed_at": datetime.now().isoformat(timespec="seconds"),
                }
                st.session_state.records[record_key(record, DYNAMIC_KEY_FIELDS)] = record
                st.session_state.unsaved_count += 1

                if pos < len(seqs) - 1:
                    st.session_state.dyn_seq = seqs[pos + 1]
                else:
                    # end of the timeline — first check for meetings the coder
                    # skipped for THIS member before declaring the trajectory done
                    own = _find_first_incomplete(mcells)
                    if own is not None:
                        st.session_state.dyn_seq = int(own["seq"])
                        ui.flash(f"You skipped some of {member}'s meetings — "
                                 "jumping back to the first incomplete one.")
                    else:
                        nxt = _find_first_incomplete(task_cells)
                        if nxt is not None:
                            st.session_state.dyn_member = nxt["stablespeaker"]
                            st.session_state.dyn_seq = int(nxt["seq"])
                            ui.flash(f"{member}'s trajectory complete — next: "
                                     f"{nxt['stablespeaker']}. Download a save file!")
                        else:
                            ui.flash("Decision complete! Download your save file, then "
                                     "pick the next decision in the sidebar.",
                                     balloons=True)
                st.rerun()
