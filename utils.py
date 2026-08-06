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
