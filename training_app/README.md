# Digital Workplace Training Academy — Volume 1 web app

An interactive online version of *The Modern Digital Workplace Training
Academy — Volume 1: Digital Foundations*, generated from the source Word
workbook. All nine modules (1.1–1.9) plus the Volume 1 completion review are
included, with working confidence sliders, guided-practice and independent
challenge write-ups, an auto-graded/self-marked knowledge check per module,
and progress tracking.

## How it's built

- `content_source/source.docx` — the original workbook.
- `scripts/build_content.py` — parses the docx into `backend/data/content.json`
  (headings, paragraphs, tables, tick-box lists, fill-in boxes, quiz
  questions and answer keys). Re-run this if the source document changes:

  ```bash
  pip install -r scripts/requirements.txt
  python3 scripts/build_content.py content_source/source.docx backend/data/content.json
  ```

- `backend/` — a small FastAPI app that serves the generated content plus an
  optional progress-sync API (SQLite).
- `frontend/` — a dependency-free HTML/CSS/JS single-page app that renders
  the content interactively.

## Running the app

```bash
cd training_app/backend
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8010
```

Then open `http://localhost:8010/`.

## How progress works

Every interaction (confidence ratings, checklists, written answers, quiz
choices) is saved to the browser's `localStorage` immediately, so the app
works with zero setup — no account needed. A learner can optionally click
**Sync progress** to create a short learner code; entering that code on
another device restores their saved progress from the backend's SQLite
database (`backend/data/progress.db`, created on first run, not committed).

## Knowledge checks

Module 1.1 uses the workbook's original multiple-choice/tick-box questions;
these are auto-graded against the answer key extracted from the document.
Modules 1.2–1.9 use the workbook's original short open-response questions;
these follow the workbook's own "open-book, self-marked" design — the
learner writes an answer, reveals the model answer, and marks themselves
correct/needs-revision.
