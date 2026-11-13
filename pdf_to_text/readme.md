# pdf2text — scanned-book PDF → readable `.txt`

A full-cycle pipeline that turns **image-only (scanned) book PDFs** into clean,
machine-readable text files, one folder per book under `output/`.

## How it works

The pipeline runs six stages, orchestrated by a single script (`pipeline.py`):

| # | Stage | What it does | Produces |
|---|-------|--------------|----------|
| 0 | **render** | Renders every PDF page to a 200-DPI grayscale PNG using PyMuPDF. | `temp_pages/page_000.png` … |
| 1 | **ocr** | Reads each PNG with the built-in Windows OCR engine (`Windows.Media.Ocr`, via `ocr_pages.ps1`) and writes one `----- Page N -----` marker per page. | `raw_ocr.txt` |
| 2 | **dehyphenate** | Joins words hyphenated across a line break (`compre-` + `hensible` → `comprehensible`). | `dehyph_ocr.txt` |
| 3 | **spellfix** | Applies curated OCR-error fixes from `curation/fix.tsv` (word-boundary token replacements). | `fixed_ocr.txt` |
| 4 | **finalize** | Joins words hyphenated across a *page* break, annotates blank pages, prepends a provenance header. | `<slug>.txt` |
| 5 | **cleanheads** | Removes running heads (the repeated book/chapter title + page number at the top of each page), detected automatically by frequency, then re-joins page-break hyphenations and annotates blank pages. | `final_<slug>_clean.txt` |
| 6 | **verify** | Spell-checks the final text and writes stats + remaining unknown tokens. | `verification_summary.txt` |

The **readable output** is `final_<slug>_clean.txt` — the final text with page
markers retained but running heads removed.

## Requirements

- **Windows** — stage 1 uses the built-in WinRT OCR engine, which needs an
  English (or matching) **OCR language pack** installed under Windows language
  settings. (The pipeline prints the detected engine language, e.g. `en-GB`.)
- **Python 3** with **PyMuPDF** installed (`import fitz`).
- **pyspellchecker**, vendored locally in `.pylibs/` (no global install needed).

## Usage

```bash
python pipeline.py source/MyBook.pdf
```

Optional flags:

| Flag | Purpose |
|------|---------|
| `--slug NAME` | Output folder name (default: derived from the PDF filename). |
| `--title "…"` | Book title for the output header (default: PDF metadata). |
| `--author "…"` | Author for the output header (default: PDF metadata). |
| `--dpi N` | Render DPI (default `200`). |
| `--keep-pages` | Keep the rendered PNGs instead of deleting them after OCR. |
| `--output-root DIR` | Parent directory for per-book folders (default `output/`). |

Example:

```bash
python pipeline.py source/TheEnergyConcept.pdf \
  --title "The Energy Concept: A Spiritual Interpretation of Reality" \
  --author "Lewis Guy Rohrbaugh"
```

## Output layout

Each book gets its own folder under `output/`:

```
output/
└── TheEnergyConcept/
    ├── final_TheEnergyConcept_clean.txt     ← readable output (running heads removed)
    ├── TheEnergyConcept.txt           ← final text with page markers
    ├── verification_summary.txt       ← spell-check stats + remaining unknown tokens
    ├── raw_ocr.txt                    ← raw OCR (one page marker per page)
    ├── dehyph_ocr.txt                 ← after line-wrap dehyphenation
    ├── fixed_ocr.txt                  ← after curated token fixes
    ├── temp_pages/                    ← rendered PNGs (deleted unless --keep-pages)
    └── curation/
        ├── fix.tsv                    ← curated OCR fixes:  wrong<TAB>correct
        └── keep.txt                   ← legitimate tokens to keep (names, Latin, …)
```

## Improving a book (curation)

OCR is not perfect. After a first run, open `verification_summary.txt` to see
the remaining unknown tokens, then curate the book's `curation/` files and
re-run:

- **`fix.tsv`** — one `wrong<TAB>correct` pair per line (lines starting with
  `#` are ignored). These are applied with word boundaries, so `offce → office`
  won't touch `offces`.
- **`keep.txt`** — one token per line for legitimate words the dictionary
  doesn't know (proper nouns, Latin/German/French quotations, archaic forms),
  so they stop being flagged.

## Notes

- The OCR engine is Windows-only, so stage 1 is delegated to
  `ocr_pages.ps1` (Windows PowerShell 5.1). It reads PNG bytes with plain .NET
  and decodes from an in-memory stream, because the WinRT `StorageFile` API is
  sandboxed and fails on arbitrary paths.
- Page markers (`----- Page N -----`) follow the PDF page order — `Page 1` is
  the cover/first scan, not the printed page number.
- Running-head removal is automatic and frequency-based: a short line that
  recurs at the top of many pages is treated as a running head and removed only
  in that header zone, never in the body.

## Legacy scripts

The repository also contains the original single-book scripts (hard-coded to
`An History of Magic, Witchcraft, and Animal Magnetism`), kept for reference:
`verify_ocr.py`, `verify2.py`, `ctx_dump.py`, `grep_ctx.py`, `finalize.py`,
`verify_final.py`, `remove-running-heads.ps1`. `pipeline.py` generalizes and
replaces that flow; prefer it for new books.
