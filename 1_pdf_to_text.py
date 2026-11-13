#!/usr/bin/env python3
"""Step 1: convert a scanned-book PDF into a clean .txt file.

Run from the repo root, e.g.:

    python 1_pdf_to_text.py pdf_source/TheEnergyConcept.pdf
    python 1_pdf_to_text.py TheEnergyConcept.pdf       # bare name -> pdf_source/

The readable output is written to
    1_output_book_txt/<slug>/<slug>_clean.txt

This is a thin runner around the full pipeline in pdf_to_text/pipeline.py
(all the render/OCR/spellfix stages live there).
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.join(ROOT, "pdf_to_text")
PDF_DIR = os.path.join(ROOT, "pdf_source")
TXT_DIR = os.path.join(ROOT, "1_output_book_txt")

# Make `import pipeline` work and let it find its vendored .pylibs/.
sys.path.insert(0, TOOL_DIR)

from pipeline import main as _pipeline_main  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # A bare PDF filename is looked up under pdf_source/.
    if argv and not os.path.isabs(argv[0]) and not os.path.exists(argv[0]):
        candidate = os.path.join(PDF_DIR, argv[0])
        if os.path.exists(candidate):
            argv[0] = candidate

    # Text output goes to 1_output_book_txt/ unless the user overrides it.
    if "--output-root" not in argv:
        argv += ["--output-root", TXT_DIR]

    return _pipeline_main(argv)


if __name__ == "__main__":
    sys.exit(main())
