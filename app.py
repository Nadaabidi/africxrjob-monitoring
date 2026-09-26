
from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

from kpis import calc_kpis, prepare_participants, prepare_events

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT/"processed"
CONFIG = ROOT/"config"

st.set_page_config(page_title="AFRICXRJOB Monitoring", page_icon="📊", layout="wide")

@st.cache_data
def load_csv(path, columns=None):
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    try:
        return pd.read_csv(path).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns or [])

participants = prepare_participants(load_csv(PROCESSED/"participants_master.csv"))
events = prepare_events(load_csv(PROCESSED/"events_master.csv"))
inventory = load_csv(PROCESSED/"document_inventory.csv")
kpi_defs = load_csv(CONFIG/"kpi_definitions.csv")
import_log = load_csv(PROCESSED/"import_log.csv")

st.title("AFRICXRJOB — Monitoring Dashboard")
st.caption("Evidence-based monitoring • traceable sources • transparent KPI formulas")

# ---------- Global filters ----------
def _vals(df, col):
    if df.empty or col not in df:
        return []
    return sorted([x for x in df[col].astype(str).unique().tolist() if x])

all_types = sorted(set(_vals(participants, "event_type") + _vals(events, "event_type")))
all_categories = _vals(participants, "evidence_category")
all_subtypes = _vals(participants, "event_subtype")
all_cohorts = _vals(participants, "cohort")
all_locations = sorted(set(_vals(participants, "location") + _vals(events, "location")))

with st.sidebar:
    st.header("Filters")
    selected_categories = st.multiselect("Evidence category", all_categories, default=all_categories)
    selected_types = st.multiselect("Event type", all_types, default=all_types)
    selected_subtypes = st.multiselect("Activity subtype", all_subtypes, default=all_subtypes)
    selected_cohorts = st.multiselect("Cohort", all_cohorts, default=all_cohorts)
    selected_locations = st.multiselect("Location", all_locations, default=all_locations)
    st.divider()
    st.caption("Filters reflect AFRICXRJOB's six evidence folders plus filename-derived subtypes.")

pf = participants.copy()
ef = events.copy()

def apply_filter(df, col, selected):
    if df.empty or col not in df or not selected:
        return df
    return df[df[col].isin(selected)]

pf = apply_filter(pf, "evidence_category", selected_categories)
pf = apply_filter(pf, "event_type", selected_types)
pf = apply_filter(pf, "event_subtype", selected_subtypes)
pf = apply_filter(pf, "cohort", selected_cohorts)
pf = apply_filter(pf, "location", selected_locations)
ef = apply_filter(ef, "event_type", selected_types)
ef = apply_filter(ef, "location", selected_locations)

page = st.sidebar.radio(
    "View",
    ["Overview","Events","Participants","Indicators & formulas","Evidence & OCR","Data quality"]
)

if page == "Overview":
    k = calc_kpis(pf, ef)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Applications", f"{k['applications']:,}")
    c2.metric("Selected", f"{k['selected']:,}")
    c3.metric("Registered", f"{k['registered']:,}")
    c4.metric("Attended", f"{k['attended']:,}")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Attendance rate", "—" if k["attendance_rate"] is None else f"{k['attendance_rate']:.1f}%")
    c2.metric("Completed", f"{k['completed']:,}")
    c3.metric("Completion rate", "—" if k["completion_rate"] is None else f"{k['completion_rate']:.1f}%")
    c4.metric("Female participation", "—" if k["female_share"] is None else f"{k['female_share']:.1f}%")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Events", f"{k['events']:,}")
    c2.metric("Institutions", f"{k['institutions']:,}")
    c3.metric("Regions", f"{k['regions']:,}")
    c4.metric("Projects / prototypes", f"{k['projects']:,}")

    st.subheader("Participation by event type")
    if not pf.empty and "event_type" in pf:
        chart = pf.groupby("event_type", dropna=False)["participant_id"].nunique().sort_values(ascending=False)
        st.bar_chart(chart)
    elif not ef.empty:
        chart = ef.groupby("event_type")["attended"].sum().sort_values(ascending=False)
        st.bar_chart(chart)
    else:
        st.info("No monitoring data yet. Run `python ingest.py`, review the master files, then reload.")

    st.subheader("Important interpretation")
    st.info(
        "Participant-level data and manually entered event-level counts are both supported. "
        "Before donor reporting, reconcile events where the same participants/counts may exist in both layers to avoid double-counting."
    )

elif page == "Events":
    st.subheader("Event monitoring")
    if ef.empty:
        st.info("Add event-level records to `processed/events_master.csv`.")
    else:
        cols = [c for c in ["event_id","event_name","event_type","event_date","location","registered","attended","completed","applications","selected","women","men","enterprises","universities","projects","source_file"] if c in ef]
        st.dataframe(ef[cols], use_container_width=True, hide_index=True)
        if "attended" in ef and "event_name" in ef:
            tmp = ef[["event_name","attended"]].copy()
            tmp["attended"] = pd.to_numeric(tmp["attended"], errors="coerce").fillna(0)
            st.bar_chart(tmp.set_index("event_name"))

elif page == "Participants":
    st.subheader("Participant-level monitoring records")
    if pf.empty:
        st.info("No participant rows imported yet.")
    else:
        search = st.text_input("Search participant / institution / region / source")
        display = pf.copy()
        if search:
            q = search.lower()
            mask = display.astype(str).apply(lambda col: col.str.lower().str.contains(q, na=False)).any(axis=1)
            display = display[mask]
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download filtered participants CSV",
            display.to_csv(index=False).encode("utf-8-sig"),
            file_name="africxrjob_filtered_participants.csv",
            mime="text/csv"
        )

elif page == "Indicators & formulas":
    st.subheader("Indicator methodology")
    st.write(
        "These definitions make the monitoring claim auditable: each reported indicator should have "
        "a formula, a source/evidence trail, and a documented review rule."
    )
    st.dataframe(kpi_defs, use_container_width=True, hide_index=True)
    st.markdown("""
**Core formulas**

- **Attendance rate** = Attended ÷ Registered × 100
- **Completion rate** = Completed ÷ Selected × 100; if no formal selection stage exists, use Completed ÷ Registered × 100 and state that denominator.
- **Female participation** = Women ÷ Participants with known gender × 100
- **Selection rate** = Selected ÷ Applications × 100
- **Representation by region/institution** = distinct validated values in participant records
""")

elif page == "Evidence & OCR":
    st.subheader("Evidence inventory")
    if inventory.empty:
        st.info("Run `python ingest.py` first.")
    else:
        inv = inventory.copy()
        inv_types = sorted([x for x in inv["event_type"].astype(str).unique() if x]) if "event_type" in inv else []
        evfilter = st.multiselect("Evidence event type", inv_types, default=inv_types)
        if evfilter and "event_type" in inv:
            inv = inv[inv["event_type"].isin(evfilter)]
        st.dataframe(inv, use_container_width=True, hide_index=True)

        st.subheader("Search OCR text")
        q = st.text_input("Search extracted/OCR text")
        if q:
            hits = []
            for _, r in inv.iterrows():
                txt_rel = str(r.get("ocr_text_file","")).strip()
                if not txt_rel:
                    continue
                path = ROOT/txt_rel
                if path.exists():
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    pos = text.lower().find(q.lower())
                    if pos >= 0:
                        snippet = text[max(0,pos-180):pos+350].replace("\n"," ")
                        hits.append({"source_file":r["source_file"],"event_type":r.get("event_type",""),"snippet":snippet})
            st.dataframe(pd.DataFrame(hits), use_container_width=True, hide_index=True)

elif page == "Data quality":
    st.subheader("Review queue")
    if not pf.empty and "needs_review" in pf:
        review = pf[pf["needs_review"].astype(str).str.lower().isin(["true","1","yes","oui"])]
        st.metric("Participant rows marked for review", len(review))
        st.dataframe(review, use_container_width=True, hide_index=True)
    else:
        st.info("No participant review rows found.")

    st.subheader("Possible duplicate participant IDs")
    if not pf.empty and "participant_id" in pf:
        dup = pf[pf["participant_id"].astype(str).ne("") & pf["participant_id"].duplicated(keep=False)].sort_values("participant_id")
        st.dataframe(dup, use_container_width=True, hide_index=True)

    st.subheader("Import log")
    st.dataframe(import_log, use_container_width=True, hide_index=True)

    st.subheader("Evidence errors")
    if not inventory.empty and "status" in inventory:
        errs = inventory[inventory["status"].astype(str).ne("OK")]
        st.dataframe(errs, use_container_width=True, hide_index=True)
