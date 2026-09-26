from __future__ import annotations
from pathlib import Path
import json, hashlib
import pandas as pd

from monitoring_utils import (
    slug, clean_text, to_bool, standardize_gender, safe_date, participant_key,
    infer_location, infer_cohort, infer_subtype, infer_date_from_filename
)
from ocr_utils import extract_pdf_text, extract_image_text

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PROCESSED = ROOT / "processed"
OCR_DIR = PROCESSED / "ocr_text"
CONFIG = ROOT / "config"
SUPPORTED = {".xlsx",".xlsm",".csv",".pdf",".png",".jpg",".jpeg",".tif",".tiff"}


def load_folder_map():
    df = pd.read_csv(CONFIG / "folder_mapping.csv").fillna("")
    return {r["folder"]: r.to_dict() for _, r in df.iterrows()}


def read_event_rules():
    df = pd.read_csv(CONFIG/"event_types.csv").fillna("")
    return [(r["event_type"], [k.strip().lower() for k in str(r["keywords"]).split("|") if k.strip()]) for _, r in df.iterrows()]


def detect_event_type(path: Path, rules, folder_info):
    hay = str(path).replace("\\", "/").lower()
    # Specific filename rules first so opendays subtypes are not swallowed by folder defaults.
    for event_type, kws in rules:
        if kws and any(k in hay for k in kws):
            return event_type
    return folder_info.get("event_type", "Other")


def build_alias_map():
    raw = json.loads((CONFIG/"column_aliases.json").read_text(encoding="utf-8"))
    return {canon: {slug(canon), *(slug(x) for x in aliases)} for canon, aliases in raw.items()}


def find_columns(columns, amap):
    normalized = {c: slug(c) for c in columns}
    mapping = {}
    for canon, aliases in amap.items():
        for original, norm in normalized.items():
            if norm in aliases:
                mapping[canon] = original
                break
    return mapping


def _score_header_row(values, amap):
    norms = {slug(x) for x in values if clean_text(x)}
    alias_union = set().union(*amap.values())
    return len(norms & alias_union)


def read_excel_smart(path: Path, amap):
    """Read each sheet and detect a likely header row among the first 15 rows."""
    xls = pd.ExcelFile(path)
    out = {}
    for sheet in xls.sheet_names:
        preview = pd.read_excel(path, sheet_name=sheet, header=None, nrows=15)
        best_row, best_score = 0, -1
        for idx, row in preview.iterrows():
            score = _score_header_row(row.tolist(), amap)
            if score > best_score:
                best_row, best_score = idx, score
        out[sheet] = pd.read_excel(path, sheet_name=sheet, header=best_row)
    return out


def read_tabular(path: Path, amap):
    if path.suffix.lower() == ".csv":
        for enc in ("utf-8-sig","utf-8","latin-1"):
            try:
                return {"CSV": pd.read_csv(path, encoding=enc)}
            except Exception:
                pass
        raise ValueError("Could not read CSV")
    return read_excel_smart(path, amap)


def frame_to_participants(df, meta, source_file, source_sheet, amap):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.dropna(how="all").copy()
    mapping = find_columns(list(df.columns), amap)
    if "participant_name" not in mapping:
        return pd.DataFrame()

    rows = []
    for _, r in df.iterrows():
        name = clean_text(r.get(mapping["participant_name"], ""))
        if not name:
            continue
        row_date = safe_date(r.get(mapping.get("event_date", ""), "")) if "event_date" in mapping else ""
        out = {
            "participant_id": "",
            "participant_name": name,
            "gender": standardize_gender(r.get(mapping.get("gender",""), "")) if "gender" in mapping else "",
            "email": clean_text(r.get(mapping.get("email",""), "")) if "email" in mapping else "",
            "phone": clean_text(r.get(mapping.get("phone",""), "")) if "phone" in mapping else "",
            "institution": clean_text(r.get(mapping.get("institution",""), "")) if "institution" in mapping else "",
            "region": clean_text(r.get(mapping.get("region",""), "")) if "region" in mapping else meta["location"],
            "event_id": "",
            "event_name": clean_text(r.get(mapping.get("event_name",""), "")) if "event_name" in mapping else Path(source_file).stem,
            "event_type": meta["event_type"],
            "event_subtype": meta["event_subtype"],
            "evidence_category": meta["evidence_category"],
            "participant_group": meta["participant_group"],
            "cohort": meta["cohort"],
            "location": meta["location"],
            "event_date": row_date or meta["event_date"],
            "registered": True,
            "attended": to_bool(r.get(mapping.get("attended",""), "")) if "attended" in mapping else (meta["evidence_category"] != "Applications"),
            "completed": to_bool(r.get(mapping.get("completed",""), "")) if "completed" in mapping else False,
            "selected": to_bool(r.get(mapping.get("selected",""), "")) if "selected" in mapping else False,
            "application": to_bool(r.get(mapping.get("application",""), "")) if "application" in mapping else meta["evidence_category"] == "Applications",
            "project_name": clean_text(r.get(mapping.get("project_name",""), "")) if "project_name" in mapping else "",
            "enterprise": clean_text(r.get(mapping.get("enterprise",""), "")) if "enterprise" in mapping else "",
            "source_file": source_file,
            "source_sheet": source_sheet,
            "needs_review": True,
        }
        out["participant_id"] = participant_key(out)
        rows.append(out)
    return pd.DataFrame(rows)


def main():
    PROCESSED.mkdir(exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    folder_map = load_folder_map()
    rules = read_event_rules()
    amap = build_alias_map()

    inventory, imported_frames, logs = [], [], []
    all_files = [p for p in DATA.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED]

    for p in all_files:
        rel = p.relative_to(ROOT).as_posix()
        rel_to_data = p.relative_to(DATA)
        folder = rel_to_data.parts[0] if rel_to_data.parts else ""
        fcfg = folder_map.get(folder, {"evidence_category": folder, "event_type": "Other", "participant_group": ""})
        event_type = detect_event_type(p, rules, fcfg)
        subtype = infer_subtype(rel)
        if subtype.startswith("Training Closing Day"):
            event_type = "Training Closing Day"
        elif subtype == "Ecosystem Open Day":
            event_type = "Ecosystem Open Day"
        meta = {
            "folder": folder,
            "evidence_category": fcfg.get("evidence_category", folder),
            "participant_group": fcfg.get("participant_group", ""),
            "event_type": event_type,
            "event_subtype": subtype,
            "cohort": infer_cohort(rel),
            "location": infer_location(rel),
            "event_date": infer_date_from_filename(rel),
        }
        if "students" in slug(subtype): meta["participant_group"] = "Students"
        if "enterprises" in slug(subtype): meta["participant_group"] = "Enterprises"
        if "ecosystem" in slug(subtype): meta["participant_group"] = "Ecosystem Actors"

        stat = p.stat()
        rec = {
            "source_file": rel, "filename": p.name, "extension": p.suffix.lower(), **meta,
            "size_kb": round(stat.st_size/1024,1), "ocr_used": False,
            "ocr_text_file": "", "status": "OK", "notes": ""
        }
        try:
            ext = p.suffix.lower()
            if ext in {".xlsx",".xlsm",".csv"}:
                sheets = read_tabular(p, amap)
                for sheet, df in sheets.items():
                    pf = frame_to_participants(df, meta, rel, str(sheet), amap)
                    if not pf.empty:
                        imported_frames.append(pf)
                        logs.append({"source_file":rel,"sheet":sheet,"rows_imported":len(pf),"status":"Imported"})
                    else:
                        logs.append({"source_file":rel,"sheet":sheet,"rows_imported":0,"status":"No participant-name column detected"})
            elif ext == ".pdf":
                text, used = extract_pdf_text(p)
                key = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
                out = OCR_DIR/f"{key}_{slug(p.stem)[:60]}.txt"
                out.write_text(text, encoding="utf-8", errors="ignore")
                rec["ocr_used"], rec["ocr_text_file"] = used, out.relative_to(ROOT).as_posix()
            else:
                text, used = extract_image_text(p)
                key = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
                out = OCR_DIR/f"{key}_{slug(p.stem)[:60]}.txt"
                out.write_text(text, encoding="utf-8", errors="ignore")
                rec["ocr_used"], rec["ocr_text_file"] = used, out.relative_to(ROOT).as_posix()
        except Exception as exc:
            rec["status"], rec["notes"] = "ERROR", str(exc)
            logs.append({"source_file":rel,"sheet":"","rows_imported":0,"status":f"ERROR: {exc}"})
        inventory.append(rec)

    pd.DataFrame(inventory).to_csv(PROCESSED/"document_inventory.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(logs).to_csv(PROCESSED/"import_log.csv", index=False, encoding="utf-8-sig")

    cols = [
        "participant_id","participant_name","gender","email","phone","institution","region",
        "event_id","event_name","event_type","event_subtype","evidence_category","participant_group",
        "cohort","location","event_date","registered","attended","completed","selected","application",
        "project_name","enterprise","source_file","source_sheet","needs_review"
    ]
    existing_path = PROCESSED/"participants_master.csv"
    try:
        existing = pd.read_csv(existing_path).fillna("")
    except Exception:
        existing = pd.DataFrame(columns=cols)
    auto = pd.concat(imported_frames, ignore_index=True) if imported_frames else pd.DataFrame(columns=cols)
    combined = pd.concat([existing, auto], ignore_index=True)
    if not combined.empty:
        for c in cols:
            if c not in combined: combined[c] = ""
        combined["_dedupe"] = combined["source_file"].astype(str)+"|"+combined["source_sheet"].astype(str)+"|"+combined["participant_name"].astype(str).str.lower().str.strip()
        combined = combined.drop_duplicates("_dedupe", keep="last").drop(columns="_dedupe")
    combined.reindex(columns=cols).to_csv(existing_path, index=False, encoding="utf-8-sig")
    print(f"Scanned {len(all_files)} evidence files.")
    print(f"Participant rows available: {len(combined)}")
    print("Outputs written to processed/")

if __name__ == "__main__":
    main()
