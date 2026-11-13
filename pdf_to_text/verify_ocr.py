"""Post-process raw OCR output: dehyphenate, spell-check, and report issues.

Usage:
  python verify_ocr.py <raw.txt> <report.txt>
"""
import re
import sys
from collections import Counter

sys.path.insert(0, r"C:\_deepSeekApps\pdf2text\.pylibs")
from spellchecker import SpellChecker

RAW = sys.argv[1] if len(sys.argv) > 1 else r"C:\_deepSeekApps\pdf2text\output\raw_ocr.txt"
REPORT = sys.argv[2] if len(sys.argv) > 2 else r"C:\_deepSeekApps\pdf2text\output\verify_report.txt"

text = open(RAW, encoding="utf-8").read()

# --- dehyphenate: "compre-\nhensible" -> "comprehensible" ---
dehyph = re.sub(r"-\n(?=[a-z])", "", text)

open(RAW.replace("raw_ocr", "dehyph_ocr"), "w", encoding="utf-8").write(dehyph)

# --- tokenize (keep apostrophes; drop other punctuation) ---
tokens = re.findall(r"[A-Za-z']+", dehyph)
tokens = [t for t in tokens if t.replace("'", "").isalpha()]
freq = Counter(tokens)
print(f"total tokens: {sum(freq.values())}, unique: {len(freq)}")

sp = SpellChecker()
known = set()
unknown = {}

# whitelist by pattern (numeric-ish / roman / initials)
pattern_ok = re.compile(
    r"^(?:[IVXLCDM]+|[0-9]+|[A-Z]\.?|St\.?|Vol\.?|No\.?)$"
)

for w, c in freq.items():
    if pattern_ok.match(w):
        continue
    if sp.known([w]):
        known.add(w)
    else:
        unknown[w] = c

print(f"known: {len(known)}, unknown tokens: {len(unknown)}, total unknown occurrences: {sum(unknown.values())}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write(f"total tokens: {sum(freq.values())}, unique: {len(freq)}\n")
    f.write(f"known: {len(known)}, unknown tokens: {len(unknown)}, unknown occurrences: {sum(unknown.values())}\n\n")
    f.write("=== UNKNOWN TOKENS (count | word | correction) ===\n")
    for w, c in sorted(unknown.items(), key=lambda kv: (-kv[1], kv[0])):
        corr = sp.correction(w) or ""
        f.write(f"{c:5d} | {w} | {corr}\n")

print("report written:", REPORT)
