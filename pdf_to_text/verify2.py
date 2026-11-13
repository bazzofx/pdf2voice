"""Verification v2: merged dictionary + proper-noun auto-keep + curated KEEP/FIX.

Usage:
  python verify2.py <input.txt> <report.txt> [fix.tsv] [keep.txt]
"""
import re
import sys
from collections import Counter

sys.path.insert(0, r"C:\_deepSeekApps\pdf2text\.pylibs")
from spellchecker import SpellChecker

INPUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\_deepSeekApps\pdf2text\output\dehyph_ocr.txt"
REPORT = sys.argv[2] if len(sys.argv) > 2 else r"C:\_deepSeekApps\pdf2text\output\verify2_report.txt"
FIX_TSV = sys.argv[3] if len(sys.argv) > 3 else r"C:\_deepSeekApps\pdf2text\curation\fix.tsv"
KEEP_TXT = sys.argv[4] if len(sys.argv) > 4 else r"C:\_deepSeekApps\pdf2text\curation\keep.txt"

# --- merged dictionary (lowercase) ---
sp = SpellChecker()
known = set(w.lower() for w in sp.word_frequency.words())
known.update(open(r"C:\_deepSeekApps\pdf2text\.pylibs\english_words.txt", encoding="utf-8").read().split())

# --- curated keep / fix ---
keep_set = set()
if KEEP_TXT:
    for f in [KEEP_TXT] + [KEEP_TXT.replace("keep.txt", f"keep_{c}.txt") for c in "abcd"]:
        try:
            keep_set.update(x.strip() for x in open(f, encoding="utf-8") if x.strip())
        except FileNotFoundError:
            pass

fix_map = {}
if FIX_TSV:
    for line in open(FIX_TSV, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            fix_map[parts[0]] = parts[1]

text = open(INPUT, encoding="utf-8").read()

# --- apply fixes ---
fixed = text
n_fixed = 0
for tok, repl in fix_map.items():
    pat = re.compile(rf"(?<![A-Za-z]){re.escape(tok)}(?![A-Za-z])")
    fixed, cnt = pat.subn(repl, fixed)
    n_fixed += cnt
open(INPUT.replace("dehyph_ocr", "fixed_ocr"), "w", encoding="utf-8").write(fixed)

# --- tokenize (skip page-marker lines) ---
body = "\n".join(
    ln for ln in fixed.split("\n") if not re.match(r"^-{5} Page \d+ -{5}$", ln)
)
tokens = re.findall(r"[A-Za-zæÆœŒ']+", body)
tokens = [t for t in tokens if t.replace("'", "").isalpha()]
freq = Counter(tokens)

roman = re.compile(r"^(?:[IVXLCDM]+|[ivxlcdm]+)$")
single = re.compile(r"^[A-Z]$")
abbrev = {"dr", "mr", "mrs", "ms", "st", "vol", "no", "nos", "vols", "etc",
          "pp", "viz", "ibid", "lb", "lib", "de", "le", "la", "du", "des",
          "der", "die", "das", "von", "van", "un", "una", "del", "di", "da",
          "el", "los", "las", "il", "gli", "le", "ii", "iii", "iv", "vi",
          "vii", "viii", "ix", "xi", "xii", "xiii", "xiv", "xv", "xvi",
          "xvii", "xviii", "xix", "xx", "xxi", "xxii", "xxiii", "xxiv",
          "xxv", "xxvi", "xxvii", "xxviii", "xxix", "xxx"}

unknown = {}
for w, c in freq.items():
    low = w.lower()
    if roman.match(w) or single.match(w):
        continue
    if low in abbrev:
        continue
    if w in keep_set or low in known:
        continue
    if w.isupper() and len(w) > 1:
        continue  # proper nouns auto-kept (only non-uppercase shapes flagged)
    unknown[w] = c

print(f"tokens: {sum(freq.values())} unique: {len(freq)}")
print(f"remaining unknown: {len(unknown)} ({sum(unknown.values())} occurrences)")
print(f"fixes applied: {n_fixed}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write(f"remaining unknown: {len(unknown)} ({sum(unknown.values())} occurrences), fixes applied: {n_fixed}\n\n")
    f.write("=== REMAINING UNKNOWN (count | word) ===\n")
    for w, c in sorted(unknown.items(), key=lambda kv: (-kv[1], kv[0])):
        f.write(f"{c:5d} | {w}\n")
print("report:", REPORT)
