# -*- coding: utf-8 -*-
"""End-to-end eval: POST the synthetic sheet to /api/process_ocr (handwriting mode)
and compare against ground truth (subject name after fuzzy match, credits, letter grade)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import normalize
import app as appmod
HERE = os.path.dirname(os.path.abspath(__file__))
img = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'synthetic_handwriting.png')
gt = json.load(open(img.rsplit('.', 1)[0] + '.json'))
c = appmod.app.test_client()
t = time.time()
r = c.post('/api/process_ocr', data={'mode': 'handwriting', 'file_anh': (open(img, 'rb'), os.path.basename(img))}).get_json()
dt = time.time() - t
print('engine:', r.get('engine'), f'time={dt:.1f}s', 'rows:', len(r.get('data', [])))
got = r.get('data', [])
ok_name = ok_tc = ok_grade = 0
for g in gt:
    m = next((x for x in got if normalize(x['ten_mon']) == normalize(g['ten_mon'])), None)
    if m:
        ok_name += 1; ok_tc += m['tin_chi'] == g['tin_chi']; ok_grade += m['diem_he_4'] == g['diem_chu']
    print(f"{'OK ' if m else 'MISS'} {g['ten_mon']:<28} -> " + (f"{m['ten_mon']} | raw='{m['raw_name']}' | {m['percentage']} | TC {m['tin_chi']} | {m['diem_he_4']}" if m else ''))
n = len(gt)
print(f"subject match {ok_name}/{n}, credits {ok_tc}/{n}, letter grade {ok_grade}/{n}")
