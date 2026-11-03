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

import numpy as np
try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

# ---------------------------------------------------------------------------
# Config from environment (no hardcoded Windows paths anymore)
# ---------------------------------------------------------------------------
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "").strip()

try:
    import pytesseract
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
except ImportError:  # light deployments
    pytesseract = None

# On serverless hosts (Vercel / Render free) default to the light ONNX engine
_LIGHT_DEFAULT = 'rapid' if (os.environ.get('VERCEL') or os.environ.get('OCR_LIGHT') == '1') else 'vietocr'
OCR_HANDWRITING_ENGINE = os.environ.get("OCR_HANDWRITING_ENGINE", _LIGHT_DEFAULT).strip().lower()
OCR_COMPUTER_ENGINE = os.environ.get("OCR_COMPUTER_ENGINE", "auto").strip().lower()

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
    """Plain text OCR (vie+eng) — used by /api/scan_detail_score (Điểm Bộ Phận / Giữa Kỳ).
    Falls back to the VietOCR hybrid (line-joined) when Tesseract is not installed."""
    import shutil
    if not (TESSERACT_CMD or shutil.which('tesseract')):
        words = rapid_words(image_path) if OCR_HANDWRITING_ENGINE == 'rapid' else hybrid_words(image_path)
        words.sort(key=lambda w: (round(w['y'] / 20), w['x']))
        return "\n".join(w['text'] for w in words)
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

# Model profile:
#   'medium' (default) -> PP-OCRv6_medium_det/rec (most accurate, ~134 MB — local/docker-compose)
#   'hybrid'           -> PP-OCRv5_mobile_det + PP-OCRv6_medium_rec (~84 MB — good accuracy,
#                         still fits Render's free 512 MB plan)
#   'mobile'           -> PP-OCRv5_mobile_det/rec  (~10 MB — smallest footprint)
OCR_MODEL_SIZE = os.environ.get('OCR_MODEL_SIZE', 'medium').strip().lower()
_MODEL_NAMES = {
    'medium': (None, None),  # None -> PaddleOCR defaults (PP-OCRv6_medium_*)
    'hybrid': ('PP-OCRv5_mobile_det', 'PP-OCRv6_medium_rec'),
    'mobile': ('PP-OCRv5_mobile_det', 'PP-OCRv5_mobile_rec'),
}


def _get_paddle_ocr():
    """Lazy singleton PaddleOCR with the Vietnamese model (lang='vi')."""
    global _paddle_ocr
    if _paddle_ocr is None:
        from paddleocr import PaddleOCR
        det_name, rec_name = _MODEL_NAMES.get(OCR_MODEL_SIZE, _MODEL_NAMES['medium'])
        engine_config = {'run_mode': PADDLE_RUN_MODE}
        kwargs = dict(lang='vi', use_doc_orientation_classify=False,
                      use_doc_unwarping=False, use_textline_orientation=False,
                      engine_config=engine_config)
        if det_name:
            kwargs['text_detection_model_name'] = det_name
            kwargs['text_recognition_model_name'] = rec_name
        try:
            # Disable the doc-orientation/unwarping extras when supported (faster, smaller image)
            _paddle_ocr = PaddleOCR(**kwargs)
        except TypeError:
            kwargs.pop('use_doc_orientation_classify', None)
            kwargs.pop('use_doc_unwarping', None)
            kwargs.pop('use_textline_orientation', None)
            _paddle_ocr = PaddleOCR(**kwargs)
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
# 2b) HYBRID: PaddleOCR text DETECTION + VietOCR (pbcquoc/vietocr) RECOGNITION
#     VietOCR's vgg_transformer is trained on Vietnamese printed + handwritten
#     text and restores diacritics far better than PaddleOCR lang='vi'
#     (e.g. "Tu tung H Chí Minh" -> "Tư tưởng Hồ Chí Minh"). 100% free/offline.
# ===========================================================================
_hybrid_lock = threading.Lock()
_det_model = None
_vietocr_model = None
VIETOCR_CONFIG = os.environ.get('VIETOCR_CONFIG', 'vgg_transformer')
VIETOCR_WEIGHTS = os.environ.get('VIETOCR_WEIGHTS', os.path.expanduser('~/.cache/vietocr/vgg_transformer.pth'))


def _vietocr_is_available():
    try:
        import vietocr  # noqa: F401
        import torch  # noqa: F401
        return _paddle_is_available()
    except Exception:
        return False


def _get_hybrid():
    global _det_model, _vietocr_model
    if _det_model is None:
        from paddleocr import TextDetection
        det_name = os.environ.get('OCR_DET_MODEL', 'PP-OCRv6_medium_det')
        _det_model = TextDetection(model_name=det_name, engine_config={'run_mode': PADDLE_RUN_MODE})
    if _vietocr_model is None:
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor
        import functools
        import vietocr.tool.predictor as _vp
        from vietocr.tool.translate import translate as _tr
        # cap decoding length: a crop without EOS otherwise decodes 128 steps and can stall for minutes on CPU
        _vp.translate = functools.partial(_tr, max_seq_length=int(os.environ.get('VIETOCR_MAX_LEN', '64')))
        cfg_file = os.environ.get('VIETOCR_CONFIG_FILE', '')
        if cfg_file and os.path.exists(cfg_file):
            cfg = Cfg.load_config_from_file(cfg_file)  # offline (saved at build time)
        else:
            cfg = Cfg.load_config_from_name(VIETOCR_CONFIG)
            if cfg_file:
                try:
                    cfg.save(cfg_file)
                except OSError:
                    pass
        if isinstance(cfg.get('cnn'), dict) and 'pretrained' in cfg['cnn']:
            cfg['cnn']['pretrained'] = False  # full weights are loaded below; no torchvision download
        if os.path.exists(VIETOCR_WEIGHTS):
            cfg['weights'] = VIETOCR_WEIGHTS
        cfg['device'] = os.environ.get('VIETOCR_DEVICE', 'cpu')
        cfg['predictor']['beamsearch'] = False
        _vietocr_model = Predictor(cfg)
    return _det_model, _vietocr_model


def _hybrid_once(path, limit_side_len=None):
    from PIL import Image
    det, rec = _get_hybrid()
    kw = {'limit_side_len': limit_side_len} if limit_side_len else {}
    res = list(det.predict(path, **kw))
    polys = res[0]['dt_polys'] if res else []
    im = Image.open(path).convert('RGB')
    W, H = im.size
    boxes, crops = [], []
    rects = []
    for q in polys:
        pts = np.asarray(q, dtype=np.float64)
        rects.append((pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()))
    med_h = float(np.median([r[3] - r[1] for r in rects])) if rects else 0
    for x1, y1, x2, y2 in rects:
        if x2 - x1 < 3 or y2 - y1 < 3:
            continue
        # skip stamps / signatures / page-size blobs: they make the seq2seq
        # decoder run for minutes and never contain grade text
        if (y2 - y1) > max(4 * med_h, 0.25 * H) or (x2 - x1) > 0.95 * W:
            continue
        pad = max(2, int((y2 - y1) * 0.12))
        crops.append(im.crop((max(0, x1 - pad), max(0, y1 - pad), min(W, x2 + pad), min(H, y2 + pad))))
        boxes.append(((x1 + x2) / 2, (y1 + y2) / 2))
    texts = rec.predict_batch(crops) if crops else []
    return [{'text': t.strip(), 'x': float(b[0]), 'y': float(b[1])}
            for t, b in zip(texts, boxes) if t and t.strip()]


def hybrid_words(image_path):
    """Paddle det + VietOCR rec, with the same upscale / second-pass tricks."""
    tmp_path = None
    try:
        path = _prepare_image(image_path)
        if path != image_path:
            tmp_path = path
        with _hybrid_lock:
            words = _hybrid_once(path)
            if _needs_second_pass(words):
                try:
                    words2 = _hybrid_once(path, limit_side_len=1920)
                    words = _merge_word_lists(words, words2)
                except Exception as e:
                    print(f"[OCR] hybrid second pass failed: {e}")
        return words
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _tesseract_is_available():
    import shutil
    return bool(TESSERACT_CMD or shutil.which('tesseract'))


def engine_status():
    return {
        'handwriting_engine': OCR_HANDWRITING_ENGINE,
        'vietocr': _vietocr_is_available(),
        'paddleocr': _paddle_is_available(),
        'tesseract': _tesseract_is_available(),
        'google_vision': _google_is_available(),
        'rapidocr': _rapid_is_available(),
    }


# ===========================================================================
# 2c) LIGHT: RapidOCR (PaddleOCR models exported to ONNX, onnxruntime) — no torch,
#     no paddle. ~25 MB of models, fits 512 MB-2 GB free hosts / Vercel Python.
#     Diacritics are weaker; the DB fuzzy matcher restores the subject names.
# ===========================================================================
_rapid = None
_rapid_lock = threading.Lock()
MODELS_DIR = os.environ.get('MODELS_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models'))
RAPID_PROFILE = os.environ.get('RAPID_PROFILE', 'latin')  # 'latin' (PP-OCRv5 latin rec) | 'v6' (PP-OCRv6 small)


def _rapid_is_available():
    try:
        import rapidocr  # noqa: F401
        return True
    except Exception:
        return False


def _get_rapid():
    global _rapid
    if _rapid is None:
        from rapidocr import RapidOCR, LangRec, OCRVersion, ModelType
        if RAPID_PROFILE == 'v6':
            det, rec = 'PP-OCRv6_det_small.onnx', 'PP-OCRv6_rec_small.onnx'
            params = {}
        else:
            det, rec = 'ch_PP-OCRv5_det_mobile.onnx', 'latin_PP-OCRv5_rec_mobile.onnx'
            params = {"Rec.lang_type": LangRec.LATIN, "Rec.ocr_version": OCRVersion.PPOCRV5,
                      "Rec.model_type": ModelType.MOBILE, "Det.ocr_version": OCRVersion.PPOCRV5,
                      "Det.model_type": ModelType.MOBILE}
        params["Global.use_cls"] = False
        # bound detector input -> bounded RAM (fits 512 MB hosts)
        side = int(os.environ.get('RAPID_LIMIT_SIDE', '960'))
        params["Det.limit_type"] = os.environ.get('RAPID_LIMIT_TYPE', 'max')
        params["Det.limit_side_len"] = side
        params["Global.max_side_len"] = side
        params["Global.use_cls"] = False
        threads = int(os.environ.get('OMP_NUM_THREADS', '1'))
        params["EngineConfig.onnxruntime.intra_op_num_threads"] = threads
        params["EngineConfig.onnxruntime.inter_op_num_threads"] = 1
        params["EngineConfig.onnxruntime.enable_cpu_mem_arena"] = False
        if os.path.exists(os.path.join(MODELS_DIR, det)):
            params["Det.model_path"] = os.path.join(MODELS_DIR, det)
        if os.path.exists(os.path.join(MODELS_DIR, rec)):
            params["Rec.model_path"] = os.path.join(MODELS_DIR, rec)
        _rapid = RapidOCR(params=params)
    return _rapid


def rapid_words(image_path):
    tmp_path = None
    try:
        path = _prepare_image(image_path)
        if path != image_path:
            tmp_path = path
        with _rapid_lock:
            r = _get_rapid()(path)
        words = []
        if r is not None and r.boxes is not None:
            for box, txt in zip(r.boxes, r.txts):
                pts = np.asarray(box, dtype=np.float64)
                if txt and txt.strip():
                    words.append({'text': txt.strip(), 'x': float(pts[:, 0].mean()), 'y': float(pts[:, 1].mean())})
        return words
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        _release_ocr_memory()


def _release_ocr_memory():
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
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
    """Computer-screenshot mode: Tesseract if installed (original behavior),
    otherwise the free PaddleOCR-det + VietOCR hybrid."""
    if OCR_COMPUTER_ENGINE == 'rapid' or (OCR_COMPUTER_ENGINE == 'auto' and OCR_HANDWRITING_ENGINE == 'rapid'):
        return rapid_words(image_path)
    if OCR_COMPUTER_ENGINE in ('auto', 'tesseract') and _tesseract_is_available():
        return tesseract_words(image_path)
    if _vietocr_is_available():
        return hybrid_words(image_path)
    return vietocr_words(image_path)


def handwriting_words(image_path):
    """Handwritten mode: Vietnamese OCR (PaddleOCR lang='vi' by default).

    Returns (word_list, engine_name). Falls back to Tesseract vie+eng if the
    Vietnamese engine is not available/installed, so the app never crashes.
    """
    engine = OCR_HANDWRITING_ENGINE
    if engine == 'rapid' and _rapid_is_available():
        return rapid_words(image_path), 'rapidocr-onnx'
    if engine == 'google' and _google_is_available():
        try:
            return google_words(image_path), 'google'
        except Exception as e:
            print(f"[OCR] Google Vision failed ({e}) -> falling back")
            engine = 'paddle'

    if engine == 'vietocr' and _vietocr_is_available():
        try:
            return hybrid_words(image_path), 'paddle-det+vietocr'
        except Exception as e:
            print(f"[OCR] VietOCR hybrid failed ({e}) -> falling back to PaddleOCR")
            engine = 'paddle'
    elif engine == 'vietocr':
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
            if _vietocr_is_available():
                _get_hybrid()
                print("[warmup] VietOCR hybrid ready")
        except Exception as e:
            print(f"[warmup] PaddleOCR unavailable: {e}")
    print("[warmup] done")
