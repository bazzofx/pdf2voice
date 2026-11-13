"""Dump context lines for a list of tokens found in the fixed text."""
import re
import sys

sys.path.insert(0, r"C:\_deepSeekApps\pdf2text\.pylibs")

TEXT = open(r"C:\_deepSeekApps\pdf2text\output\fixed_ocr.txt", encoding="utf-8").read()
REPORT = open(r"C:\_deepSeekApps\pdf2text\output\verify2_report.txt", encoding="utf-8").read()

tokens = []
for line in REPORT.split("\n")[3:]:
    m = re.match(r"\s*\d+\s*\|\s*(.+?)\s*$", line)
    if m:
        tokens.append(m.group(1))

# build page structure
pages = {}
cur = None
for ln in TEXT.split("\n"):
    pm = re.match(r"^-{5} Page (\d+) -{5}$", ln)
    if pm:
        cur = int(pm.group(1))
        pages[cur] = []
    elif cur:
        pages[cur].append(ln)

def context_for(tok):
    pat = re.compile(rf"(?<![A-Za-zæÆœŒ]){re.escape(tok)}(?![A-Za-zæÆœŒ])")
    out = []
    for pno in sorted(pages):
        for ln in pages[pno]:
            if pat.search(ln):
                out.append((pno, ln.strip()))
                if len(out) >= 3:
                    return out
    return out

with open(r"C:\_deepSeekApps\pdf2text\output\contexts.txt", "w", encoding="utf-8") as f:
    for tok in tokens:
        f.write(f"### {tok}\n")
        for pno, ln in context_for(tok):
            f.write(f"  [p{pno}] {ln}\n")
        f.write("\n")
print("contexts written")
