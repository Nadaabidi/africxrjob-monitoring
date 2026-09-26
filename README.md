# AFRICXRJOB Monitoring Tool — adapted to the real evidence structure

This version is configured for these exact folders:

- `data/applications/`
- `data/ecosystem_trainings/`
- `data/student_trainings/`
- `data/kickoffs/`
- `data/talentverse_testing_sessions/`
- `data/opendays/`

The attached source archive inventory contained 27 files: 4 applications, 1 ecosystem training, 7 student training files, 3 kickoffs, 10 Open/Closing Day documents, and 2 TalentVerse testing-session files.

## What this version adds

- Controlled `evidence_category` based on the six folders.
- Event type and subtype recognition.
- Cohort inference (`Cohort 1`, `Cohort 2`) from filenames.
- Location inference for Gabès, Monastir, Borj Cedria, Nabeul and Tunis.
- Distinction between ordinary Open Days, Ecosystem Open Days and Training Closing Days.
- Distinction between student, ecosystem and enterprise closing-day evidence.
- Smart Excel header detection in the first 15 rows.
- OCR/text extraction for PDFs.
- Evidence inventory and OCR search.
- Filters for evidence category, event type, subtype, cohort and location.
- Transparent KPI formula catalogue.

## Important limitation

PDF OCR is deliberately not treated as automatically validated participant data. OCR output is searchable evidence. Counts or names coming from scans should be reviewed before they are used as official donor-reporting figures.

## Installation — Windows

Open Command Prompt inside this project folder:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install Tesseract OCR separately and make sure at least `eng` and `fra` language data are available:

```bat
tesseract --version
tesseract --list-langs
```

## Put the real evidence in `data/`

Copy the six folders from your organised AFRICXRJOB data folder into this project's `data/` directory. Keep the folder names exactly as above.

## Run ingestion

```bat
python ingest.py
```

This creates/updates:

- `processed/document_inventory.csv`
- `processed/import_log.csv`
- `processed/participants_master.csv`
- `processed/ocr_text/`

## Review before reporting

Open `processed/participants_master.csv` and review rows marked `needs_review = True`.

For scanned/signature-heavy PDFs, inspect the OCR text and validate counts manually. If a document only supports an event-level total, add the validated total to `processed/events_master.csv` rather than inventing participant rows.

## Start the dashboard

```bat
python -m streamlit run app.py
```

## Filters available

- Evidence category
- Event type
- Activity subtype
- Cohort
- Location

Examples of subtypes detected from your current filenames include:

- Open Day
- Ecosystem Open Day
- Training Closing Day - Ecosystem
- Training Closing Day - Enterprises
- Training Closing Day - Students
- Online Training
- On-site Training
- Testing Session

## KPI logic

The methodology catalogue is in `config/kpi_definitions.csv` and appears in the dashboard. Core formulas include:

- Attendance rate = Attended / Registered × 100
- Female participation = Women / Participants with known gender × 100
- Selection rate = Selected / Applications × 100
- Completion rate = Completed / denominator × 100, with the denominator explicitly documented

AFRICXRJOB-specific indicators included in the catalogue include applications received, students trained, ecosystem actors reached, Open Day attendance, TalentVerse testing participants, institutions represented, regions represented and activities implemented.

## Files worth knowing

- `config/folder_mapping.csv` — the six-folder monitoring taxonomy
- `config/event_types.csv` — keyword/event classification rules
- `config/column_aliases.json` — French/English spreadsheet-header aliases
- `config/kpi_definitions.csv` — KPI names, formulas and evidence sources
- `config/source_archive_inventory.csv` — inventory of the archive supplied for this revision
- `ingest.py` — extraction and standardisation pipeline
- `app.py` — Streamlit dashboard
- `kpis.py` — KPI calculations

## Next validation step

After `python ingest.py` runs on your machine, inspect `processed/import_log.csv`. Any sheet reported as `No participant-name column detected` needs a new header alias or a custom parser. That is the point where the generic extraction becomes fully tailored to the exact spreadsheet column names.
