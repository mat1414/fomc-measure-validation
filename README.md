# FOMC Measure Validation Tools

Three Streamlit apps for human-coder validation of the v5 LLM-extracted FOMC
measures. Human coders ("RAs") review Claude's score for each cell — seeing
**exactly the text Claude saw** — and record their own assessment.

| App | Measure | Scale | Unit of work |
|---|---|---|---|
| `app_alignment.py` | Position alignment (static) | -2..+2 | speaker x decision at the adoption meeting |
| `app_dynamic.py` | Dynamic position alignment | -2..+2 | member x run-up meeting for a landmark decision |
| `app_adoption.py` | Adoption contribution | 0..3 | speaker x decision at the adoption meeting |

## Validation sample

Defined in [sample_config.py](sample_config.py):

- **Static tools**: the three meetings used for the old paper's validation
  (Aug 1994, Dec 2008, Aug 2011), every scored speaker — 324 speaker x
  decision pairs per measure, organized as one screen per speaker.
- **Dynamic tool**: three landmark decisions (ZLB Dec 2008, Evans rule
  Dec 2012, Liftoff Dec 2015), 6 stratified members each, coded across the
  run-up window oldest-meeting-first, plus a 9-cell QE1 audit slice —
  153 cells total.

## How the RAs use it

1. Open the app URL, enter your coder ID (initials).
2. Pick a meeting (static tools) or decision + member (dynamic tool).
3. For each cell: read the speeches (Claude's evidence quotes are
   highlighted; a badge flags quotes that were not found verbatim), review
   Claude's score/evidence, then record: does the evidence support the score
   (yes/partially/no), your own score, your confidence, optional notes.
4. **Download the JSON save file often** (sidebar). Progress lives only in
   the browser session — if the connection drops, restore by uploading the
   JSON file in the sidebar. The app reminds you every 10 unsaved
   assessments.
5. When done, send both the JSON and CSV downloads to the research team.

Every output row is self-describing: it carries the tool name, data version,
coder id, and the full join key (`ymd`/`stablespeaker`/`decision_id`, plus
`decision_ymd`/`meeting_ymd`/`meetings_back` for the dynamic tool), so files
merge 1:1 onto the master v5 datasets.

## What the coder sees vs. what Claude saw

The packets are frozen at build time by [build_data.py](build_data.py), which
copies the rendering code verbatim from `kv_code/claude_measures_v5`
(same cleaning, truncation limits, and policy-section filter) and extracts
the instruction prompts from the source scripts. In each app:

- the decision blocks, alternatives, and speeches panels are exactly what
  Claude received (a "Raw packets" expander shows the literal text);
- the full-meeting transcript viewer is clearly labeled as context Claude
  did **not** see;
- static tools show only the speaker's **policy-section** speeches (that is
  all Claude saw); the dynamic tool shows **all** the member's speeches
  (that is what Claude saw there).

## Deployment (GitHub -> Streamlit Community Cloud)

1. Push this repo to GitHub (data files are included; ~a few MB).
2. On [share.streamlit.io](https://share.streamlit.io), create **three**
   apps from the same repo, one per main file: `app_alignment.py`,
   `app_dynamic.py`, `app_adoption.py`.
3. In each app's **Settings** (three-dot menu), set **Python version = 3.13**.
4. Give each RA the URL for their assigned tool.

## If an app shows "Oh no. Error running app"

The real error is only visible when the app owner is signed in: open the app
URL and click **Manage app** (bottom right) to see the boot log.

Known failure modes (July 2026 outages):

- **`Segmentation fault` in the log.** Community Cloud has had a
  platform-level bug since ~2026-07-10 where a container occasionally
  segfaults at boot or on a session reconnect, independent of package
  versions. **Fix: just reboot the app** (three-dot menu -> Reboot, either in
  the console app list or the Manage-app panel). One retry is usually enough.
- **Python version reset.** The platform migrated apps to Python 3.14 on
  ~2026-07-11, which broke boot outright. Check Settings -> Python version is
  **3.13** for all three apps.
- **Dependency drift.** The cloud re-resolves `requirements.txt` from scratch
  on every reboot/wake, so the file pins the *entire* dependency tree, and
  `streamlit` is deliberately held at **1.56.0** — the last release using the
  battle-tested Tornado server. streamlit >= 1.57 ships a new
  uvicorn/websockets server that segfaulted on Community Cloud (crash on
  "Session with id ... is already connected"). Do not unpin or bump pins
  without testing (see `tests/` and run the apps locally first).

RA work is never lost to a crash **if they download the JSON save file**
regularly — remind them.

## Local development

```bash
pip install -r requirements.txt
streamlit run app_alignment.py    # or app_dynamic.py / app_adoption.py
python tests/test_core.py         # sanity checks
```

## Rebuilding the frozen data

Only needed when the sample or the source v5 data changes. On a machine with
the source datasets (paths at the top of `build_data.py`):

```bash
python build_data.py
```

Sources of record:
- Claude scores: `fed_wsj/kv_analysis/output_v5/claude_output/analysis_files/`
- Decision context: `.../claude_output/{adopted_decisions,decision_alternative_links,alternatives}.pkl`
- Transcripts: `_earlystage/fomctidy/data/transcripts.dta`

The build stamps a `data_version` hash into `data/meta.json`; it is embedded
in every exported row so results can always be traced to the data they were
coded against. `meta.json` also records source file mtimes, row counts, and
quote-verification statistics.
