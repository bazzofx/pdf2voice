import re
text = open(r'C:\_deepSeekApps\pdf2text\output\dehyph_ocr.txt', encoding='utf-8').read()
lines = text.split('\n')
pats = ['Sible', 'ofa', 'Cial', 'conclu', 'nesse', 'occa', 'racter', 'auc-', 'ther', 'tions', 'mena', 'schol']
for pat in pats:
    print('=' * 20, pat)
    for i, ln in enumerate(lines):
        if re.search(r'(?<![A-Za-z])' + re.escape(pat) + r'(?![A-Za-z])', ln):
            print('  [%d] %s' % (i, ln[:170]))
            if i > 0:
                print('      prev: %s' % lines[i - 1][:170])
