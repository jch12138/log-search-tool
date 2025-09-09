"""统一编码处理工具 (migrated)

仅支持 UTF-8 和 GB2312 两种编码自动识别/回退。
"""

def decode_bytes(data: bytes) -> str:
    """尝试以 UTF-8 解码，失败则回退 GB2312，再失败使用替换策略。"""
    if not data:
        return ''
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return data.decode('gb2312')
        except UnicodeDecodeError:
            return data.decode('utf-8', errors='replace')

def ensure_utf8(text: str) -> str:
    """粗略校正含大量替换符号的文本。"""
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

__all__ = ['decode_bytes', 'ensure_utf8']
