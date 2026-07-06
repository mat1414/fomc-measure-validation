"""Save / restore / export. Every exported row is self-describing: it carries
the tool name, data version, coder id, and the full join key back to the
master v5 datasets."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
        return super().default(obj)


def record_key(record: dict, key_fields: list[str]) -> str:
    return "|".join(str(record[f]) for f in key_fields)


def stamp_records(records: dict, tool: str, data_version: str, coder_id: str) -> list[dict]:
    stamped = []
    for rec in records.values():
        stamped.append({
            "tool": tool,
            "data_version": data_version,
            "coder_id": coder_id,
            **rec,
        })
    return stamped


def generate_results_json(
    tool: str,
    data_version: str,
    coder_id: str,
    records: dict,
    started_at: str,
    columns: list[str],
) -> tuple[str, str]:
    rows = stamp_records(records, tool, data_version, coder_id)
    completed = sum(1 for r in rows if r.get("completed"))
    output = {
        "metadata": {
            "tool": tool,
            "app_version": "1.0",
            "data_version": data_version,
            "coder_id": coder_id,
            "started_at": started_at,
            "last_saved": datetime.now().isoformat(timespec="seconds"),
            "num_records": len(rows),
            "num_completed": completed,
        },
        "records": [{col: r.get(col) for col in columns} for r in rows],
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{tool}_{coder_id}_{timestamp}.json"
    return json.dumps(output, indent=2, ensure_ascii=False, cls=NumpyEncoder), filename


def generate_results_csv(
    tool: str,
    data_version: str,
    coder_id: str,
    records: dict,
    columns: list[str],
) -> tuple[str, str]:
    rows = stamp_records(records, tool, data_version, coder_id)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df = df[columns]
    sort_keys = [c for c in ("ymd", "decision_ymd", "stablespeaker", "seq", "decision_index")
                 if c in df.columns]
    if len(df) > 0 and sort_keys:
        df = df.sort_values(sort_keys)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{tool}_{coder_id}_{timestamp}.csv"
    return df.to_csv(index=False), filename


def restore_from_uploaded_json(
    uploaded_file,
    expected_tool: str,
    key_fields: list[str],
) -> tuple[bool, str, Optional[dict]]:
    try:
        data = json.loads(uploaded_file.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False, "Not a valid JSON save file.", None

    metadata = data.get("metadata", {})
    tool = metadata.get("tool")
    if tool != expected_tool:
        return False, (
            f"This save file is for the '{tool}' tool, not '{expected_tool}'. "
            "Please upload it in the matching app."
        ), None

    records: dict[str, dict] = {}
    for rec in data.get("records", []):
        if any(rec.get(f) in (None, "") for f in key_fields):
            continue
        records[record_key(rec, key_fields)] = rec

    if not records:
        return False, "The save file contains no restorable records.", None

    restored = {
        "coder_id": metadata.get("coder_id", ""),
        "started_at": metadata.get("started_at"),
        "data_version": metadata.get("data_version"),
        "records": records,
    }
    completed = sum(1 for r in records.values() if r.get("completed"))
    return True, f"Restored {len(records)} records ({completed} completed).", restored
