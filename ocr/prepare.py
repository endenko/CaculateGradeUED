# -*- coding: utf-8 -*-
"""Chuẩn bị ảnh điện thoại trước OCR: EXIF, HEIC, nghiêng, phối cảnh, tương phản.

Ảnh được thu nhỏ trước các bước nặng để RAM không vượt gói Render 512 MB.
"""
from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageOps

PHONE_MAX_SIDE = int(os.environ.get("PHONE_MAX_SIDE", "1400"))
_HEIC_MESSAGE = (
    "Ảnh HEIC/HEIF chưa đọc được. Trên iPhone hãy gửi dạng JPEG: "
    "mở ảnh → Chia sẻ → Lưu thành JPEG, hoặc tắt Định dạng hiệu quả cao trong Cài đặt → Máy ảnh."
)


class PhotoPrepareError(Exception):
    pass


def _is_heic(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            blob = handle.read(64)
    except OSError:
        return False
    return any(tag in blob for tag in (b"ftypheic", b"ftypheix", b"ftypheif", b"ftypmif1", b"ftypmsf1"))


def _open_pil(path: str, max_side: int = 1600) -> Image.Image:
    """Đọc ảnh, xoay theo EXIF, thu nhỏ ngay để không giữ bitmap lớn trên RAM."""
    if _is_heic(path):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError as exc:
            raise PhotoPrepareError(_HEIC_MESSAGE) from exc
    try:
        image = Image.open(path)
        try:
            image.draft("RGB", (max_side, max_side))
        except Exception:
            pass
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return image.convert("RGB")
    except PhotoPrepareError:
        raise
    except Exception as exc:
        if _is_heic(path):
            raise PhotoPrepareError(_HEIC_MESSAGE) from exc
        raise PhotoPrepareError("Không đọc được file ảnh. Hãy gửi JPG hoặc PNG.") from exc


def _to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _fit_side(bgr: np.ndarray, min_side: int, max_side: int) -> np.ndarray:
    """Đưa cạnh dài vào khoảng đọc được, không phóng quá 4 lần."""
    height, width = bgr.shape[:2]
    long_side = max(height, width)
    if long_side < min_side:
        scale = min(4.0, min_side / float(long_side))
        bgr = cv2.resize(bgr, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_CUBIC)
    return _downscale(bgr, max_side)


def _downscale(bgr: np.ndarray, max_side: int) -> np.ndarray:
    height, width = bgr.shape[:2]
    long_side = max(height, width)
    if long_side <= max_side:
        return bgr
    scale = max_side / float(long_side)
    return cv2.resize(bgr, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)


def _order_quad(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def _perspective(bgr: np.ndarray) -> np.ndarray:
    """Gỡ phối cảnh nếu thấy một tứ giác lớn (màn hình hoặc tờ giấy), không phải cả khung ảnh."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    height, width = gray.shape
    image_area = float(height * width)
    best = None
    best_area = 0.0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 0.18 * image_area or area > 0.92 * image_area:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4 and area > best_area:
            best, best_area = approx, area
    if best is None:
        return bgr
    quad = _order_quad(best)
    width_a = np.linalg.norm(quad[2] - quad[3])
    width_b = np.linalg.norm(quad[1] - quad[0])
    height_a = np.linalg.norm(quad[1] - quad[2])
    height_b = np.linalg.norm(quad[0] - quad[3])
    out_w = int(max(width_a, width_b))
    out_h = int(max(height_a, height_b))
    if out_w < 200 or out_h < 80:
        return bgr
    dest = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad, dest)
    return cv2.warpPerspective(bgr, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _deskew(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if len(coords) < 200:
        return bgr
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90
    if abs(angle) < 0.4 or abs(angle) > 15:
        return bgr
    height, width = bgr.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(bgr, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _crop_content(bgr: np.ndarray) -> np.ndarray:
    """Cắt vào khối chữ (bảng điểm), bỏ thanh trạng thái và khoảng trống của ảnh dọc."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 40, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 9))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = gray.shape
    image_area = float(height * width)
    best = None
    best_area = 0
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        if ch < 50 or cw < 80:
            continue
        if area > best_area:
            best, best_area = (x, y, cw, ch), area
    if best is None or best_area > 0.82 * image_area or best_area < 0.04 * image_area:
        return bgr
    x, y, cw, ch = best
    pad = 8
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(width, x + cw + pad), min(height, y + ch + pad)
    crop = bgr[y0:y1, x0:x1]
    if crop.shape[0] < 40 or crop.shape[1] < 80:
        return bgr
    return crop


def _contrast(bgr: np.ndarray) -> np.ndarray:
    smooth = cv2.bilateralFilter(bgr, 7, 45, 45)
    blur = cv2.GaussianBlur(smooth, (0, 0), 0.8)
    smooth = cv2.addWeighted(smooth, 1.35, blur, -0.35, 0)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lightness = clahe.apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)


def looks_like_phone_capture(path: str) -> bool:
    """Ảnh máy ảnh hoặc file rất lớn: dùng pipeline điện thoại kể cả khi người dùng chọn Portal."""
    try:
        with Image.open(path) as image:
            exif = image.getexif() or {}
            if exif.get(271) or exif.get(272):
                return True
            width, height = image.size
    except Exception:
        return _is_heic(path)
    return max(width, height) >= 2200 or _is_heic(path)


def prepare_phone_image(path: str) -> str:
    """Trả về file JPEG tạm đã nắn, thu nhỏ. Người gọi xóa file này."""
    bgr = _to_bgr(_open_pil(path, 1600))
    bgr = _perspective(bgr)
    bgr = _deskew(bgr)
    bgr = _crop_content(bgr)
    bgr = _fit_side(bgr, 1200, PHONE_MAX_SIDE)
    bgr = _contrast(bgr)
    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    handle.close()
    cv2.imwrite(handle.name, bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return handle.name


def prepare_exif_image(path: str) -> str | None:
    """Xoay theo EXIF rồi ghi JPEG tạm. None nếu không cần (PNG thẳng, không HEIC)."""
    if not _is_heic(path):
        try:
            with Image.open(path) as image:
                exif = image.getexif()
                orientation = exif.get(274) if exif else None
                if orientation in (None, 1):
                    return None
        except Exception:
            return None
    return prepare_phone_image(path)
