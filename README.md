# pdf2voice

Turn scanned-book **PDFs** into spoken **audio** (audiobooks) in two steps.

1. **PDF → text** — `1_pdf_to_text.py` (Windows OCR → dehyphenation → spell-fix → running-head removal).
2. **Text → audio** — `2_text_to_speech.py` (OmniVoice text-to-speech, voice design + `--split` chunking).

## Quick start

```powershell
# 1) Put a PDF in pdf_source/, then:
.venv\Scripts\python.exe 1_pdf_to_text.py pdf_source/MyBook.pdf

# 2) Convert the extracted text to audio (split into ~5000-char parts):
.venv\Scripts\python.exe 2_text_to_speech.py "1_output_book_txt/<book>/final_<book>_clean.txt" --split 5000
```

Full walkthrough and all flags: see **[GUIDE.md](GUIDE.md)**.

## Layout

| Path | Purpose |
|------|---------|
| `pdf_source/` | input PDFs |
| `1_output_book_txt/` | extracted text (per book) — generated, not committed |
| `2_output_book_audio/` | generated audio (per book) — generated, not committed |
| `pdf_to_text/` | the PDF → text engine |
| `omnivoice/` | the OmniVoice TTS library |

## Setup

Uses a `.venv` with OmniVoice, PyTorch, and PyMuPDF:

```powershell
uv sync
uv pip install pymupdf
```

## Credits

Text-to-speech is powered by [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice) (Apache-2.0).
