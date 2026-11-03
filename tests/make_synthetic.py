# -*- coding: utf-8 -*-
"""Generate a synthetic handwritten-style grade sheet (Patrick Hand font, jitter, noise)."""
import random, json, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
random.seed(7)
HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [  # (subject, credits, grade10, letter) — subjects from several UED faculties
    ("Triết học Mác - Lênin", 3, "7.5", "B"),
    ("Tư tưởng Hồ Chí Minh", 2, "8.2", "B+"),
    ("Giải tích 1", 3, "6.8", "C+"),
    ("Cơ sở văn hóa Việt Nam", 2, "9.1", "A+"),
    ("Tâm lý học đại cương", 3, "8.6", "A"),
    ("Hóa học đại cương", 2, "5.9", "C"),
    ("Lập trình Java", 3, "7.2", "B"),
    ("Văn học thiếu nhi", 4, "8.0", "B+"),
    ("Sinh học phân tử", 4, "6.1", "C"),
    ("Tiếng Anh B1.1", 3, "7.9", "B"),
]
def make(path, font_size=40):
    W, H = 1400, 140 + 72 * len(ROWS)
    img = Image.new('RGB', (W, H), (250, 248, 240))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(os.path.join(HERE, 'PatrickHand.ttf'), font_size)
    for i in range(0, H, 36):
        d.line([(0, i), (W, i)], fill=(205, 220, 240), width=1)
    d.text((60, 30), "Bảng điểm học kỳ", font=f, fill=(20, 30, 120))
    for i, (s, tc, g, l) in enumerate(ROWS):
        y = 110 + 72 * i + random.randint(-6, 6)
        ink = (random.randint(10, 40), random.randint(20, 50), random.randint(90, 140))
        d.text((60 + random.randint(-8, 8), y), s, font=f, fill=ink)
        d.text((720 + random.randint(-8, 8), y + random.randint(-5, 5)), str(tc), font=f, fill=ink)
        d.text((880 + random.randint(-8, 8), y + random.randint(-5, 5)), g, font=f, fill=ink)
        d.text((1060 + random.randint(-8, 8), y + random.randint(-5, 5)), l, font=f, fill=ink)
    img = img.rotate(1.2, expand=False, fillcolor=(250, 248, 240), resample=Image.BICUBIC)
    a = np.asarray(img).astype(np.int16) + np.random.RandomState(1).randint(-18, 18, (H, W, 1))
    img = Image.fromarray(np.clip(a, 0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.6))
    img.save(path)
    json.dump([dict(ten_mon=s, tin_chi=tc, diem10=g, diem_chu=l) for s, tc, g, l in ROWS],
              open(path.rsplit('.', 1)[0] + '.json', 'w'), ensure_ascii=False, indent=1)
if __name__ == '__main__':
    make(os.path.join(HERE, 'synthetic_handwriting.png'))
