# -*- coding: utf-8 -*-
"""Ảnh điện thoại giả lập từ fixture portal phải ra cùng kỳ, tín chỉ và điểm."""
import os
import time
import unittest

import cv2
import numpy as np
from PIL import Image, ImageDraw

import app

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "portal_hk2_2024.png")
OUT = os.path.join(os.path.dirname(__file__), "fixtures", "phone")


def _signature(rows):
    def key(row):
        score = None if row.get("diem_10") is None else round(float(row["diem_10"]), 1)
        credit = row.get("tin_chi")
        return (credit is None, credit or 0, score is None, -1 if score is None else score, bool(row.get("in_progress")), row.get("lan") or 1)
    return sorted(key(row) for row in rows)


def _read(path, mode):
    import shutil
    import tempfile
    suffix = os.path.splitext(path)[1] or ".png"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    shutil.copy(path, tmp.name)
    started = time.perf_counter()
    result = app._run_ocr_file(tmp.name, mode)
    elapsed = round(time.perf_counter() - started, 2)
    if not result.get("success"):
        raise AssertionError(result.get("error") or "ocr failed")
    return result.get("term"), result.get("data") or [], elapsed


def _mobile_screenshot(src):
    """Ảnh chụp màn hình điện thoại đã phóng to: khung dọc, thanh trạng thái, bảng gần đầy bề ngang."""
    table = Image.open(src).convert("RGB")
    tw, th = table.size
    width, height = 1170, 2300
    shown_w = width - 20
    shown = table.resize((shown_w, max(1, int(th * shown_w / tw))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (245, 247, 250))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 64), fill=(20, 24, 28))
    draw.text((28, 22), "9:41", fill=(255, 255, 255))
    draw.text((width - 170, 22), "5G   80%", fill=(255, 255, 255))
    draw.rectangle((0, 64, width, 124), fill=(255, 255, 255))
    draw.rectangle((0, 123, width, 124), fill=(210, 216, 224))
    draw.text((22, 84), "qlht.ued.udn.vn", fill=(11, 78, 162))
    canvas.paste(shown, (10, 140))
    path = os.path.join(OUT, "mobile_screenshot.png")
    canvas.save(path, "PNG")
    return path


def _camera_photo(src):
    """Ảnh máy chụp màn hình: phối cảnh, xoay, nhiễu, lóa, tương phản thấp."""
    bgr = cv2.imread(src)
    height, width = bgr.shape[:2]
    source = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    canvas_w, canvas_h = int(width * 1.35), int(height * 2.1)
    canvas = np.full((canvas_h, canvas_w, 3), (32, 36, 42), np.uint8)
    margin_x, margin_y = 70, 90
    dest = np.float32([
        [margin_x + 50, margin_y + 30],
        [canvas_w - margin_x - 20, margin_y + 80],
        [canvas_w - margin_x - 40, canvas_h - margin_y - 10],
        [margin_x + 15, canvas_h - margin_y - 50],
    ])
    matrix = cv2.getPerspectiveTransform(source, dest)
    shot = cv2.warpPerspective(bgr, matrix, (canvas_w, canvas_h))
    mask = cv2.warpPerspective(np.full((height, width), 255, np.uint8), matrix, (canvas_w, canvas_h))
    canvas[mask > 0] = shot[mask > 0]
    center = (canvas_w / 2, canvas_h / 2)
    rotate = cv2.getRotationMatrix2D(center, 6.5, 1.0)
    spun = cv2.warpAffine(canvas, rotate, (canvas_w, canvas_h), borderValue=(32, 36, 42))
    spun = cv2.convertScaleAbs(spun, alpha=0.86, beta=12)
    noise = np.random.default_rng(3).normal(0, 4, spun.shape).astype(np.int16)
    spun = np.clip(spun.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    glare = np.zeros_like(spun)
    cv2.ellipse(glare, (int(canvas_w * 0.72), int(canvas_h * 0.28)), (180, 70), 20, 0, 360, (255, 255, 255), -1)
    spun = cv2.addWeighted(spun, 1.0, glare, 0.12, 0)
    yy, xx = np.mgrid[0:canvas_h, 0:canvas_w]
    moire = (5 * np.sin(xx / 3.4) * np.sin(yy / 3.1)).astype(np.int16)
    spun = np.clip(spun.astype(np.int16) + moire[:, :, None], 0, 255).astype(np.uint8)
    spun = cv2.GaussianBlur(spun, (3, 3), 0.4)
    path = os.path.join(OUT, "camera_screen.png")
    cv2.imwrite(path, spun)
    return path


class PhoneOcrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(OUT, exist_ok=True)
        cls.base_term, cls.base_rows, cls.base_seconds = _read(FIXTURE, "computer")
        cls.mobile = _mobile_screenshot(FIXTURE)
        cls.camera = _camera_photo(FIXTURE)

    def test_phone_images_match_computer_rows(self):
        self.assertIsNotNone(self.base_term)
        self.assertGreaterEqual(len(self.base_rows), 8)
        expected = _signature(self.base_rows)
        print("PHONE_BASE", self.base_seconds, "s", len(self.base_rows), self.base_term)
        for label, path in (("mobile_screenshot", self.mobile), ("camera_photo", self.camera)):
            term, rows, seconds = _read(path, "phone")
            print(f"PHONE_{label}", seconds, "s", "rows", len(rows), "term", term, "match", _signature(rows) == expected)
            self.assertEqual(term, self.base_term, label)
            self.assertEqual(_signature(rows), expected, label)

    def test_heic_and_exif_and_bad_heic_message(self):
        from PIL import Image as PILImage
        import pillow_heif
        pillow_heif.register_heif_opener()
        heic_path = os.path.join(OUT, "fixture.heic")
        PILImage.open(FIXTURE).convert("RGB").save(heic_path, format="HEIF", quality=50)
        term, rows, seconds = _read(heic_path, "computer")
        print("PHONE_heic", seconds, "s", "rows", len(rows), "term", term)
        self.assertEqual(term, self.base_term)
        self.assertEqual(_signature(rows), _signature(self.base_rows))

        tilted = PILImage.new("RGB", (80, 40), (255, 255, 255))
        exif = tilted.getexif()
        exif[274] = 6
        jpeg_path = os.path.join(OUT, "exif_rot.jpg")
        tilted.save(jpeg_path, format="JPEG", exif=exif)
        from ocr.prepare import prepare_exif_image
        prepared = prepare_exif_image(jpeg_path)
        self.assertIsNotNone(prepared)
        fixed = cv2.imread(prepared)
        os.remove(prepared)
        self.assertGreater(fixed.shape[0], fixed.shape[1])

        fake = os.path.join(OUT, "broken.heic")
        with open(fake, "wb") as handle:
            handle.write(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32)
        from ocr.prepare import PhotoPrepareError, prepare_phone_image
        with self.assertRaises(PhotoPrepareError) as caught:
            prepare_phone_image(fake)
        self.assertIn("HEIC", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
