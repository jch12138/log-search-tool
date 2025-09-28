"""统一编码处理工具 (migrated & extended)

提供:
 - decode_bytes: 简单 UTF-8 -> GB2312 回退
 - smart_decode: 多编码尝试 + 替换符比例启发式
 - ensure_utf8: 替换符过多时的再尝试
"""

from typing import Tuple, Optional, List

_BASIC_FALLBACK = ['utf-8', 'gb2312']
_SMART_CANDIDATES = ['utf-8', 'gb18030', 'gbk', 'big5', 'shift_jis', 'latin-1']


def decode_bytes(data: bytes) -> str:
    if not data:
        return ''
    for enc in _BASIC_FALLBACK:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode('utf-8', errors='replace')


def smart_decode(data: bytes, last_good: Optional[str] = None, forced: Optional[str] = None) -> Tuple[str, str]:
    """多编码探测: forced > last_good > candidates; 返回 (文本, 采用编码)。"""
    if not data:
        return '', (forced or last_good or 'utf-8')
    # forced 覆盖
    if forced:
        try:
            return data.decode(forced, errors='replace'), forced
        except Exception:
            pass
    # last_good
    if last_good:
        try:
            t = data.decode(last_good)
            if t.count('\ufffd') / max(len(t), 1) < 0.02:
                return t, last_good
        except Exception:
            pass
    # candidates
    for enc in _SMART_CANDIDATES:
        if enc == last_good:
            continue
        try:
            t = data.decode(enc)
            if t.count('\ufffd') / max(len(t), 1) < 0.02:
                return t, enc
        except Exception:
            continue
    # fallback
    return data.decode('utf-8', errors='replace'), 'utf-8'


def ensure_utf8(text: str) -> str:
    if not text:
        return text
    replacement_count = text.count('\ufffd')
    if replacement_count and replacement_count * 5 > len(text):
        try:
            raw = text.encode('latin-1', errors='ignore')
            return decode_bytes(raw)
        except Exception:
            return text
    return text

__all__ = ['decode_bytes', 'smart_decode', 'ensure_utf8']
