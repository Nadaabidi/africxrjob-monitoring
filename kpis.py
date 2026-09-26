
from __future__ import annotations
import pandas as pd
from monitoring_utils import participant_key

BOOL_COLS = ["registered","attended","completed","selected","application"]

def _bool_series(s):
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(["true","1","yes","oui","x","✓"])

def prepare_participants(df):
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy().fillna("")
    for c in BOOL_COLS:
        if c in d:
            d[c] = _bool_series(d[c])
    if "participant_id" not in d:
        d["participant_id"] = ""
    empty = d["participant_id"].astype(str).str.strip().eq("")
    if empty.any():
        d.loc[empty, "participant_id"] = d.loc[empty].apply(participant_key, axis=1)
    return d

def prepare_events(df):
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy().fillna("")
    numeric = ["registered","attended","completed","applications","selected","women","men","enterprises","universities","projects"]
    for c in numeric:
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    return d

def calc_kpis(participants, events):
    p = prepare_participants(participants)
    e = prepare_events(events)

    # Participant-level totals (deduplicated within current filter)
    if not p.empty:
        p_unique = p.drop_duplicates("participant_id", keep="first") if "participant_id" in p else p
        registered_p = int(p_unique["registered"].sum()) if "registered" in p_unique else len(p_unique)
        attended_p = int(p_unique["attended"].sum()) if "attended" in p_unique else 0
        completed_p = int(p_unique["completed"].sum()) if "completed" in p_unique else 0
        selected_p = int(p_unique["selected"].sum()) if "selected" in p_unique else 0
        applications_p = int(p_unique["application"].sum()) if "application" in p_unique else 0
        women_p = int(p_unique["gender"].astype(str).str.lower().isin(["female","woman","femme","f"]).sum()) if "gender" in p_unique else 0
        men_p = int(p_unique["gender"].astype(str).str.lower().isin(["male","man","homme","m"]).sum()) if "gender" in p_unique else 0
        institutions = p_unique["institution"].replace("", pd.NA).nunique() if "institution" in p_unique else 0
        regions = p_unique["region"].replace("", pd.NA).nunique() if "region" in p_unique else 0
        projects_p = p_unique["project_name"].replace("", pd.NA).nunique() if "project_name" in p_unique else 0
        enterprises_p = p_unique["enterprise"].replace("", pd.NA).nunique() if "enterprise" in p_unique else 0
    else:
        registered_p=attended_p=completed_p=selected_p=applications_p=women_p=men_p=institutions=regions=projects_p=enterprises_p=0

    # Event-level counts are used only when present. For programme summaries we take them as
    # additional evidence. Reconcile duplicates manually if the same people/counts exist in both layers.
    def esum(col):
        if e.empty or col not in e:
            return 0
        return int(e[col].fillna(0).sum())

    registered = registered_p + esum("registered")
    attended = attended_p + esum("attended")
    completed = completed_p + esum("completed")
    applications = applications_p + esum("applications")
    selected = selected_p + esum("selected")
    women = women_p + esum("women")
    men = men_p + esum("men")
    projects = projects_p + esum("projects")
    enterprises = enterprises_p + esum("enterprises")
    universities = esum("universities")

    attendance_rate = (attended / registered * 100) if registered else None
    completion_den = selected if selected else registered
    completion_rate = (completed / completion_den * 100) if completion_den else None
    known_gender = women + men
    female_share = (women / known_gender * 100) if known_gender else None

    return {
        "applications": applications,
        "selected": selected,
        "registered": registered,
        "attended": attended,
        "attendance_rate": attendance_rate,
        "completed": completed,
        "completion_rate": completion_rate,
        "women": women,
        "men": men,
        "female_share": female_share,
        "institutions": int(institutions),
        "regions": int(regions),
        "projects": int(projects),
        "enterprises": int(enterprises),
        "universities": int(universities),
        "events": int(len(e)) if not e.empty else int(p["event_name"].replace("",pd.NA).nunique() if not p.empty and "event_name" in p else 0),
    }
