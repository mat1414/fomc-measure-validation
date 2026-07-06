"""Freeze the validation data for the three human-coding apps.

Run this locally (it needs the source datasets on this machine); the Streamlit
apps only ever read the small files it writes into ``data/``.

The rendering helpers below are copied VERBATIM from
``kv_code/claude_measures_v5/policy_measure_common.py`` and
``10_dynamic_position_alignment_scores.py`` (same cleaning, truncation limits,
policy-section filter, and templates), so the text shown to human coders is
character-for-character what Claude saw. Instruction prompts are extracted
from the source scripts at build time, not copied by hand.

Sources (authoritative v5 locations):
  - transcripts:      _earlystage/fomctidy/data/transcripts.dta
  - decision context: fed_wsj/kv_analysis/output_v5/claude_output/
                      {adopted_decisions,decision_alternative_links,alternatives}.pkl
  - Claude scores:    .../claude_output/analysis_files/
                      {position_alignment,dynamic_position_alignment,adoption_contribution}.pkl
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from sample_config import DYNAMIC_SAMPLE, STATIC_MEETINGS

# ---------------------------------------------------------------------------
# Source paths (Ben's machine)
# ---------------------------------------------------------------------------
RESEARCH = Path(r"E:\Research Dropbox\Ben Matthies\NotreDame\Research")
V5_DIR = RESEARCH / "fed_wsj" / "kv_analysis" / "output_v5" / "claude_output"
ANALYSIS_DIR = V5_DIR / "analysis_files"
TRANSCRIPTS_DTA = RESEARCH / "_earlystage" / "fomctidy" / "data" / "transcripts.dta"
MEASURES_CODE_DIR = RESEARCH / "fed_wsj" / "kv_code" / "claude_measures_v5"

OUT_DIR = Path(__file__).resolve().parent / "data"

SOURCE_FILES = {
    "transcripts": TRANSCRIPTS_DTA,
    "adopted_decisions": V5_DIR / "adopted_decisions.pkl",
    "decision_alternative_links": V5_DIR / "decision_alternative_links.pkl",
    "alternatives": V5_DIR / "alternatives.pkl",
    "position_alignment": ANALYSIS_DIR / "position_alignment.pkl",
    "dynamic_position_alignment": ANALYSIS_DIR / "dynamic_position_alignment.pkl",
    "adoption_contribution": ANALYSIS_DIR / "adoption_contribution.pkl",
}

PROMPT_SOURCE_SCRIPTS = {
    "position_alignment": MEASURES_CODE_DIR / "09_position_alignment_scores.py",
    "dynamic_position_alignment": MEASURES_CODE_DIR / "10_dynamic_position_alignment_scores.py",
    "adoption_contribution": MEASURES_CODE_DIR / "11_adoption_contribution_scores.py",
}

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  WARNING: {msg}")


# ---------------------------------------------------------------------------
# Rendering helpers — copied verbatim from policy_measure_common.py
# ---------------------------------------------------------------------------
def clean(value, limit: int | None = None) -> str:
    if value is None:
        text = ""
    else:
        try:
            if pd.isna(value):
                text = ""
            else:
                text = str(value)
        except (TypeError, ValueError):
            text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _direction_of(score) -> str:
    """policy_direction is rule-derived: sign(score). + = tightening, - = easing,
    0/missing = neutral."""
    s = pd.to_numeric(pd.Series([score]), errors="coerce").iloc[0]
    if pd.isna(s) or s == 0:
        return "neutral"
    return "tightening" if s > 0 else "easing"


def _xml_escape(value, limit: int | None = None) -> str:
    s = clean(value, limit)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_policy_decision_blocks(ymd: str, linked_decisions: pd.DataFrame) -> str:
    meeting = linked_decisions[linked_decisions["ymd"].astype(str) == str(ymd)].copy()
    if meeting.empty:
        return "No adopted policy decisions found for this meeting."

    blocks: list[str] = []
    for _, row in meeting.sort_values("decision_id").iterrows():
        blocks.append("\n".join([
            "  <decision>",
            f"    <id>{_xml_escape(row.get('decision_id'))}</id>",
            f"    <adoption_date>{_xml_escape(row.get('ymd'))}</adoption_date>",
            f"    <policy_direction>{_direction_of(row.get('score'))}</policy_direction>",
            f"    <type>{_xml_escape(row.get('type'))}</type>",
            f"    <communication_subtype>{_xml_escape(row.get('communication_subtype')) or 'none'}</communication_subtype>",
            f"    <description>{_xml_escape(row.get('description'))}</description>",
            f"    <adopted_policy_evidence>{_xml_escape(row.get('adopted_policy_evidence'), 900)}</adopted_policy_evidence>",
            "  </decision>",
        ]))
    return "\n".join(blocks)


def format_alternatives(ymd: str, alternatives_df: pd.DataFrame) -> str:
    meeting = alternatives_df[alternatives_df["ymd"].astype(str) == str(ymd)].copy()
    if meeting.empty:
        return "No policy alternatives found for this meeting."

    lines: list[str] = []
    for _, row in meeting.iterrows():
        lines.append(f"=== {clean(row.get('label'))} ===")
        description = clean(row.get("description"), 1200)
        statement = clean(row.get("policy_statement"), 2400)
        directive = clean(row.get("proposed_directive"), 2400)
        if description:
            lines.append(f"Description: {description}")
        if statement:
            lines.append(f"Policy statement: {statement}")
        if directive:
            lines.append(f"Proposed directive: {directive}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_speeches(ymd: str, stablespeaker: str, transcript_df: pd.DataFrame) -> str:
    meeting = transcript_df[
        (transcript_df["ymd"].astype(str) == str(ymd))
        & pd.to_numeric(transcript_df["policy"], errors="coerce").fillna(0).eq(1)
        & transcript_df["stablespeaker"].astype(str).eq(str(stablespeaker))
    ].copy()
    if meeting.empty:
        return "No policy discussion speeches found for this speaker."

    lines: list[str] = []
    for idx, (_, row) in enumerate(meeting.sort_values("n").iterrows(), start=1):
        text = clean(row.get("combined"))
        if not text:
            continue
        lines.append(f"[{idx}] {clean(row.get('stablespeaker'))} ({clean(row.get('speechid'))}):")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip()


# Copied verbatim from 10_dynamic_position_alignment_scores.py
def format_speeches_full(meeting_ymd: str, stablespeaker: str, transcript_df: pd.DataFrame) -> str:
    """ALL of the focus speaker's speeches at the meeting, in speaking order — no
    policy-section filter."""
    meeting = transcript_df[
        (transcript_df["ymd"].astype(str) == str(meeting_ymd))
        & transcript_df["stablespeaker"].astype(str).eq(str(stablespeaker))
    ].copy()
    if meeting.empty:
        return "No speeches found for this speaker."
    lines: list[str] = []
    for idx, (_, row) in enumerate(meeting.sort_values("n").iterrows(), start=1):
        text = clean(row.get("combined"))
        if not text:
            continue
        lines.append(f"[{idx}] {clean(row.get('stablespeaker'))} ({clean(row.get('speechid'))}):")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip()


DECISION_BLOCK_TEMPLATE = """  <decision>
    <id>{decision_id}</id>
    <adoption_date>{decision_ymd}</adoption_date>
    <policy_direction>{policy_direction}</policy_direction>
    <type>{type}</type>
    <communication_subtype>{communication_subtype}</communication_subtype>
    <description>{description}</description>
    <adopted_policy_evidence>{adopted_policy_evidence}</adopted_policy_evidence>
  </decision>"""

DYNAMIC_PACKET_WRAPPER = """Meeting packet:

<policy_decisions>
{blocks}
</policy_decisions>

meeting_date: {meeting_ymd}   (this is {meetings_back} meeting(s) BEFORE adoption_date)"""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def read_transcripts() -> pd.DataFrame:
    print("Loading transcripts.dta ...")
    transcripts = pd.read_stata(TRANSCRIPTS_DTA)
    transcripts["ymd"] = transcripts["ymd"].astype(str)
    if "policy" not in transcripts.columns:
        transcripts["policy"] = pd.to_numeric(transcripts["alternative_start"], errors="coerce").fillna(0)
    else:
        transcripts["policy"] = pd.to_numeric(transcripts["policy"], errors="coerce").fillna(0)
    return transcripts


def read_linked_decisions() -> pd.DataFrame:
    decisions = pd.read_pickle(SOURCE_FILES["adopted_decisions"])
    decisions["ymd"] = decisions["ymd"].astype(str)
    links = pd.read_pickle(SOURCE_FILES["decision_alternative_links"])
    links["ymd"] = links["ymd"].astype(str)
    merge_keys = ["ymd", "description", "type", "communication_subtype", "score"]
    linked = links.merge(
        decisions[merge_keys + ["adopted_policy_evidence"]],
        on=merge_keys,
        how="left",
        validate="one_to_one",
    )
    if linked["adopted_policy_evidence"].isna().any():
        missing = int(linked["adopted_policy_evidence"].isna().sum())
        raise ValueError(f"Missing adopted-policy evidence for {missing} linked decision rows")
    return linked


def extract_instruction_prompts() -> dict[str, str]:
    prompts = {}
    for name, path in PROMPT_SOURCE_SCRIPTS.items():
        source = path.read_text(encoding="utf-8")
        match = re.search(r'INSTRUCTION_PROMPT = """(.*?)"""', source, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Could not extract INSTRUCTION_PROMPT from {path}")
        prompts[name] = match.group(1)
    return prompts


# ---------------------------------------------------------------------------
# Quote checking (shared with the apps)
# ---------------------------------------------------------------------------
from core.quotes import quote_match  # noqa: E402


# ---------------------------------------------------------------------------
# Static tools (position alignment + adoption contribution)
# ---------------------------------------------------------------------------
def speaking_order(ymd: str, transcripts: pd.DataFrame) -> dict[str, int]:
    """First policy-section appearance order for each speaker at the meeting."""
    meeting = transcripts[
        (transcripts["ymd"] == str(ymd))
        & transcripts["policy"].eq(1)
    ].sort_values("n")
    order: dict[str, int] = {}
    for speaker in meeting["stablespeaker"].dropna().astype(str):
        if speaker not in order:
            order[speaker] = len(order)
    return order


def build_static(transcripts, linked, alternatives, pos_scores, adopt_scores):
    meetings_rows, decisions_rows, alts_rows, speech_rows = [], [], [], []
    align_rows, adopt_rows = [], []

    for ymd, label in STATIC_MEETINGS.items():
        print(f"Static meeting {ymd} ({label})")
        linked_m = linked[linked["ymd"] == ymd].sort_values("decision_id")
        if linked_m.empty:
            raise ValueError(f"No linked decisions for meeting {ymd}")

        blocks_xml = format_policy_decision_blocks(ymd, linked)
        alts_text = format_alternatives(ymd, alternatives)
        meetings_rows.append({
            "ymd": ymd,
            "label": label,
            "decision_blocks_xml": blocks_xml,
            "alternatives_text": alts_text,
        })

        for _, row in linked_m.iterrows():
            decisions_rows.append({
                "ymd": ymd,
                "decision_id": clean(row["decision_id"]),
                "decision_index": int(re.search(r"\d+", str(row["decision_id"])).group(0)),
                "description": clean(row["description"]),
                "type": clean(row["type"]),
                "communication_subtype": clean(row.get("communication_subtype")) or "none",
                "decision_score": clean(row.get("score")),
                "policy_direction": _direction_of(row.get("score")),
                "adopted_policy_evidence": clean(row.get("adopted_policy_evidence"), 900),
                # Metadata below was NOT in the packet Claude saw (display it
                # only with a clear label in the app).
                "matched_alternatives": clean(row.get("matched_alternatives")) or "None",
                "choice_set_alternatives": clean(row.get("choice_set_alternatives")) or "None",
            })

        alts_m = alternatives[alternatives["ymd"].astype(str) == ymd]
        for _, row in alts_m.iterrows():
            alts_rows.append({
                "ymd": ymd,
                "label": clean(row.get("label")),
                "description": clean(row.get("description"), 1200),
                "policy_statement": clean(row.get("policy_statement"), 2400),
                "proposed_directive": clean(row.get("proposed_directive"), 2400),
            })

        # Speakers = exactly the sample Claude scored, in policy speaking order.
        pos_m = pos_scores[pos_scores["ymd"].astype(str) == ymd]
        adopt_m = adopt_scores[adopt_scores["ymd"].astype(str) == ymd]
        speakers = sorted(set(pos_m["stablespeaker"].astype(str)))
        adopt_speakers = sorted(set(adopt_m["stablespeaker"].astype(str)))
        if speakers != adopt_speakers:
            warn(f"{ymd}: alignment/adoption speaker sets differ "
                 f"({set(speakers) ^ set(adopt_speakers)})")
        order = speaking_order(ymd, transcripts)
        speakers = sorted(speakers, key=lambda s: order.get(s, 999))

        for rank, speaker in enumerate(speakers):
            text = format_speeches(ymd, speaker, transcripts)
            if text == "No policy discussion speeches found for this speaker.":
                warn(f"{ymd}/{speaker}: no policy-section speeches found")
            speech_rows.append({
                "ymd": ymd,
                "stablespeaker": speaker,
                "speaker_order": rank,
                "speeches_text": text,
            })

        speech_lookup = {r["stablespeaker"]: r["speeches_text"]
                         for r in speech_rows if r["ymd"] == ymd}
        valid_ids = set(d["decision_id"] for d in decisions_rows if d["ymd"] == ymd)

        for source, target, col in ((pos_m, align_rows, "alignment"),
                                    (adopt_m, adopt_rows, "adoption_contribution")):
            for _, row in source.iterrows():
                did = clean(row["decision_id"])
                if did not in valid_ids:
                    warn(f"{ymd}: score row for unknown decision {did}")
                    continue
                speaker = str(row["stablespeaker"])
                evidence = clean(row.get("evidence"))
                target.append({
                    "ymd": ymd,
                    "stablespeaker": speaker,
                    "decision_id": did,
                    "claude_score": int(row[col]),
                    "claude_evidence": evidence,
                    "quote_match": quote_match(evidence, speech_lookup.get(speaker, "")),
                })

    return (pd.DataFrame(meetings_rows), pd.DataFrame(decisions_rows),
            pd.DataFrame(alts_rows), pd.DataFrame(speech_rows),
            pd.DataFrame(align_rows), pd.DataFrame(adopt_rows))


# ---------------------------------------------------------------------------
# Dynamic tool
# ---------------------------------------------------------------------------
def build_dynamic(transcripts, linked, dyn_scores):
    cells = []
    linked = linked.copy()
    linked["decision_ymd"] = linked["ymd"].astype(str).str.replace("-", "")
    linked["decision_id"] = linked["decision_id"].astype(str)

    for entry in DYNAMIC_SAMPLE:
        dymd, did = entry["decision_ymd"], entry["decision_id"]
        sub = dyn_scores[
            (dyn_scores["decision_ymd"].astype(str) == dymd)
            & (dyn_scores["decision_id"].astype(str) == did)
        ]
        if sub.empty:
            raise ValueError(f"No dynamic scores for {dymd} {did}")

        dec = linked[(linked["decision_ymd"] == dymd) & (linked["decision_id"] == did)]
        if len(dec) != 1:
            raise ValueError(f"Expected one linked decision for {dymd} {did}, got {len(dec)}")
        dec = dec.iloc[0]
        decision_label = clean(sub["label"].iloc[0])

        meetings = sorted(sub["meeting_ymd"].astype(str).unique())
        window = entry["window"]
        if window != "all":
            n = int(window.replace("last", ""))
            meetings = meetings[-n:]
        print(f"Dynamic {dymd} {did} ({entry['short_name']}): "
              f"{len(meetings)} meetings x {len(entry['members'])} members")

        for member in entry["members"]:
            for seq, meeting_ymd in enumerate(meetings, start=1):
                rows = sub[
                    (sub["meeting_ymd"].astype(str) == meeting_ymd)
                    & (sub["stablespeaker"].astype(str) == member)
                ]
                if rows.empty:
                    warn(f"dynamic {dymd} {did} {meeting_ymd} {member}: "
                         f"no Claude score (member absent) — cell skipped")
                    continue
                row = rows.iloc[0]
                meetings_back = int(row["meetings_back"])
                speeches = format_speeches_full(meeting_ymd, member, transcripts)
                if speeches == "No speeches found for this speaker.":
                    warn(f"dynamic {dymd} {did} {meeting_ymd} {member}: no speeches")
                evidence = clean(row.get("evidence"))
                cells.append({
                    "decision_ymd": dymd,
                    "decision_id": did,
                    "decision_label": decision_label,
                    "short_name": entry["short_name"],
                    "meeting_ymd": meeting_ymd,
                    "meetings_back": meetings_back,
                    "seq": seq,
                    "n_meetings": len(meetings),
                    "stablespeaker": member,
                    "description": clean(dec["description"]),
                    "type": clean(dec["type"]),
                    "communication_subtype": clean(dec.get("communication_subtype")) or "none",
                    "decision_score": clean(dec.get("score")),
                    "policy_direction": _direction_of(dec.get("score")),
                    "adopted_policy_evidence": clean(dec.get("adopted_policy_evidence"), 900),
                    "packet_text": build_dynamic_decision_packet(
                        {**dec.to_dict(), "decision_ymd": dymd}, meeting_ymd, meetings_back
                    ),
                    "speeches_text": speeches,
                    "claude_score": int(row["alignment"]),
                    "claude_evidence": evidence,
                    "claude_reasoning": clean(row.get("reasoning")),
                    "quote_match": quote_match(evidence, speeches),
                })
    return pd.DataFrame(cells)


def build_dynamic_decision_packet(decision: dict, meeting_ymd: str, meetings_back: int) -> str:
    dec = pd.Series(decision)
    block = DECISION_BLOCK_TEMPLATE.format(
        decision_id=_xml_escape(dec["decision_id"]),
        decision_ymd=_xml_escape(dec["decision_ymd"]),
        policy_direction=_direction_of(dec.get("score")),
        type=_xml_escape(dec.get("type", "")),
        communication_subtype=_xml_escape(dec.get("communication_subtype")) or "none",
        description=_xml_escape(dec.get("description", "")),
        adopted_policy_evidence=_xml_escape(dec.get("adopted_policy_evidence", ""), 900),
    )
    return DYNAMIC_PACKET_WRAPPER.format(
        blocks=block,
        meeting_ymd=_xml_escape(meeting_ymd),
        meetings_back=int(meetings_back),
    )


# ---------------------------------------------------------------------------
# Transcript viewer extract
# ---------------------------------------------------------------------------
def build_transcript_view(transcripts: pd.DataFrame, ymds: set[str]) -> pd.DataFrame:
    rows = []
    for ymd in sorted(ymds):
        meeting = transcripts[transcripts["ymd"] == ymd].sort_values("n")
        if meeting.empty:
            warn(f"transcript viewer: no rows for meeting {ymd}")
            continue
        for _, row in meeting.iterrows():
            text = clean(row.get("combined"))
            if not text:
                continue
            title = clean(row.get("titletidy"))
            name = clean(row.get("stablespeaker"))
            label = f"{title} {name}".strip() if title else (name or "UNKNOWN")
            rows.append({
                "ymd": ymd,
                "n": int(row["n"]),
                "speaker_label": label,
                "stablespeaker": name,
                "text": text,
                "is_policy": bool(row.get("policy") == 1),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, path in SOURCE_FILES.items():
        if not path.exists():
            raise FileNotFoundError(f"{name}: {path}")

    transcripts = read_transcripts()
    linked = read_linked_decisions()
    alternatives = pd.read_pickle(SOURCE_FILES["alternatives"])
    alternatives["ymd"] = alternatives["ymd"].astype(str)
    pos_scores = pd.read_pickle(SOURCE_FILES["position_alignment"])
    adopt_scores = pd.read_pickle(SOURCE_FILES["adoption_contribution"])
    dyn_scores = pd.read_pickle(SOURCE_FILES["dynamic_position_alignment"])

    meetings, decisions, alts, speeches, align_scores, adopt_out = build_static(
        transcripts, linked, alternatives, pos_scores, adopt_scores
    )
    dynamic_cells = build_dynamic(transcripts, linked, dyn_scores)

    view_ymds = set(STATIC_MEETINGS) | set(dynamic_cells["meeting_ymd"].astype(str))
    transcript_view = build_transcript_view(transcripts, view_ymds)

    prompts = extract_instruction_prompts()

    outputs = {
        "static_meetings.parquet": meetings,
        "static_decisions.parquet": decisions,
        "static_alternatives.parquet": alts,
        "static_speeches.parquet": speeches,
        "scores_alignment.parquet": align_scores,
        "scores_adoption.parquet": adopt_out,
        "dynamic_cells.parquet": dynamic_cells,
        "transcripts_view.parquet": transcript_view,
    }
    for filename, df in outputs.items():
        df.to_parquet(OUT_DIR / filename, index=False)
        print(f"Wrote {filename}: {len(df)} rows")

    (OUT_DIR / "prompts.json").write_text(
        json.dumps(prompts, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    content_hash = hashlib.sha256()
    for filename in sorted(outputs):
        content_hash.update((OUT_DIR / filename).read_bytes())
    data_version = content_hash.hexdigest()[:12]

    def _stats(df, kind):
        nz = df[df["claude_score"] != 0] if kind == "nonzero" else df[df["claude_score"] > 0]
        counts = nz["quote_match"].value_counts().to_dict()
        return {k: int(v) for k, v in counts.items()} | {"total": len(nz)}

    meta = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "data_version": data_version,
        "sources": {name: str(path) for name, path in SOURCE_FILES.items()},
        "source_mtimes": {
            name: datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            for name, path in SOURCE_FILES.items()
        },
        "counts": {name: len(df) for name, df in outputs.items()},
        "quote_found_nonzero": {
            "alignment": _stats(align_scores, "nonzero"),
            "adoption": _stats(adopt_out, "positive"),
            "dynamic": _stats(dynamic_cells, "nonzero"),
        },
        "warnings": WARNINGS,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nData version: {data_version}")
    print(f"Quote-found (nonzero scores): {meta['quote_found_nonzero']}")
    if WARNINGS:
        print(f"{len(WARNINGS)} warnings (see meta.json)")
    print("Done.")


if __name__ == "__main__":
    main()
