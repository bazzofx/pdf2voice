#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full-cycle scanned-book PDF -> readable .txt pipeline, one folder per book.

Run:
    python pipeline.py source/TheEnergyConcept.pdf

Stages (all in one call):
  0. render      PyMuPDF renders every PDF page to a 200-DPI grayscale PNG.
  1. ocr         Windows.Media.Ocr (via ocr_pages.ps1) reads the PNGs into
                 raw_ocr.txt, one "----- Page N -----" marker per page.
  2. dehyphenate join words hyphenated across a line break -> dehyph_ocr.txt.
  3. spellfix    apply curated token fixes (curation/fix.tsv) -> fixed_ocr.txt.
  4. finalize    join words hyphenated across a page break, annotate blank
                 pages, prepend a provenance header -> <slug>.txt.
  5. cleanheads  remove running heads / page numbers, then re-join page-break
                 hyphenations and annotate blank pages -> final_<slug>_clean.txt.
  6. verify      spell-check the clean text -> verification_summary.txt.

Per-book output layout (under output/<slug>/):
    temp_pages/            rendered PNGs (deleted on success unless --keep-pages)
    raw_ocr.txt            raw OCR with page markers
    dehyph_ocr.txt         after line-wrap dehyphenation
    fixed_ocr.txt          after curated token fixes
    <slug>.txt             final text (page markers retained)
    final_<slug>_clean.txt       final text with running heads removed  <-- the readable file
    verification_summary.txt  spell-check stats + remaining unknown tokens
    curation/fix.tsv       curated OCR-error fixes (token -> replacement)
    curation/keep.txt      legitimate tokens to keep (proper nouns, Latin, ...)
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PYLIBS = os.path.join(HERE, ".pylibs")
sys.path.insert(0, PYLIBS)

PAGE_MARKER_RE = re.compile(r"^-{5} Page \d+ -{5}$")
HEADING_RE = re.compile(r"^(chapter|part|appendix|contents|preface|introduction|index|section|book)\b", re.IGNORECASE)
PAGENUM_RE = re.compile(r"^\d+$")
ROMAN_RE = re.compile(r"^[ivxlcdmIVXLCDM]+$")
MAX_HEAD_LEN = 40          # a running-head line longer than this is treated as content
MAX_HEAD_LINES = 3         # remove at most this many header lines per page


# --------------------------------------------------------------------------
# stage 0: render
# --------------------------------------------------------------------------
def render(pdf_path, pages_dir, dpi):
    import fitz  # PyMuPDF
    os.makedirs(pages_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for i in range(doc.page_count):
        pix = doc[i].get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
        pix.save(os.path.join(pages_dir, "page_{:03d}.png".format(i)))
    n = doc.page_count
    doc.close()
    return n


# --------------------------------------------------------------------------
# stage 1: ocr (delegated to Windows PowerShell / WinRT OCR)
# --------------------------------------------------------------------------
def run_ocr(pages_dir, out_raw, count):
    ps1 = os.path.join(HERE, "ocr_pages.ps1")
    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", ps1,
        "-PagesDir", pages_dir,
        "-OutFile", out_raw,
        "-Count", str(count),
    ]
    # NOTE: do NOT capture stdout/stderr here -- the Windows sandbox forbids
    # creating the named pipes subprocess uses for capture (CreatePipe -> EPERM).
    # Inherit stdio instead; the OCR result is written to `out_raw` by the script.
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("OCR failed (exit %d)" % r.returncode)


# --------------------------------------------------------------------------
# stage 2: line-wrap dehyphenation
# --------------------------------------------------------------------------
def dehyphenate(text):
    # "compre-\nhensible" -> "comprehensible". The [a-z] before the hyphen
    # ensures the "----- Page N -----" marker's own dashes are never treated
    # as a hyphenated word break.
    return re.sub(r"([a-z])-\n(?=[a-z])", r"\1", text)


# --------------------------------------------------------------------------
# stage 3: curated token fixes
# --------------------------------------------------------------------------
def load_fix_map(path):
    fix_map = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2 and parts[0] and parts[1]:
                    fix_map[parts[0]] = parts[1]
    return fix_map


def apply_fixes(text, fix_map):
    n = 0
    for tok, repl in fix_map.items():
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(tok) + r"(?![A-Za-z])")
        text, cnt = pat.subn(repl, text)
        n += cnt
    return text, n


# --------------------------------------------------------------------------
# stage 4: finalize (page-break dehyphenation + blank pages + header)
# --------------------------------------------------------------------------
def join_page_breaks(text):
    # "charac-\n----- Page N -----\nter" -> "character". Require a letter
    # before the hyphen so page markers are left intact.
    return re.sub(r"([a-z])-\n(?:-{5} Page \d+ -{5}\n)+(?=[a-z])", r"\1", text)


def annotate_blank_pages(text):
    lines = text.split("\n")
    out = []
    blank = []
    i = 0
    while i < len(lines):
        m = re.match(r"^-{5} Page (\d+) -{5}$", lines[i])
        if m:
            out.append(lines[i])
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not nxt.strip() or re.match(r"^-{5} Page ", nxt):
                out.append("[blank page]")
                blank.append(int(m.group(1)))
            i += 1
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out), blank


def remove_standalone_numbers(text):
    """Delete lines that contain only digits (leftover page numbers)."""
    lines = text.split("\n")
    kept = [ln for ln in lines if not PAGENUM_RE.match(ln.strip())]
    return "\n".join(kept), len(lines) - len(kept)


def build_header(title, author, src_pdf, page_count):
    bar = "-" * 78
    parts = []
    if title:
        parts.append(title)
    if author:
        parts.append("by " + author)
    if parts:
        parts.append(bar)
    parts += [
        "Machine-readable text converted from the scanned PDF:",
        "  " + src_pdf + " (" + str(page_count) + " pages)",
        "Method: 200-DPI grayscale rendering (PyMuPDF) + Windows OCR, followed by",
        "  automated dehyphenation, spelling fixes, and running-head removal.",
        "Note: \"----- Page N -----\" markers follow the PDF page order (Page 1 = cover).",
        bar,
    ]
    return "\n".join(parts) + "\n\n"


# --------------------------------------------------------------------------
# stage 5: running-head removal
# --------------------------------------------------------------------------
def split_pages(text):
    """Return list of (pageno, [content lines]) excluding the marker line."""
    pages = []
    cur = None
    for ln in text.split("\n"):
        m = re.match(r"^-{5} Page (\d+) -{5}$", ln)
        if m:
            cur = int(m.group(1))
            pages.append((cur, []))
        elif cur is not None:
            pages[-1][1].append(ln)
    return pages


def detect_running_heads(pages, min_count=4, min_frac=0.1):
    cand = Counter()
    total = len(pages)
    for _, lines in pages:
        seen = 0
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            if s == "[blank page]":
                break
            if len(s) > MAX_HEAD_LEN:
                break
            if HEADING_RE.match(s):
                break
            if PAGENUM_RE.match(s) or ROMAN_RE.match(s):
                seen += 1
                continue
            cand[s.lower()] += 1
            seen += 1
            if seen >= MAX_HEAD_LINES:
                break
    heads = set()
    for low, c in cand.items():
        if c >= min_count and c >= total * min_frac:
            heads.add(low)
    return heads


def remove_running_heads(text, heads):
    lines = text.split("\n")
    out = []
    scan = False
    removed_this_page = 0
    removed_total = 0
    for line in lines:
        # marker glued to content -> split it onto its own line
        m = re.search(r"----- Page \d+ -----", line)
        if m and line.strip() != m.group(0):
            before = line[:m.start()].rstrip()
            after = line[m.end():]
            if before:
                out.append(before)
            out.append(m.group(0))
            if after:
                out.append(after)
            scan = True
            removed_this_page = 0
            continue

        if PAGE_MARKER_RE.match(line.strip()):
            out.append(line)
            scan = True
            removed_this_page = 0
            continue

        if scan:
            s = line.strip()
            if s == "":
                continue
            if s == "[blank page]":
                out.append(line)
                scan = False
                continue
            if len(s) > MAX_HEAD_LEN:
                out.append(line)
                scan = False
                continue

            is_heading = bool(HEADING_RE.match(s))
            is_pagenum = bool(PAGENUM_RE.match(s) or ROMAN_RE.match(s))
            is_head = s.lower() in heads

            if (not is_heading) and (is_pagenum or is_head) and removed_this_page < MAX_HEAD_LINES:
                removed_this_page += 1
                removed_total += 1
                continue

            out.append(line)
            if removed_this_page == 0:
                scan = False
            continue

        out.append(line)
    return "\n".join(out) + "\n", removed_total


# --------------------------------------------------------------------------
# stage 6: verification
# --------------------------------------------------------------------------
def known_words():
    from spellchecker import SpellChecker
    sp = SpellChecker()
    known = set(w.lower() for w in sp.word_frequency.words())
    words_txt = os.path.join(PYLIBS, "english_words.txt")
    if os.path.exists(words_txt):
        known.update(open(words_txt, encoding="utf-8").read().split())
    return known


ABBREV = {"dr", "mr", "mrs", "ms", "st", "vol", "no", "nos", "vols", "etc",
          "pp", "viz", "ibid", "lb", "lib", "de", "le", "la", "du", "des",
          "der", "die", "das", "von", "van", "un", "una", "del", "di", "da",
          "el", "los", "las", "il", "gli", "ii", "iii", "iv", "vi", "vii",
          "viii", "ix", "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii",
          "xviii", "xix", "xx", "xxi", "xxii", "xxiii", "xxiv", "xxv",
          "xxvi", "xxvii", "xxviii", "xxix", "xxx"}


def verify(text, keep_set, known):
    body = "\n".join(ln for ln in text.split("\n") if not PAGE_MARKER_RE.match(ln))
    tokens = re.findall(r"[A-Za-z\u00e6\u00c6\u0153\u0152']+", body)
    tokens = [t for t in tokens if t.replace("'", "").isalpha()]
    freq = Counter(tokens)
    unknown = []
    for w, c in freq.items():
        low = w.lower()
        if ROMAN_RE.match(w) or (len(w) == 1 and w.isupper()) or low in ABBREV:
            continue
        if w in keep_set or low in known:
            continue
        if w.isupper() and len(w) > 1:
            continue
        unknown.append((w, c))
    unknown.sort(key=lambda kv: (-kv[1], kv[0]))
    return sum(freq.values()), unknown


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="PDF -> readable .txt (full cycle)")
    ap.add_argument("pdf", help="path to the source PDF")
    ap.add_argument("--slug", help="output folder name (default: derived from filename)")
    ap.add_argument("--title", default="", help="book title for the output header")
    ap.add_argument("--author", default="", help="author for the output header")
    ap.add_argument("--dpi", type=int, default=200, help="render DPI (default 200)")
    ap.add_argument("--keep-pages", action="store_true", help="keep rendered PNGs")
    ap.add_argument("--output-root", default=os.path.join(os.path.dirname(HERE), "1_output_book_txt"),
                    help="parent directory for per-book folders")
    args = ap.parse_args(argv)

    pdf = os.path.abspath(args.pdf)
    if not os.path.exists(pdf):
        ap.error("PDF not found: %s" % pdf)
    slug = args.slug or re.sub(r"[^A-Za-z0-9]+", "_", os.path.splitext(os.path.basename(pdf))[0]).strip("_") or "book"
    book_dir = os.path.join(args.output_root, slug)
    os.makedirs(book_dir, exist_ok=True)

    pages_dir = os.path.join(book_dir, "temp_pages")
    raw = os.path.join(book_dir, "raw_ocr.txt")
    dehyph = os.path.join(book_dir, "dehyph_ocr.txt")
    fixed = os.path.join(book_dir, "fixed_ocr.txt")
    final = os.path.join(book_dir, slug + ".txt")
    clean = os.path.join(book_dir, "final_" + slug + "_clean.txt")
    summary = os.path.join(book_dir, "verification_summary.txt")
    curation = os.path.join(book_dir, "curation")
    os.makedirs(curation, exist_ok=True)
    fix_tsv = os.path.join(curation, "fix.tsv")
    keep_txt = os.path.join(curation, "keep.txt")

    # -- title/author fallbacks from PDF metadata --
    title = args.title
    author = args.author
    if not title or not author:
        try:
            import fitz
            doc = fitz.open(pdf)
            meta = doc.metadata or {}
            doc.close()
            title = title or (meta.get("title") or "").strip()
            author = author or (meta.get("author") or "").replace("From Old Catalog", "").strip(", .")
        except Exception:
            pass

    print("=" * 78)
    print("Book     : %s" % slug)
    print("Source   : %s" % pdf)
    print("Output   : %s" % book_dir)
    print("=" * 78)

    # stage 0
    print("\n[0/6] rendering pages at %d DPI ..." % args.dpi)
    n_pages = render(pdf, pages_dir, args.dpi)
    print("  rendered %d pages -> %s" % (n_pages, pages_dir))

    # stage 1
    print("\n[1/6] OCR (%d pages) ..." % n_pages)
    run_ocr(pages_dir, raw, n_pages)
    print("  wrote %s" % raw)

    # stage 2
    print("\n[2/6] dehyphenating line wraps ...")
    text = open(raw, encoding="utf-8-sig").read()
    text = dehyphenate(text)
    open(dehyph, "w", encoding="utf-8").write(text)
    print("  wrote %s" % dehyph)

    # stage 3
    print("\n[3/6] applying curated token fixes ...")
    fix_map = load_fix_map(fix_tsv)
    text, n_fixed = apply_fixes(text, fix_map)
    open(fixed, "w", encoding="utf-8").write(text)
    print("  %d fix rule(s), %d replacement(s) -> %s" % (len(fix_map), n_fixed, fixed))

    # stage 4
    print("\n[4/6] finalizing (<slug>.txt with running heads) ...")
    final_text = join_page_breaks(text)
    final_text, blank = annotate_blank_pages(final_text)
    header = build_header(title, author, os.path.relpath(pdf, HERE).replace(os.sep, "/"), n_pages)
    open(final, "w", encoding="utf-8").write(header + final_text)
    print("  blank pages annotated: %s" % (blank if blank else "none"))
    print("  wrote %s" % final)

    # stage 5
    # Remove running heads BEFORE joining across page breaks: a word hyphenated
    # at the very end of a page ("care-\n----- Page 9 -----\nRELIGIOUS PHILOSOPHY
    # \n21\nful") only becomes joinable once the interposed running head is gone.
    print("\n[5/6] removing running heads, then joining page breaks ...")
    pages = split_pages(text)
    heads = detect_running_heads(pages)
    clean_text, n_removed = remove_running_heads(text, heads)
    clean_text = join_page_breaks(clean_text)
    clean_text, _ = annotate_blank_pages(clean_text)
    clean_text, n_digits = remove_standalone_numbers(clean_text)
    open(clean, "w", encoding="utf-8").write(header + clean_text)
    print("  detected running heads: %s" % (sorted(heads) if heads else "none"))
    print("  header lines removed: %d" % n_removed)
    print("  page-number lines removed: %d" % n_digits)
    print("  wrote %s" % clean)

    # stage 6
    print("\n[6/6] verifying ...")
    known = known_words()
    keep_set = set()
    if os.path.exists(keep_txt):
        keep_set = set(x.strip() for x in open(keep_txt, encoding="utf-8") if x.strip())
    total_tokens, unknown = verify(clean_text, keep_set, known)
    with open(summary, "w", encoding="utf-8") as f:
        f.write("source: %s (%d pages)\n" % (os.path.basename(pdf), n_pages))
        f.write("token fixes applied: %d\n" % n_fixed)
        f.write("running-head lines removed: %d\n" % n_removed)
        f.write("blank pages: %s\n" % (", ".join(map(str, blank)) if blank else "none"))
        f.write("\ntotal tokens: %d\n" % total_tokens)
        f.write("remaining unknown tokens: %d (%d occurrences)\n" %
                (len(unknown), sum(c for _, c in unknown)))
        f.write("\n=== REMAINING UNKNOWN (count | word) ===\n")
        for w, c in unknown:
            f.write("%5d | %s\n" % (c, w))
    print("  total tokens: %d, remaining unknown: %d" % (total_tokens, len(unknown)))
    print("  wrote %s" % summary)

    # cleanup
    if not args.keep_pages and os.path.isdir(pages_dir):
        shutil.rmtree(pages_dir, ignore_errors=True)
        print("\n  removed %s" % pages_dir)

    print("\nDone. Readable output: %s" % clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
