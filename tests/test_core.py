"""Plain-python sanity checks (no streamlit server needed).

Run from the repo root:  python tests/test_core.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import export  # noqa: E402
from core.quotes import find_quote_ranges, quote_match  # noqa: E402
from core.specs import (  # noqa: E402
    DYNAMIC_KEY_FIELDS,
    DYNAMIC_RECORD_COLUMNS,
    STATIC_KEY_FIELDS,
    STATIC_RECORD_COLUMNS,
    STATIC_SPECS,
)

DATA = Path(__file__).resolve().parent.parent / "data"
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {message}")
    if not condition:
        FAILURES.append(message)


def test_data_files():
    print("Data files:")
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    check(bool(meta.get("data_version")), "meta.json has data_version")

    prompts = json.loads((DATA / "prompts.json").read_text(encoding="utf-8"))
    for key in ("position_alignment", "dynamic_position_alignment", "adoption_contribution"):
        check(len(prompts.get(key, "")) > 1000, f"prompts.json has full {key} prompt")

    meetings = pd.read_parquet(DATA / "static_meetings.parquet")
    decisions = pd.read_parquet(DATA / "static_decisions.parquet")
    speeches = pd.read_parquet(DATA / "static_speeches.parquet")
    check(len(meetings) == 5, "5 static meetings")

    for scores_file in ("scores_alignment.parquet", "scores_adoption.parquet"):
        scores = pd.read_parquet(DATA / scores_file)
        merged = scores.merge(decisions[["ymd", "decision_id"]],
                              on=["ymd", "decision_id"], how="left", indicator=True)
        check((merged["_merge"] == "both").all(),
              f"{scores_file}: every score row joins to a decision")
        merged2 = scores.merge(speeches[["ymd", "stablespeaker"]].drop_duplicates(),
                               on=["ymd", "stablespeaker"], how="left", indicator=True)
        check((merged2["_merge"] == "both").all(),
              f"{scores_file}: every score row has a speeches extract")
        check(not scores.duplicated(["ymd", "stablespeaker", "decision_id"]).any(),
              f"{scores_file}: no duplicate keys")
        # full grid: every speaker has every decision of the meeting
        grid = scores.groupby("ymd").apply(
            lambda g: g["stablespeaker"].nunique() * g["decision_id"].nunique() == len(g),
            include_groups=False,
        )
        check(bool(grid.all()), f"{scores_file}: complete speaker x decision grid")

    cells = pd.read_parquet(DATA / "dynamic_cells.parquet")
    check(len(cells) == 153, f"dynamic_cells has 153 rows (got {len(cells)})")
    check(not cells.duplicated(
        ["decision_ymd", "decision_id", "meeting_ymd", "stablespeaker"]).any(),
        "dynamic_cells: no duplicate keys")
    check(cells["speeches_text"].str.len().gt(0).all(), "dynamic_cells: all have speeches")
    check(cells["packet_text"].str.contains("BEFORE adoption_date").all(),
          "dynamic_cells: packet text carries the run-up framing")

    tv = pd.read_parquet(DATA / "transcripts_view.parquet")
    needed = set(meetings["ymd"]) | set(cells["meeting_ymd"])
    check(needed <= set(tv["ymd"].unique()),
          "transcripts_view covers all static + dynamic meetings")


def test_quote_logic():
    print("Quote matching:")
    speech = '[1] SMITH (x_1):\nI support alternative B. The funds rate should go to 5-1/4 percent now.'
    check(quote_match("The funds rate should go to 5-1/4 percent now.", speech) == "found",
          "verbatim quote -> found")
    check(quote_match('"The funds rate should go to 5-1/4 percent" and '
                      '"we must act today without any further hesitation"',
                      speech) == "partial", "one of two fragments -> partial")
    check(quote_match("Rates must rise immediately and without delay.", speech) == "not_found",
          "absent quote -> not_found")
    check(quote_match("No explicit statement found.", speech) is None,
          "zero-score sentinel -> None")
    ranges = find_quote_ranges(speech, ["The funds rate should go to 5-1/4 percent now."])
    check(len(ranges) == 1 and speech[ranges[0][0]:ranges[0][1]].startswith("The funds"),
          "highlight range indexes into original text")


class FakeUpload(io.BytesIO):
    pass


def test_export_roundtrip():
    print("Export / restore round-trip:")
    records = {
        "20081216|YELLEN|d001": {
            "ymd": "20081216", "stablespeaker": "YELLEN", "decision_id": "d001",
            "decision_index": 1, "description": "Cut the funds rate.",
            "claude_score": 2, "claude_evidence": "I support this.",
            "quote_match": "found", "supports_evidence": "yes", "human_score": 1,
            "confidence": "high", "notes": "", "completed": True,
            "completed_at": "2026-07-06T12:00:00",
        }
    }
    spec = STATIC_SPECS["position_alignment"]
    js, name = export.generate_results_json(
        spec["tool"], "v1", "BM", records, "2026-07-06T11:00:00", STATIC_RECORD_COLUMNS)
    check(name.startswith("position_alignment_BM_"), "JSON filename carries tool + coder")
    parsed = json.loads(js)
    check(parsed["metadata"]["num_completed"] == 1, "JSON metadata counts completed")
    check(parsed["records"][0]["coder_id"] == "BM", "rows are stamped with coder_id")
    check(parsed["records"][0]["tool"] == "position_alignment", "rows are stamped with tool")

    ok, msg, restored = export.restore_from_uploaded_json(
        FakeUpload(js.encode("utf-8")), "position_alignment", STATIC_KEY_FIELDS)
    check(ok, f"restore succeeds ({msg})")
    check(set(restored["records"]) == set(records), "restore rebuilds the same keys")
    check(restored["records"]["20081216|YELLEN|d001"]["human_score"] == 1,
          "restored record keeps human_score")

    ok2, msg2, _ = export.restore_from_uploaded_json(
        FakeUpload(js.encode("utf-8")), "adoption_contribution", STATIC_KEY_FIELDS)
    check(not ok2, "restore rejects a file from a different tool")

    csv, _ = export.generate_results_csv(
        spec["tool"], "v1", "BM", records, STATIC_RECORD_COLUMNS)
    df = pd.read_csv(io.StringIO(csv))
    check(list(df.columns) == STATIC_RECORD_COLUMNS, "CSV has the documented column order")

    # dynamic schema sanity
    check(set(DYNAMIC_KEY_FIELDS) <= set(DYNAMIC_RECORD_COLUMNS),
          "dynamic key fields are all in the record columns")


def test_apps_import():
    print("App engines import cleanly:")
    import core.dynamic_app  # noqa: F401
    import core.static_app  # noqa: F401
    check(True, "core.static_app / core.dynamic_app import")


if __name__ == "__main__":
    test_data_files()
    test_quote_logic()
    test_export_roundtrip()
    test_apps_import()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURES")
        sys.exit(1)
    print("All checks passed.")
