# PDF → Audiobook Pipeline

Two numbered scripts, run in sequence, to turn a scanned-book **PDF** into an
**audio file**:

```
Step 1  PDF ──▶ text      1_pdf_to_text.py
Step 2  text ─▶ audio     2_text_to_speech.py
```

Everything is run from the repo root: `C:\_web_apps_2025\OmniVoice`.

---

## Folder layout

```
OmniVoice/
├── pdf_source/                    ← PUT YOUR SOURCE PDFs HERE
├── 1_pdf_to_text.py               ← Step 1 entry point
├── 2_text_to_speech.py            ← Step 2 entry point
├── 1_output_book_txt/<book>/      ← extracted text, one folder per book
│        └── <book>_clean.txt      ← the readable text (use THIS for audio)
├── 2_output_book_audio/<book>/    ← final .wav, one folder per book
├── pdf_to_text/                   ← Step 1 engine (pipeline.py + OCR helpers)
├── omnivoice/                     ← the TTS engine (library, don't touch)
└── .venv/                         ← shared Python env (both steps)
```

**One folder per book** is shared across stages, using the book *slug*
(the PDF filename with spaces/punctuation turned into `_`).

---

## Step 1 — PDF → text

Renders, OCRs with the Windows engine, dehyphenates, spell-fixes, and strips
running heads:

```powershell
.venv\Scripts\python.exe 1_pdf_to_text.py pdf_source/MyBook.pdf
```

A bare filename also works (it's looked up under `pdf_source/`):

```powershell
.venv\Scripts\python.exe 1_pdf_to_text.py MyBook.pdf
```

Optional flags:

| Flag | Purpose |
|------|---------|
| `--title "…"` / `--author "…"` | Book title / author for the text header (default: PDF metadata). |
| `--slug NAME` | Override the output folder name (default: derived from the filename). |
| `--dpi N` | Render DPI (default `200`). |

**Result:** `1_output_book_txt/<slug>/<slug>_clean.txt` (running heads removed).
Use the `_clean.txt` file — not the raw/fixed ones — for the next step.

> Note: Step 1 needs the Windows OCR language pack. See
> [pdf_to_text/readme.md](pdf_to_text/readme.md) for the full detail.

## Step 2 — text → audio

```powershell
# Whole book:
.venv\Scripts\python.exe 2_text_to_speech.py "1_output_book_txt/<slug>/<slug>_clean.txt" -all-chars

# Quick sample (first 1000 characters) — good for a performance check:
.venv\Scripts\python.exe 2_text_to_speech.py "1_output_book_txt/<slug>/<slug>_clean.txt" -max-chars 1000
```

**Result:** `2_output_book_audio/<slug>/<slug>.wav` (the output folder is the
default — pass an explicit directory or `.wav` path as a second argument to
override it).

Default voice is **female · young adult · moderate pitch · British accent**,
language auto-detected. Change it with `--instruct "..."` (e.g.
`--instruct "male, american accent"`) or `--auto-voice` for a random voice. See
`.venv\Scripts\python.exe 2_text_to_speech.py --help` for `--num-step`,
`--speed`, `--ref-audio` (voice cloning), etc.

> Both steps use the same `.venv` Python (`PyMuPDF`, OmniVoice and torch are
> all installed there).

---

## Full worked example

```powershell
cd C:\_web_apps_2025\OmniVoice

# 1) PDF → text (TheEnergyConcept is already converted, but for a new book):
.venv\Scripts\python.exe 1_pdf_to_text.py pdf_source/TheEnergyConcept.pdf `
    --title "The Energy Concept: A Spiritual Interpretation of Reality" `
    --author "Lewis Guy Rohrbaugh"

# 2) text → audio (sample first, then the whole book):
.venv\Scripts\python.exe 2_text_to_speech.py "1_output_book_txt/TheEnergyConcept/TheEnergyConcept_clean.txt" -max-chars 1000
.venv\Scripts\python.exe 2_text_to_speech.py "1_output_book_txt/TheEnergyConcept/TheEnergyConcept_clean.txt" -all-chars
```

---

## Notes

- **Time estimate:** on an NVIDIA GTX 1070 the model runs at roughly
  **1–2× real-time** (RTF ≈ 1–2). A ~150 KB book is about **2.5 hours of
  audio → 2.5–5 hours of compute**. Use `-max-chars 1000` first to sample
  before committing to a full conversion.
- **Speed/quality trade-off:** add `--num-step 16` to roughly halve generation
  time at slightly lower quality.
- **OCR quality:** after Step 1, open `1_output_book_txt/<slug>/verification_summary.txt`
  to see remaining unknown words, then curate `curation/fix.tsv` / `keep.txt`
  and re-run Step 1 if needed (details in `pdf_to_text/readme.md`).
