# -*- coding: utf-8 -*-
"""Ảnh QLHT thật cho Hướng dẫn: xóa tên tài khoản, gắn số bước, nén WebP."""
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

UPLOADS = "/home/ubuntu/.cursor/projects/workspace/uploads"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "guide")
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
FONTB = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
NAVY = (11, 78, 162)
GOLD = (245, 184, 0)
RED = (196, 40, 40)


def font(size, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, size)


def to_pil(bgr):
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def save(image, name, max_side=1200):
    image = image.convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    path = os.path.join(OUT, name)
    image.save(path, "WEBP", quality=82, method=6)
    print(name, image.size, os.path.getsize(path))


def badge(draw, xy, number):
    x, y = xy
    draw.ellipse((x, y, x + 36, y + 36), fill=GOLD, outline=RED, width=2)
    label = str(number)
    box = draw.textbbox((0, 0), label, font=font(18, True))
    draw.text((x + 18 - (box[2] - box[0]) / 2, y + 6), label, font=font(18, True), fill=NAVY)


def redact_menu():
    image = cv2.imread(os.path.join(UPLOADS, "3-menu_bbae.png"))
    # Chỉ xóa họ tên sau chữ "Tài khoản". Màu lấy từ nền thanh menu.
    cv2.rectangle(image, (1312, 152), (1532, 181), (160, 105, 44), -1)
    return image


def highlight_menu(bgr):
    pil = to_pil(bgr)
    draw = ImageDraw.Draw(pil)
    # Icon thứ 5: Kết quả học tập, kèm dòng chữ dưới icon.
    box = (628, 186, 792, 360)
    draw.rectangle(box, outline=GOLD, width=6)
    draw.rectangle((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), outline=RED, width=2)
    badge(draw, (box[0] - 8, box[1] - 18), 3)
    return pil


def crop_mark(path):
    pil = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(pil)
    draw.rectangle((6, 6, pil.width - 7, pil.height - 7), outline=GOLD, width=6)
    draw.rectangle((2, 2, pil.width - 3, pil.height - 3), outline=RED, width=2)
    badge(draw, (16, 16), 5)
    return pil


def sai_crops(path):
    bgr = cv2.imread(path)
    save(to_pil(bgr), "crop-dung.webp")
    save(to_pil(bgr[48:, :]), "crop-sai-header.webp")
    save(to_pil(bgr[:, :1100]), "crop-sai-cot.webp")
    save(to_pil(cv2.GaussianBlur(bgr, (31, 31), 0)), "crop-sai-mo.webp")


def formula_card():
    image = Image.new("RGB", (1100, 720), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1100, 8), fill=GOLD)
    draw.text((36, 28), "Điểm học phần trên trang này", font=font(28, True), fill=NAVY)
    draw.text((36, 78), "Điểm hệ 10  =  làm tròn 1 số  (BP × w1 + GK × w2 + CK × w3)", font=font(22, True), fill=(29, 42, 58))
    draw.text((36, 118), "Mặc định w1 = 20%, w2 = 30%, w3 = 50%. Nếu ba ô không cộng đủ 100, trang chia lại theo tỷ lệ.", font=font(18), fill=(70, 84, 104))
    draw.rounded_rectangle((36, 168, 1064, 248), 12, fill=(255, 246, 214), outline=GOLD)
    draw.text((52, 188), "Ví dụ: bộ phận 8, giữa kỳ 7, cuối kỳ 9", font=font(18), fill=NAVY)
    draw.text((52, 214), "8×0,2 + 7×0,3 + 9×0,5 = 8,2, chữ B+, hệ 4 là 3,5", font=font(20, True), fill=(29, 42, 58))
    rows = [
        ("Điểm hệ 10", "Chữ", "Hệ 4"),
        ("9,5 – 10", "A+", "4,0"),
        ("8,5 – 9,4", "A", "4,0"),
        ("8,0 – 8,4", "B+", "3,5"),
        ("7,0 – 7,9", "B", "3,0"),
        ("6,5 – 6,9", "C+", "2,5"),
        ("5,5 – 6,4", "C", "2,0"),
        ("5,0 – 5,4", "D+", "1,5"),
        ("4,0 – 4,9", "D", "1,0"),
        ("dưới 4,0", "F", "0"),
    ]
    y = 276
    for index, row in enumerate(rows):
        bg = (11, 78, 162) if index == 0 else ((248, 250, 252) if index % 2 == 0 else (255, 255, 255))
        fg = (255, 255, 255) if index == 0 else (29, 42, 58)
        draw.rectangle((36, y, 620, y + 36), fill=bg)
        draw.text((52, y + 6), row[0], font=font(16, True), fill=fg)
        draw.text((280, y + 6), row[1], font=font(16, True), fill=fg)
        draw.text((420, y + 6), row[2], font=font(16, True), fill=fg)
        y += 36
    draw.text((650, 290), "Thang ô nhập điểm và bảng\nĐiểm học phần đang dùng\n(QĐ 1586, khóa 2021 trở đi).\nA+ và A cùng 4,0.", font=font(18), fill=(70, 84, 104))
    draw.text((650, 430), "QĐ 1473 (khóa 2020 trở về trước)\nkhông có A+ và B+:\nA 8,5 = 4 · B 7,0 = 3\nC 5,5 = 2 · D 4,0 = 1 · F = 0.", font=font(18), fill=(70, 84, 104))
    save(image, "calc-scale.webp", max_side=1200)


def example_card():
    image = Image.new("RGB", (1100, 560), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1100, 8), fill=GOLD)
    draw.text((36, 24), "Học kỳ 2 · 2024-2025 trên ảnh mẫu", font=font(26, True), fill=NAVY)
    draw.text((36, 68), "CPA = tổng (hệ 4 × tín chỉ) / tổng tín chỉ có chữ, làm tròn 2 số.", font=font(18), fill=(70, 84, 104))
    lines = [
        "Chủ nghĩa xã hội khoa học   2 × 3,5 = 7",
        "An toàn thông tin            2 × 4,0 = 8",
        "Phát triển chương trình      3 × 4,0 = 12",
        "Cơ sở dữ liệu                3 × 3,0 = 9",
        "Đồ họa máy tính              3 × 4,0 = 12",
        "Mã nguồn mở                  3 × 4,0 = 12",
        "Lý luận dạy học Tin học      3 × 4,0 = 12",
        "Giao tiếp sư phạm            2 × 4,0 = 8",
    ]
    y = 112
    for line in lines:
        draw.text((36, y), line, font=font(18), fill=(29, 42, 58))
        y += 32
    draw.rounded_rectangle((36, 390, 1064, 520), 12, fill=(232, 240, 251))
    draw.text((52, 408), "8 môn có chữ: 80 điểm-tín chỉ / 21 tín chỉ = 3,81", font=font(20, True), fill=NAVY)
    draw.text((52, 448), "Giáo dục thể chất 4 (1 tín chỉ) chưa có điểm nên không vào mẫu số.", font=font(18), fill=(29, 42, 58))
    draw.text((52, 478), "Dòng tổng 22 tín chỉ trên portal vẫn tính môn đang học đó.", font=font(18), fill=(29, 42, 58))
    save(image, "calc-example.webp", max_side=1200)


def main():
    os.makedirs(OUT, exist_ok=True)
    login = Image.open(os.path.join(UPLOADS, "1-login-page_2986.png")).convert("RGB")
    box = Image.open(os.path.join(UPLOADS, "2-login-box_c229.png")).convert("RGB")
    icon = Image.open(os.path.join(UPLOADS, "4-ketquahoctap_e39d.png")).convert("RGB")
    table = os.path.join(UPLOADS, "5-bangdiem_ad3a.png")
    save(login, "qlht-1-login.webp")
    save(box, "qlht-2-login.webp", max_side=800)
    save(highlight_menu(redact_menu()), "qlht-3-menu.webp")
    marked = icon.copy()
    draw = ImageDraw.Draw(marked)
    draw.rectangle((2, 2, marked.width - 3, marked.height - 3), outline=GOLD, width=4)
    save(marked, "qlht-4-icon.webp", max_side=480)
    save(Image.open(table).convert("RGB"), "qlht-5-table.webp")
    save(crop_mark(table), "qlht-5-crop.webp")
    sai_crops(table)
    formula_card()
    example_card()


if __name__ == "__main__":
    main()
