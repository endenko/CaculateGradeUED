# -*- coding: utf-8 -*-
"""Shared Vietnamese text helpers."""
import re

_ACCENT_MAP = [
    (r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a'),
    (r'[ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴ]', 'A'),
    (r'[èéẹẻẽêềếệểễ]', 'e'),
    (r'[ÈÉẸẺẼÊỀẾỆỂỄ]', 'E'),
    (r'[òóọỏõôồốộổỗơờớợởỡ]', 'o'),
    (r'[ÒÓỌỎÕÔỒỐỘỔƠỜỚỢỞỠ]', 'O'),
    (r'[ìíịỉĩ]', 'i'),
    (r'[ÌÍỊỈĨ]', 'I'),
    (r'[ùúụủũưừứựửữ]', 'u'),
    (r'[ÙÚỤỦŨƯỪỨỰỬỮ]', 'U'),
    (r'[ỳýỵỷỹ]', 'y'),
    (r'[ỲÝỴỶỸ]', 'Y'),
    (r'[đ]', 'd'),
    (r'[Đ]', 'D'),
]


def no_accent_vietnamese(s):
    """Strip Vietnamese diacritics (same behavior as the original SQL Server collation)."""
    s = str(s)
    for pattern, repl in _ACCENT_MAP:
        s = re.sub(pattern, repl, s)
    return s


import unicodedata


def normalize(s):
    """Diacritic-insensitive, lowercase, punctuation-light key for fuzzy matching.
    Unicode NFD strip (handles composed + decomposed input) and đ->d."""
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.replace('đ', 'd').replace('Đ', 'D').lower()
    s = re.sub(r'www\.\S+', ' ', s)
    s = re.sub(r'[^\w\s\+#]', ' ', s)
    s = s.replace('_', ' ')
    return re.sub(r'\s+', ' ', s).strip()
