import re
import sys
from collections import Counter

sys.path.insert(0, r"C:\_deepSeekApps\pdf2text\.pylibs")
from spellchecker import SpellChecker

sp = SpellChecker()
known = set(w.lower() for w in sp.word_frequency.words())
known.update(open(r"C:\_deepSeekApps\pdf2text\.pylibs\english_words.txt", encoding="utf-8").read().split())

keep = set(x.strip() for x in open(r"C:\_deepSeekApps\pdf2text\curation\keep.txt", encoding="utf-8") if x.strip())

t = open(r"C:\_deepSeekApps\pdf2text\output\A_History_of_Magic_Witchcraft_and_Animal_Magnetism.txt", encoding="utf-8").read()
body = "\n".join(ln for ln in t.split("\n") if not re.match(r"^-{5} Page \d+ -{5}$", ln))
toks = re.findall(r"[A-Za-z\u00e6\u00c6\u0153\u0152']+", body)
toks = [x for x in toks if x.replace("'", "").isalpha()]
freq = Counter(toks)
roman = re.compile(r"^(?:[IVXLCDM]+|[ivxlcdm]+)$")
abbrev = {"dr","mr","mrs","ms","st","vol","no","nos","vols","etc","pp","viz","ibid","de","le","la","du","des","der","die","das","von","van","un","una","del","di","da","el","los","las","il","gli","ii","iii","iv","vi","vii","viii","ix","xi","xii","xiii","xiv","xv","xvi","xvii","xviii","xix","xx","xxi","xxii","xxiii","xxiv","xxv","xxvi","xxvii","xxviii","xxix","xxx"}

unknown = []
for w, c in freq.items():
    low = w.lower()
    if roman.match(w) or (len(w) == 1 and w.isupper()) or low in abbrev:
        continue
    if w in keep or low in known:
        continue
    if w.isupper() and len(w) > 1:
        continue
    unknown.append((w, c))

unknown.sort(key=lambda kv: (-kv[1], kv[0]))
print("total tokens:", sum(freq.values()))
print("remaining unknown:", len(unknown), "occurrences:", sum(c for _, c in unknown))
for w, c in unknown[:60]:
    print("%4d | %s" % (c, w))
