# -*- coding: utf-8 -*-
"""Bảng tin công khai từ ued.udn.vn (WordPress REST), có cache.

Không có trang quản trị, không bài đăng tay. Facebook không được kéo bài
(trang trả về ứng dụng cần đăng nhập / Graph API cần token) — giao diện chỉ
nhúng plugin Page chính thức.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.request

WP_POSTS = "https://ued.udn.vn/wp-json/wp/v2/posts"
FB_PAGE = "https://www.facebook.com/ueddn"
CACHE_PATH = os.environ.get("NEWS_CACHE_PATH", "/tmp/ued-news-cache.json")
TTL_SECONDS = int(os.environ.get("NEWS_CACHE_TTL", "1800"))
PER_PAGE = 12

_BLOCK = re.compile(r"</?(?:p|div|br|li|h[1-6]|tr|td|ul|ol)[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_DATE_NUM = re.compile(r"\b(\d{1,2})[\/.\-](\d{1,2})[\/.\-](20\d{2})\b")
_DATE_TEXT = re.compile(
    r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(20\d{2})",
    re.IGNORECASE,
)
_EVENT_HINT = re.compile(
    r"hạn\s|hạn$|đăng ký|đăng kí|hết hạn|nộp hồ sơ|nộp lệ|đợt thi|ngày thi|thời gian thi|lệ phí",
    re.IGNORECASE,
)

# Thứ tự ưu tiên: mục cụ thể trước, Học tập sau, Khác cuối.
_CATEGORIES = (
    ("thac_si", "Thạc sĩ / Sau đại học", ("thạc sĩ", "sau đại học", "cao học", "nghiên cứu sinh", "tiến sĩ", "ncs")),
    ("tieng_anh", "Tiếng Anh", ("tiếng anh", "anh văn", "vstep", "ielts", "toeic", "ngoại ngữ")),
    ("quoc_phong", "Quốc phòng", ("quốc phòng", "gdqp", "giáo dục quốc phòng", "an ninh")),
    ("hoc_bong", "Học bổng", ("học bổng",)),
    ("hoc_tap", "Học tập / Đào tạo", (
        "đào tạo", "học phần", "tín chỉ", "thời khóa biểu", "thời khoá biểu",
        "đăng ký học", "xét tốt nghiệp", "cảnh báo", "sinh viên", "học kỳ", "học kì",
    )),
)


def categorize(text: str) -> tuple[str, str]:
    hay = _fold(text)
    for key, label, words in _CATEGORIES:
        if any(_fold(w) in hay for w in words):
            return key, label
    return "khac", "Khác"


def extract_dates(text: str, title: str, url: str, post_date: str = "") -> list[dict]:
    """Chỉ lấy ngày đứng cạnh hạn / đăng ký / lịch thi, và không lệch quá xa ngày đăng."""
    events = []
    seen = set()
    plain = text or ""
    try:
        post_year = int((post_date or "0000")[:4])
    except ValueError:
        post_year = 0
    for rx in (_DATE_NUM, _DATE_TEXT):
        for m in rx.finditer(plain):
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if not (1 <= day <= 31 and 1 <= month <= 12):
                continue
            if post_year and (year < post_year - 1 or year > post_year + 1):
                continue
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            start = max(0, m.start() - 80)
            end = min(len(plain), m.end() + 80)
            snippet = _SPACE.sub(" ", plain[start:end]).strip()
            if not _EVENT_HINT.search(snippet):
                continue
            sig = (iso, url)
            if sig in seen:
                continue
            seen.add(sig)
            events.append({
                "date": iso,
                "kind": "han",
                "label": "Hạn / lịch thi",
                "snippet": snippet[:180],
                "title": title,
                "url": url,
            })
    events.sort(key=lambda e: e["date"])
    return events


def build_board(posts: list[dict]) -> dict:
    items = []
    calendar = []
    for post in posts:
        title = _clean(post.get("title") or "")
        if len(title) < 2:
            continue
        raw = post.get("content") or post.get("excerpt") or ""
        text = _clean(raw)
        link = post.get("link") or ""
        posted = (post.get("date") or "")[:10]
        key, label = categorize(f"{title}\n{text}")
        excerpt = text[:320]
        item = {
            "id": post.get("id"),
            "date": posted,
            "title": title,
            "url": link,
            "excerpt": excerpt,
            "category": key,
            "category_label": label,
        }
        items.append(item)
        calendar.extend(extract_dates(text, title, link, posted))
    calendar.sort(key=lambda e: (e["date"], e["title"]))
    return {"posts": items, "calendar": calendar}


def get_board(now: float | None = None, fetcher=None) -> dict:
    now = time.time() if now is None else now
    cached = _read_cache()
    if cached and now - cached.get("fetched_at_epoch", 0) < TTL_SECONDS:
        cached["cache"] = "fresh"
        return cached
    fetch = fetcher or _fetch_wp
    try:
        posts = fetch()
        board = build_board(posts)
        payload = {
            "posts": board["posts"],
            "calendar": board["calendar"],
            "fetched_at_epoch": now,
            "source": WP_POSTS,
            "facebook": {
                "page": FB_PAGE,
                "fetched": False,
                "reason": "Trang Facebook công khai không trả bài viết đọc được khi chưa đăng nhập; Graph API cần token. Chỉ nhúng plugin Page.",
            },
            "stale": False,
            "error": None,
        }
        _write_cache(payload)
        payload["cache"] = "miss"
        return payload
    except Exception as exc:  # noqa: BLE001 — trả cache cũ nếu mạng lỗi
        if cached:
            cached["cache"] = "stale"
            cached["stale"] = True
            cached["error"] = str(exc)
            return cached
        return {
            "posts": [],
            "calendar": [],
            "fetched_at_epoch": now,
            "source": WP_POSTS,
            "facebook": {"page": FB_PAGE, "fetched": False, "reason": "Chưa nhúng được bài Facebook."},
            "stale": False,
            "cache": "error",
            "error": str(exc),
        }


# Chuyên mục thông báo trên ued.udn.vn (không phải bài sự kiện chung).
_NOTICE_CATEGORIES = (
    (85, 10),  # Thông báo Đào tạo
    (84, 10),  # Thông báo dành cho người học
    (83, 6),   # Lịch thi - phúc khảo
    (26, 4),   # Lịch tuần
    (29, 5),   # Chế độ chính sách - người học
)


def _fetch_wp() -> list[dict]:
    """Bài mới trên trang chủ cộng thông báo đào tạo / lịch thi, để mục Tiếng Anh không bị bài sự kiện đẩy mất."""
    seen = set()
    posts = []

    def add(chunk):
        if not isinstance(chunk, list):
            return
        for post in chunk:
            pid = post.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            posts.append(post)

    chunk = _wp_get({"per_page": PER_PAGE, "page": 1})
    add(chunk)
    for cat, size in _NOTICE_CATEGORIES:
        try:
            add(_wp_get({"categories": cat, "per_page": size}))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            continue
    posts.sort(key=lambda p: p.get("date") or "", reverse=True)
    return posts


def _wp_get(params: dict) -> list:
    from urllib.parse import urlencode
    query = {"_fields": "id,date,link,title,excerpt,content", **params}
    url = WP_POSTS + "?" + urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": "UEDCalculateGrade/1.0 (public bulletin; +https://ued.udn.vn/)"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean(value) -> str:
    if isinstance(value, dict):
        value = value.get("rendered") or ""
    text = html.unescape(str(value))
    text = _BLOCK.sub(" ", text)
    text = _TAG.sub("", text)
    return _SPACE.sub(" ", text).strip()


def _fold(text: str) -> str:
    # So khớp không dấu đơn giản, đủ cho từ khóa tiếng Việt đã liệt kê.
    mapping = str.maketrans(
        "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ",
        "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
    )
    return text.lower().translate(mapping)


def _read_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(payload: dict) -> None:
    try:
        parent = os.path.dirname(CACHE_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)
    except OSError:
        pass
