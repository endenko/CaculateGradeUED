# -*- coding: utf-8 -*-
import os
import unittest

from PIL import Image, ImageDraw, ImageFont

import schedule_ocr

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures")


def word(text, x, y):
    return {"text": text, "x": x, "y": y}


class ExamParseTests(unittest.TestCase):
    def test_columns_and_header_term(self):
        words = [
            word("Lịch thi Năm học: 2026-2027 Học kỳ: 1", 400, 20),
            word("Stt", 40, 60), word("Mã học phần", 120, 60), word("Tên học phần", 280, 60),
            word("Hình thức thi", 460, 60), word("Giờ", 560, 60), word("Ngày thi", 660, 60),
            word("Buổi thi", 760, 60), word("Nhóm học phần", 880, 60), word("Nhóm thi", 1000, 60),
            word("Tên phòng thi", 1120, 60),
            word("1", 40, 100), word("31241014", 120, 100), word("Lập trình Java", 280, 100),
            word("Tự luận", 460, 100), word("13:30", 560, 100), word("07-12-2026", 660, 100),
            word("Chiều", 760, 100), word("26-0101", 880, 100), word("01", 1000, 100),
            word("B3-102", 1120, 100),
        ]
        parsed = schedule_ocr.parse_exam(words)
        self.assertEqual(parsed["nam_hoc"], "2026-2027")
        self.assertEqual(parsed["hoc_ky"], "1")
        row = parsed["rows"][0]
        self.assertEqual(row["ma_hp"], "31241014")
        self.assertEqual(row["ten_mon"], "Lập trình Java")
        self.assertEqual(row["hinh_thuc"], "Tự luận")
        self.assertEqual(row["gio"], "13:30")
        self.assertEqual(row["ngay"], "07-12-2026")
        self.assertEqual(row["buoi"], "Chiều")
        self.assertEqual(row["nhom"], "26-0101")
        self.assertEqual(row["phong"], "B3-102")


class TimetableParseTests(unittest.TestCase):
    def test_x_marks_select_periods_and_sparse_weeks(self):
        words = [
            word("Tuần 1 bắt đầu từ 17-08-2026", 300, 15),
            word("Thứ", 40, 50), word("Mã học phần", 140, 50), word("Tên học phần", 300, 50),
            word("1", 500, 50), word("2", 540, 50), word("3", 580, 50),
            word("1", 760, 50), word("2", 800, 50), word("5", 840, 50),
            word("Thứ 2", 40, 90), word("31241014", 140, 90), word("Lập trình Java", 300, 90),
            word("Sáng", 420, 90), word("x", 500, 90), word("x", 540, 90),
            word("x", 760, 90), word("x", 840, 90), word("A5-207", 360, 90),
        ]
        parsed = schedule_ocr.parse_timetable(words)
        self.assertEqual(parsed["week_start"], "2026-08-17")
        row = parsed["rows"][0]
        self.assertEqual(row["ma_hp"], "31241014")
        self.assertEqual(row["thu"], 2)
        self.assertEqual(row["tiet"], [1, 2])
        self.assertEqual(row["start"], "07:00")
        self.assertEqual(row["end"], "08:45")
        self.assertEqual(row["tuan"], [1, 5])
        self.assertEqual(row["phong"], "A5-207")
        self.assertEqual(row["buoi"], "Sáng")


def _font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_exam():
    os.makedirs(FIXTURE, exist_ok=True)
    image = Image.new("RGB", (1400, 220), "white")
    draw = ImageDraw.Draw(image)
    font = _font(22)
    draw.text((40, 16), "Lich thi Nam hoc: 2026-2027 Hoc ky: 1", fill="black", font=font)
    headers = [(40, "Stt"), (120, "Ma hoc phan"), (320, "Ten hoc phan"), (560, "Hinh thuc thi"),
               (760, "Gio"), (860, "Ngay thi"), (1040, "Buoi thi"), (1160, "Phong")]
    for x, text in headers:
        draw.text((x, 70), text, fill="black", font=font)
    values = [(40, "1"), (120, "31241014"), (320, "Lap trinh Java"), (560, "Tu luan"),
              (760, "13:30"), (860, "07-12-2026"), (1040, "Chieu"), (1160, "B3-102")]
    for x, text in values:
        draw.text((x, 120), text, fill="black", font=font)
    path = os.path.join(FIXTURE, "lich-thi.png")
    image.save(path)
    return path


def draw_timetable():
    os.makedirs(FIXTURE, exist_ok=True)
    image = Image.new("RGB", (1100, 180), "white")
    draw = ImageDraw.Draw(image)
    font = _font(20)
    draw.text((20, 10), "Tuan 1 bat dau tu 17-08-2026", fill="black", font=font)
    for index, label in enumerate(["Thu", "Ma", "Ten"]):
        draw.text((20 + index * 140, 50), label, fill="black", font=font)
    for n in range(1, 4):
        draw.text((480 + (n - 1) * 36, 50), str(n), fill="black", font=font)
    for n, label in ((1, "1"), (2, "2"), (5, "5")):
        draw.text((700 + [1, 2, 5].index(n) * 40, 50), label, fill="black", font=font)
    draw.text((20, 100), "Thu 2", fill="black", font=font)
    draw.text((160, 100), "31241014", fill="black", font=font)
    draw.text((300, 100), "Java", fill="black", font=font)
    draw.text((480, 100), "x", fill="black", font=font)
    draw.text((516, 100), "x", fill="black", font=font)
    draw.text((700, 100), "x", fill="black", font=font)
    draw.text((780, 100), "x", fill="black", font=font)
    path = os.path.join(FIXTURE, "thoi-khoa-bieu.png")
    image.save(path)
    return path


class TimetableImageTests(unittest.TestCase):
    def test_timetable_image_reads_periods_and_weeks(self):
        from ocr.engines import rapid_words
        words = rapid_words(draw_timetable())
        parsed = schedule_ocr.parse_timetable(words)
        self.assertTrue(parsed["rows"], [w["text"] for w in words])
        row = parsed["rows"][0]
        self.assertEqual(row["ma_hp"], "31241014")
        self.assertEqual(row["tiet"], [1, 2])
        self.assertEqual(row["tuan"], [1, 5])
        self.assertEqual(parsed["week_start"], "2026-08-17")
    def test_exam_image_round_trip(self):
        from ocr.engines import rapid_words
        path = draw_exam()
        words = rapid_words(path)
        parsed = schedule_ocr.parse_exam(words)
        self.assertTrue(parsed["rows"], words)
        row = parsed["rows"][0]
        self.assertEqual(row["ma_hp"], "31241014")
        self.assertEqual(row["ngay"], "07-12-2026")
        self.assertEqual(row["gio"], "13:30")
        self.assertIn("B3-102", row["phong"])


if __name__ == "__main__":
    unittest.main()
