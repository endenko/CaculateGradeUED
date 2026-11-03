# -*- coding: utf-8 -*-
"""Vẽ hình minh họa Hướng dẫn từ fixture portal. Không bịa giao diện QLHT ngoài ảnh thật."""
import os

import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "portal_hk2_2024.png")
OUT = os.path.join(ROOT, "static", "guide")

NAVY = (11, 78, 162)
NAVY_DARK = (6, 47, 102)
GOLD = (245, 184, 0)
INK = (29, 42, 58)
MUTED = (92, 107, 128)
LINE = (214, 222, 232)
PAGE = (244, 247, 251)

FONT = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
FONTB = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, size)


def browser(width, height, step, title):
    image = Image.new("RGB", (width, height), (226, 232, 240))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((14, 14, width - 14, height - 14), 18, fill=(255, 255, 255))
    draw.rectangle((14, 62, width - 14, 86), fill=(248, 250, 252))
    draw.rounded_rectangle((14, 14, width - 14, 78), 18, fill=(248, 250, 252))
    draw.rectangle((14, 40, width - 14, 78), fill=(248, 250, 252))
    for index, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        draw.ellipse((34 + index * 20, 28, 48 + index * 20, 42), fill=color)
    draw.rounded_rectangle((118, 24, width - 36, 50), 12, fill=(255, 255, 255), outline=LINE)
    draw.text((132, 28), "https://qlht.ued.udn.vn/", font=font(16), fill=INK)
    draw.rounded_rectangle((32, 96, 118, 126), 14, fill=GOLD)
    draw.text((46, 100), f"Bước {step}", font=font(16, True), fill=NAVY_DARK)
    draw.text((130, 99), title, font=font(18, True), fill=NAVY)
    return image, draw


def save(image, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    image.save(path, "PNG", optimize=True)
    print(name, image.size)


def step_open():
    image, draw = browser(960, 420, 1, "Mở QLHT")
    draw.rounded_rectangle((70, 170, 890, 300), 16, fill=PAGE, outline=LINE)
    draw.text((96, 196), "Trình duyệt", font=font(16), fill=MUTED)
    draw.text((96, 226), "qlht.ued.udn.vn", font=font(32, True), fill=NAVY)
    draw.text((96, 272), "Quản lý đào tạo — Trường Đại học Sư phạm, Đại học Đà Nẵng", font=font(16), fill=INK)
    save(image, "step-mo-qlht.png")


def step_login():
    image, draw = browser(960, 460, 2, "Đăng nhập")
    draw.text((80, 160), "Ô đăng nhập trên QLHT (sơ đồ, không phải giao diện thật)", font=font(15), fill=MUTED)
    draw.rounded_rectangle((80, 196, 620, 250), 10, fill=(255, 255, 255), outline=LINE)
    draw.text((96, 210), "Tài khoản", font=font(18), fill=MUTED)
    draw.rounded_rectangle((80, 266, 620, 320), 10, fill=(255, 255, 255), outline=LINE)
    draw.text((96, 280), "Mật khẩu", font=font(18), fill=MUTED)
    draw.rounded_rectangle((80, 344, 280, 396), 12, fill=NAVY)
    draw.text((112, 356), "Đăng nhập", font=font(18, True), fill=(255, 255, 255))
    save(image, "step-dang-nhap.png")


def step_menu():
    image, draw = browser(960, 440, 3, "Vào Bảng điểm / Kết quả học tập")
    draw.text((80, 156), "Trong menu của QLHT, mở mục bảng điểm. Tên trên site là một trong hai:", font=font(16), fill=INK)
    draw.rounded_rectangle((80, 200, 860, 268), 12, fill=(255, 246, 214), outline=GOLD)
    draw.ellipse((100, 220, 124, 244), fill=GOLD)
    draw.text((140, 218), "Bảng điểm", font=font(22, True), fill=NAVY_DARK)
    draw.rounded_rectangle((80, 284, 860, 352), 12, fill=(255, 246, 214), outline=GOLD)
    draw.ellipse((100, 304, 124, 328), fill=GOLD)
    draw.text((140, 302), "Kết quả học tập", font=font(22, True), fill=NAVY_DARK)
    save(image, "step-bang-diem.png")


def step_term():
    image, draw = browser(960, 420, 4, "Chọn học kỳ cần lấy")
    draw.text((80, 160), "Chọn đúng học kỳ trước khi chụp. Ví dụ kỳ trong ảnh mẫu:", font=font(16), fill=INK)
    draw.rounded_rectangle((80, 206, 700, 270), 12, fill=(255, 255, 255), outline=NAVY, width=2)
    draw.text((100, 222), "Học kỳ 2  —  Năm học 2024-2025", font=font(22, True), fill=NAVY)
    draw.text((80, 300), "Dòng này phải nằm trong ảnh. Thiếu dòng thì trang ghi Không xác định được kỳ/năm.", font=font(16), fill=MUTED)
    save(image, "step-chon-ky.png")


def step_computer(table):
    image, draw = browser(980, 560, 5, "Chụp và cắt trên máy tính")
    fitted = table.copy()
    fitted.thumbnail((900, 300), Image.Resampling.LANCZOS)
    x = (980 - fitted.width) // 2
    y = 168
    image.paste(fitted, (x, y))
    draw.rectangle((x - 4, y - 4, x + fitted.width + 3, y + fitted.height + 3), outline=GOLD, width=4)
    draw.rounded_rectangle((x, y + fitted.height + 16, x + 430, y + fitted.height + 52), 10, fill=NAVY)
    draw.text((x + 14, y + fitted.height + 24), "Windows: Win + Shift + S", font=font(16, True), fill=(255, 255, 255))
    draw.rounded_rectangle((x + 446, y + fitted.height + 16, x + fitted.width, y + fitted.height + 52), 10, fill=NAVY_DARK)
    draw.text((x + 460, y + fitted.height + 24), "Mac: Cmd + Shift + 4", font=font(16, True), fill=(255, 255, 255))
    save(image, "step-cat-may.png")


def step_phone(table):
    image = Image.new("RGB", (960, 640), (226, 232, 240))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((300, 24, 660, 616), 36, fill=(20, 24, 28))
    draw.rounded_rectangle((314, 40, 646, 600), 28, fill=(255, 255, 255))
    draw.rectangle((314, 40, 646, 78), fill=(20, 24, 28))
    draw.rounded_rectangle((314, 40, 646, 70), 20, fill=(20, 24, 28))
    draw.text((332, 48), "9:41", font=font(14, True), fill=(255, 255, 255))
    draw.text((560, 48), "5G  80%", font=font(14), fill=(255, 255, 255))
    fitted = table.copy()
    fitted.thumbnail((312, 360), Image.Resampling.LANCZOS)
    image.paste(fitted, (324, 96))
    draw.rectangle((320, 92, 324 + fitted.width + 4, 96 + fitted.height + 4), outline=GOLD, width=4)
    for cx, cy in ((320, 92), (324 + fitted.width, 92), (320, 96 + fitted.height), (324 + fitted.width, 96 + fitted.height)):
        draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=GOLD)
    draw.text((24, 80), "Bước 5", font=font(16, True), fill=NAVY)
    draw.text((24, 112), "Điện thoại", font=font(22, True), fill=NAVY_DARK)
    draw.text((24, 170), "1. Chụp màn hình", font=font(16), fill=INK)
    draw.text((24, 200), "2. Mở ứng dụng ảnh", font=font(16), fill=INK)
    draw.text((24, 230), "3. Cắt, giữ vùng viền vàng", font=font(16), fill=INK)
    draw.text((690, 120), "Giữ dòng\nHọc kỳ,\ncả bảng\nvà phần tổng.", font=font(16), fill=INK)
    save(image, "step-cat-dienthoai.png")


def crops(table):
    table.save(os.path.join(OUT, "crop-dung.png"), "PNG", optimize=True)
    bgr = cv2.cvtColor(cv2.imread(FIXTURE), cv2.COLOR_BGR2RGB)
    header = bgr[78:, :]
    Image.fromarray(header).save(os.path.join(OUT, "crop-sai-header.png"), "PNG", optimize=True)
    partial = bgr[:, :820]
    Image.fromarray(partial).save(os.path.join(OUT, "crop-sai-cot.png"), "PNG", optimize=True)
    blur = cv2.GaussianBlur(bgr, (31, 31), 0)
    Image.fromarray(blur).save(os.path.join(OUT, "crop-sai-mo.png"), "PNG", optimize=True)
    print("crops", table.size)


def main():
    os.makedirs(OUT, exist_ok=True)
    table = Image.open(FIXTURE).convert("RGB")
    step_open()
    step_login()
    step_menu()
    step_term()
    step_computer(table)
    step_phone(table)
    crops(table)


if __name__ == "__main__":
    main()
