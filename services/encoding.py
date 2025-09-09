"""统一编码处理工具

仅支持 UTF-8 和 GB2312 两种编码自动识别/回退。
"""

def decode_bytes(data: bytes) -> str:
    """尝试以 UTF-8 解码，失败则回退 GB2312，再失败使用替换策略。
    Args:
        data: 原始字节
    Returns:
        解码后的字符串（最大化保留可读中文）
    """
    if not data:
        return ''
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return data.decode('gb2312')
        except UnicodeDecodeError:
            # 最后兜底：utf-8 替换错误字符
            return data.decode('utf-8', errors='replace')

def ensure_utf8(text: str) -> str:
    """若文本包含大量替换符号，尝试按 GB2312 重新推断。
    当前策略简单：如果出现连续 � 符号超过一定阈值，判定为误解码。
    """
    if not text:
        return text
    replacement_count = text.count('\ufffd')  # '�'
    if replacement_count and replacement_count * 5 > len(text):  # 粗略阈值
        try:
            raw = text.encode('latin-1', errors='ignore')
            return decode_bytes(raw)
        except Exception:
            return text
    return text
