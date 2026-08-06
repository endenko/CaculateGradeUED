# -*- coding: utf-8 -*-
"""
OCR engines for UED Calculate Grade.

Three engines, one interface:
  1. TesseractEngine   — local Tesseract OCR (vie+eng). Used for computer screenshots (KEPT from original).
  2. VietOcrEngine     — PaddleOCR with the Vietnamese model (lang='vi'). Replaces Google Cloud Vision
                         for handwritten transcripts (viết tay) — works fully offline, no API key.
  3. GoogleVisionEngine— OPTIONAL. Only loaded when GOOGLE_APPLICATION_CREDENTIALS is set AND
                         OCR_HANDWRITING_ENGINE=google. google-cloud-vision is NOT in requirements.txt
                         (see requirements-google.txt). Kept as a comparison hook for the thesis.

Engine selection for handwriting mode is controlled by the env var OCR_HANDWRITING_ENGINE:
    'paddle' (default) -> VietOcrEngine, falls back to TesseractEngine if PaddleOCR is missing
    'tesseract'        -> TesseractEngine (vie+eng)
    'google'           -> GoogleVisionEngine (requires credentials + extra package)
"""
import io
import os
import re
import tempfile
import threading

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Config from environment (no hardcoded Windows paths anymore)
# ---------------------------------------------------------------------------
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "").strip()

if TESSERACT_CMD:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    import pytesseract  # let pytesseract find tesseract on PATH (Docker: /usr/bin/tesseract)

OCR_HANDWRITING_ENGINE = os.environ.get("OCR_HANDWRITING_ENGINE", "paddle").strip().lower()

# ---------------------------------------------------------------------------
# Shared image preprocessing (from original LocalOCR.py)
# ---------------------------------------------------------------------------
def preprocess_image(image_path):
    """Grayscale + 2x resize + Otsu threshold — the original Tesseract pipeline."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Không đọc được ảnh: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    processed = cv2.threshold(img_resized, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    return processed


# ===========================================================================
# 1) TESSERACT (kept — original local OCR for computer screenshots)
# ===========================================================================
def tesseract_words(image_path):
    """Word-level OCR (vie+eng) with coordinates — same logic as original perform_local_ocr_computer."""
    processed_img = preprocess_image(image_path)
    config = '--oem 3 --psm 6'
    data = pytesseract.image_to_data(processed_img, lang='vie+eng', config=config,
                                     output_type=pytesseract.Output.DICT)
    word_list = []
    for i in range(len(data['text'])):
        if int(data['conf'][i]) > 10:
            text = data['text'][i].strip()
            text = re.sub(r'[^\w\s\+\-\*,\.]', '', text)
            if text:
                # coordinates were doubled by the 2x resize -> divide by 2
                x = (data['left'][i] + data['width'][i] / 2) / 2
                y = (data['top'][i] + data['height'][i] / 2) / 2
                word_list.append({'text': text, 'x': x, 'y': y})
    return word_list


def tesseract_full_text(image_path):
    """Plain text OCR (vie+eng) — used by /api/scan_detail_score (Điểm Bộ Phận / Giữa Kỳ)."""
    processed_img = preprocess_image(image_path)
    config = '--oem 3 --psm 6'
    return pytesseract.image_to_string(processed_img, lang='vie+eng', config=config)


# ===========================================================================
# 2) VIETNAMESE OCR — PaddleOCR lang='vi' (replaces Google Cloud Vision)
# ===========================================================================
_paddle_lock = threading.Lock()
_paddle_ocr = None
_paddle_available = None


def _paddle_is_available():
    global _paddle_available
    if _paddle_available is None:
        try:
            import paddleocr  # noqa: F401
            _paddle_available = True
        except Exception:
            _paddle_available = False
    return _paddle_available


# Paddle inference run mode: 'paddle' (stable, default) or 'mkldnn' (oneDNN, faster on Linux).
# NOTE: 'mkldnn' crashes with PP-OCRv6 models on Windows/paddle 3.3 (onednn PIR bug),
# so the default is 'paddle' for cross-platform stability.
PADDLE_RUN_MODE = os.environ.get('PADDLE_RUN_MODE', 'paddle').strip().lower()


def _get_paddle_ocr():
    """Lazy singleton PaddleOCR with the Vietnamese model (lang='vi')."""
    global _paddle_ocr
    if _paddle_ocr is None:
        from paddleocr import PaddleOCR
        engine_config = {'run_mode': PADDLE_RUN_MODE}
        try:
            # Disable the doc-orientation/unwarping extras when supported (faster, smaller image)
            _paddle_ocr = PaddleOCR(lang='vi', use_doc_orientation_classify=False,
                                    use_doc_unwarping=False, use_textline_orientation=False,
                                    engine_config=engine_config)
        except TypeError:
            _paddle_ocr = PaddleOCR(lang='vi', engine_config=engine_config)
    return _paddle_ocr


def _paddle_extract_words(predictions):
    """Robust extractor for PaddleOCR 3.x predict() output (handles rec_polys / rec_boxes variants)."""
    word_list = []
    for page in predictions:
        if not isinstance(page, dict):
            continue
        texts = page.get('rec_texts') or []
        boxes = page.get('rec_polys') or page.get('rec_boxes') or page.get('dt_polys') or []
        for text, box in zip(texts, boxes):
            text = (text or '').strip()
            if not text:
                continue
            try:
                pts = np.asarray(box, dtype=np.float64)
                word_list.append({'text': text,
                                  'x': float(pts[:, 0].mean()),
                                  'y': float(pts[:, 1].mean())})
            except Exception:
                continue
    return word_list


def _prepare_image(image_path):
    """Upscale SMALL images before OCR — tiny handwriting photos lose their
    grade columns during text detection. Mirrors the original Tesseract path's
    2x-resize trick, but only kicks in below 1200px (adaptive, max 3x)."""
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    h, w = img.shape[:2]
    max_dim = max(h, w)
    if max_dim >= 1200:
        return image_path  # already large enough
    scale = min(3.0, 1600.0 / max_dim)
    up = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.close()
    cv2.imwrite(tmp.name, up)
    return tmp.name


def _needs_second_pass(words):
    """Trigger a higher-res det pass when many boxes look like subjects with no
    grade digits (the det model sometimes drops tiny grade columns)."""
    if not words:
        return False
    letter_only = [w for w in words
                   if len(w['text']) >= 4 and not any(c.isdigit() for c in w['text'])]
    return len(letter_only) / len(words) >= 0.4


def _merge_word_lists(a, b):
    """Union of two word lists from the SAME input image, deduped by text+cell."""
    seen = set()
    out = []
    for w in a + b:
        key = (w['text'], int(w['x'] // 30), int(w['y'] // 30))
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def vietocr_words(image_path):
    """Vietnamese OCR (PaddleOCR lang='vi') — reads handwritten Vietnamese transcripts offline."""
    ocr = _get_paddle_ocr()
    tmp_path = None
    try:
        path = _prepare_image(image_path)
        if path != image_path:
            tmp_path = path
        with _paddle_lock:
            try:
                predictions = ocr.predict(path)
            except AttributeError:
                # older PaddleOCR 2.x API
                result = ocr.ocr(path, cls=True)
                word_list = []
                for page in result or []:
                    for line in page or []:
                        box, (text, _conf) = line
                        word_list.append({'text': text.strip(),
                                          'x': sum(p[0] for p in box) / 4.0,
                                          'y': sum(p[1] for p in box) / 4.0})
                return word_list
        words = _paddle_extract_words(predictions)

        # Second det pass at higher resolution recovers grade columns that the
        # default-res pass missed on small handwriting (e.g. '7.3', 'B').
        if _needs_second_pass(words):
            try:
                with _paddle_lock:
                    predictions2 = ocr.predict(path, text_det_limit_side_len=1920)
                words2 = _paddle_extract_words(predictions2)
                words = _merge_word_lists(words, words2)
                print(f"[OCR] second det pass merged {len(words2)} -> {len(words)} words")
            except Exception as e:
                print(f"[OCR] second det pass failed: {e}")
        return words
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ===========================================================================
# 3) GOOGLE CLOUD VISION (OPTIONAL — only when explicitly enabled)
# ===========================================================================
def _google_is_available():
    return bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))


def google_words(image_path):
    """Google Cloud Vision document_text_detection (original handwriting engine, kept optional)."""
    from google.cloud import vision
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    if not response.text_annotations:
        return []
    word_list = []
    for w in response.text_annotations[1:]:
        xs = [v.x for v in w.bounding_poly.vertices]
        ys = [v.y for v in w.bounding_poly.vertices]
        word_list.append({'text': w.description, 'x': sum(xs) / 4.0, 'y': sum(ys) / 4.0})
    return word_list


# ===========================================================================
# Dispatch helpers used by app.py
# ===========================================================================
def computer_words(image_path):
    """Computer-screenshot mode: Tesseract (original behavior, kept)."""
    return tesseract_words(image_path)


def handwriting_words(image_path):
    """Handwritten mode: Vietnamese OCR (PaddleOCR lang='vi' by default).

    Returns (word_list, engine_name). Falls back to Tesseract vie+eng if the
    Vietnamese engine is not available/installed, so the app never crashes.
    """
    engine = OCR_HANDWRITING_ENGINE
    if engine == 'google' and _google_is_available():
        try:
            return google_words(image_path), 'google'
        except Exception as e:
            print(f"[OCR] Google Vision failed ({e}) -> falling back")
            engine = 'paddle'

    if engine == 'paddle' and _paddle_is_available():
        try:
            return vietocr_words(image_path), 'paddle'
        except Exception as e:
            print(f"[OCR] PaddleOCR failed ({e}) -> falling back to Tesseract")
            engine = 'tesseract'

    # tesseract (or any fallback path)
    return tesseract_words(image_path), 'tesseract'


def warmup():
    """Pre-download PaddleOCR models + verify Tesseract — called at Docker build time."""
    if OCR_HANDWRITING_ENGINE in ('paddle', 'google') and _paddle_is_available():
        try:
            _get_paddle_ocr()
            print("[warmup] PaddleOCR Vietnamese models ready")
        except Exception as e:
            print(f"[warmup] PaddleOCR unavailable: {e}")
    print("[warmup] done")
