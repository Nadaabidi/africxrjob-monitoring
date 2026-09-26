
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
import pandas as pd

TRUE_WORDS = {"1","true","yes","y","oui","o","present","présent","presente","présente","attended","selected","completed","done","x","✓"}
FALSE_WORDS = {"0","false","no","n","non","absent"}

def slug(s):
    s = "" if s is None else str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

def clean_text(v):
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()

def to_bool(v):
    if pd.isna(v) or str(v).strip() == "":
        return False
    s = clean_text(v).lower()
    if s in TRUE_WORDS:
        return True
    if s in FALSE_WORDS:
        return False
    # If a registration/presence column contains a name/timestamp/mark, consider it present
    return bool(s)

def standardize_gender(v):
    s = slug(v)
    if not s:
        return ""
    if s in {"f","female","femme","woman","women","feminin","feminine"}:
        return "Female"
    if s in {"m","male","homme","man","men","masculin","masculine"}:
        return "Male"
    return clean_text(v)

def safe_date(v):
    if pd.isna(v) or str(v).strip() == "":
        return ""
    dt = pd.to_datetime(v, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return clean_text(v)
    return dt.strftime("%Y-%m-%d")

def participant_key(row):
    email = slug(row.get("email",""))
    if email:
        return "email:" + email
    phone = re.sub(r"\D", "", clean_text(row.get("phone","")))
    if len(phone) >= 6:
        return "phone:" + phone
    name = slug(row.get("participant_name",""))
    inst = slug(row.get("institution",""))
    if name:
        return f"name:{name}|inst:{inst}"
    return ""


def infer_location(path_text):
    s = slug(path_text)
    checks = [("borj_cedria", "Borj Cedria"), ("gabes", "Gabès"), ("monastir", "Monastir"), ("nabeul", "Nabeul"), ("university_of_tunis", "Tunis"), ("tunis", "Tunis")]
    for key, label in checks:
        if key in s:
            return label
    return ""

def infer_cohort(path_text):
    s = slug(path_text)
    if "cohort_1" in s or "cohort1" in s: return "Cohort 1"
    if "cohort_2" in s or "cohort2" in s: return "Cohort 2"
    return ""

def infer_subtype(path_text):
    s = slug(path_text)
    if "training_closing_day" in s:
        if "ecosystem" in s: return "Training Closing Day - Ecosystem"
        if "enterprises" in s or "enterprise" in s: return "Training Closing Day - Enterprises"
        if "students" in s or "student" in s: return "Training Closing Day - Students"
        return "Training Closing Day"
    if "ecosystem_open_day" in s: return "Ecosystem Open Day"
    if "open_day" in s: return "Open Day"
    if "online" in s and "training" in s: return "Online Training"
    if ("on_site" in s or "onsite" in s) and "training" in s: return "On-site Training"
    if "testing_session" in s: return "Testing Session"
    return ""


def infer_date_from_filename(path_text):
    import re
    from datetime import date
    s = slug(path_text)
    months = {
        "january":1,"janvier":1,"february":2,"fevrier":2,"march":3,"mars":3,
        "april":4,"avril":4,"may":5,"mai":5,"june":6,"juin":6,"july":7,"juillet":7,
        "august":8,"aout":8,"september":9,"septembre":9,"october":10,"octobre":10,
        "november":11,"novembre":11,"december":12,"decembre":12
    }
    m = re.search(r"(?:^|_)([0-3]?\d)_([a-z]+)_((?:20)\d{2})(?:_|$)", s)
    if m and m.group(2) in months:
        try: return date(int(m.group(3)), months[m.group(2)], int(m.group(1))).isoformat()
        except ValueError: return ""
    return ""
