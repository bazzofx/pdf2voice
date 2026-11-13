"""Finalize: apply token fixes + page-break dehyphenation + textual fixes -> final output txt."""
import re

SRC = r"C:\_deepSeekApps\pdf2text\output\dehyph_ocr.txt"
OUT = r"C:\_deepSeekApps\pdf2text\output\A_History_of_Magic_Witchcraft_and_Animal_Magnetism.txt"

text = open(SRC, encoding="utf-8").read()

# --- 1. token fixes ---
fix_map = {}
for line in open(r"C:\_deepSeekApps\pdf2text\curation\fix.tsv", encoding="utf-8"):
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
        continue
    parts = line.split("\t")
    if len(parts) >= 2:
        fix_map[parts[0]] = parts[1]

n_fixed = 0
for tok, repl in fix_map.items():
    pat = re.compile(rf"(?<![A-Za-zæÆ]){re.escape(tok)}(?![A-Za-zæÆ])")
    text, cnt = pat.subn(repl, text)
    n_fixed += cnt

# --- 2. page-break dehyphenation: "charac-\n----- Page N -----\nter" -> "character" ---
n_pb = 0
pat_pb = re.compile(r"-\n(?:-{5} Page \d+ -{5}\n)+(?=[a-z])")
text, n_pb = pat_pb.subn("", text)

# --- 3. textual phrase fixes ---
phrase_fixes = [
    ("REVEI AT A", "REVELATA"),
    ("L SQ", "ESQ."),
    ("Copyright 0 2016", "Copyright \u00a9 2016"),
    ("Sible to reason", "possible to reason"),
    ("Sible world", "sensible world"),
    ("Cial notice", "especial notice"),
    ("Cial circumstances", "especial circumstances"),
    ("ther unpalatable", "rather unpalatable"),
    ("bv-and-bye", "by-and-bye"),
]
n_ph = 0
for old, new in phrase_fixes:
    n_ph += text.count(old)
    text = text.replace(old, new)

# --- 4. Greek epigraph on page 3 (unreadable by OCR) ---
text = text.replace(
    "0b yue v5v z\u00c6x\u00e5\u00c95, \u00e6iE1 750T\u00c9\nZi zobb\u20acis dibsv, OTOV\n",
    "[Greek epigraph - not machine-readable in this scan]\n",
)

# --- 5. annotate blank pages ---
lines = text.split("\n")
out_lines = []
i = 0
blank_pages = []
while i < len(lines):
    m = re.match(r"^-{5} Page (\d+) -{5}$", lines[i])
    if m:
        pno = int(m.group(1))
        out_lines.append(lines[i])
        # look ahead: blank if next line is another marker or EOF
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if not nxt.strip() or re.match(r"^-{5} Page ", nxt):
            out_lines.append("[blank page]")
            blank_pages.append(pno)
        i += 1
    else:
        out_lines.append(lines[i])
        i += 1
text = "\n".join(out_lines)

# --- header ---
header = (
    "A HISTORY OF MAGIC, WITCHCRAFT, AND ANIMAL MAGNETISM\n"
    "by John Campbell Colquhoun (London: Longman, Brown, Green, & Longmans, 1851) - Volume I\n"
    "------------------------------------------------------------------------------\n"
    "Machine-readable text converted from the scanned PDF:\n"
    "  source/AnHistoryofMagicWitchcraftandAnimalMagnetism_10811026.pdf (399 pages)\n"
    "Method: 200-DPI grayscale rendering + Windows OCR, followed by an automated\n"
    "  spelling/OCR-error verification pass (239+ auto-corrections reviewed and applied).\n"
    "Note: \"----- Page N -----\" markers follow the PDF page order (Page 1 = cover).\n"
    "      Latin/Greek quotations retain the original period spelling; Greek characters\n"
    "      that the OCR could not read are marked with a bracketed note.\n"
    "------------------------------------------------------------------------------\n\n"
)
text = header + text

open(OUT, "w", encoding="utf-8").write(text)

print(f"token fixes applied: {n_fixed}")
print(f"page-break joins: {n_pb}")
print(f"phrase fixes: {n_ph}")
print(f"blank pages annotated: {blank_pages}")
print("output:", OUT)
