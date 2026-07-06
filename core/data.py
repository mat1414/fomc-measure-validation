"""Cached loaders for the frozen data extracts in ``data/``."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data(show_spinner=False)
def load_parquet(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / name)


@st.cache_data(show_spinner=False)
def load_meta() -> dict:
    return json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_prompts() -> dict:
    return json.loads((DATA_DIR / "prompts.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_static_bundle(scores_file: str) -> dict:
    return {
        "meetings": load_parquet("static_meetings.parquet"),
        "decisions": load_parquet("static_decisions.parquet"),
        "alternatives": load_parquet("static_alternatives.parquet"),
        "speeches": load_parquet("static_speeches.parquet"),
        "scores": load_parquet(scores_file),
    }


@st.cache_data(show_spinner=False)
def load_dynamic_cells() -> pd.DataFrame:
    df = load_parquet("dynamic_cells.parquet")
    return df.sort_values(["decision_ymd", "decision_id", "stablespeaker", "seq"])


@st.cache_data(show_spinner=False)
def load_transcript_view(ymd: str) -> pd.DataFrame:
    df = load_parquet("transcripts_view.parquet")
    return df[df["ymd"] == ymd].sort_values("n")
