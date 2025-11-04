"""通用编码检测和解码工具

提供智能编码检测和多编码回退机制，适用于 SSH、SFTP、Terminal 等场景。
"""

import logging
import re
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)

# 常见编码优先级列表
_ENCODING_CANDIDATES = ['utf-8', 'gb18030', 'gbk', 'big5', 'shift_jis', 'latin-1']

# 编码缓存：避免重复检测
_encoding_cache: Dict[str, str] = {}


class EncodingDetector:
    """编码检测器 - 用于检测和缓存远程系统的默认编码"""
    
    @staticmethod
    def detect_from_locale(locale_output: str) -> str:
        """从 locale 命令输出检测编码
        
        Args:
            locale_output: locale 命令的输出，例如: LC_CTYPE="zh_CN.UTF-8"
            
        Returns:
            检测到的编码名称，默认为 'utf-8'
        """
        if not locale_output:
            return 'utf-8'
        
        output_upper = locale_output.upper()
        
        # 检测 UTF-8
        if 'UTF-8' in output_upper or 'UTF8' in output_upper:
            return 'utf-8'
        # 检测 GBK
        elif 'GBK' in output_upper:
            return 'gbk'
        # 检测 GB18030
        elif 'GB18030' in output_upper:
            return 'gb18030'
        # 检测 GB2312
        elif 'GB2312' in output_upper:
            return 'gb18030'  # GB18030 向下兼容 GB2312
        # 检测 Big5
        elif 'BIG5' in output_upper:
            return 'big5'
        # 检测 Shift_JIS
        elif 'SHIFT' in output_upper or 'SJIS' in output_upper:
            return 'shift_jis'
        # 检测 ISO-8859
        elif 'ISO-8859' in output_upper or 'LATIN' in output_upper:
            return 'latin-1'
        else:
            # 默认 UTF-8
            return 'utf-8'
    
    @staticmethod
    def get_cached_encoding(cache_key: str) -> Optional[str]:
        """获取缓存的编码"""
        return _encoding_cache.get(cache_key)
    
    @staticmethod
    def cache_encoding(cache_key: str, encoding: str):
        """缓存编码"""
        _encoding_cache[cache_key] = encoding
    
    @staticmethod
    def clear_cache(cache_key: Optional[str] = None):
        """清除编码缓存"""
        if cache_key:
            _encoding_cache.pop(cache_key, None)
        else:
            _encoding_cache.clear()


def smart_decode(
    data: bytes,
    preferred_encoding: Optional[str] = None,
    fallback_encodings: Optional[list] = None
) -> Tuple[str, str]:
    """智能解码字节数据
    
    优先使用 preferred_encoding，失败后尝试 fallback_encodings，
    最终使用 utf-8 + errors='replace'
    
    Args:
        data: 要解码的字节数据
        preferred_encoding: 首选编码（例如从 locale 检测到的编码）
        fallback_encodings: 备选编码列表，默认使用常见编码
        
    Returns:
        (解码后的文本, 实际使用的编码)
        
    Examples:
        >>> text, enc = smart_decode(b'\\xe4\\xb8\\xad\\xe6\\x96\\x87')
        >>> print(text, enc)
        中文 utf-8
        
        >>> text, enc = smart_decode(b'\\xd6\\xd0\\xce\\xc4', preferred_encoding='gbk')
        >>> print(text, enc)
        中文 gbk
    """
    if not data:
        return '', preferred_encoding or 'utf-8'
    
    # 使用默认备选编码
    if fallback_encodings is None:
        fallback_encodings = _ENCODING_CANDIDATES
    
    # 1. 首先尝试首选编码
    if preferred_encoding:
        try:
            text = data.decode(preferred_encoding)
            # 检查替换符比例（<2% 认为成功）
            if text.count('\ufffd') / max(len(text), 1) < 0.02:
                return text, preferred_encoding
        except (UnicodeDecodeError, LookupError) as e:
            logger.debug(f"首选编码 {preferred_encoding} 解码失败: {e}")
    
    # 2. 尝试备选编码列表
    for encoding in fallback_encodings:
        if encoding == preferred_encoding:
            continue  # 已经尝试过了
        try:
            text = data.decode(encoding)
            # 检查替换符比例
            if text.count('\ufffd') / max(len(text), 1) < 0.02:
                logger.debug(f"使用备选编码成功: {encoding}")
                return text, encoding
        except (UnicodeDecodeError, LookupError):
            continue
    
    # 3. 最终回退：UTF-8 + replace
    logger.warning("所有编码尝试失败，使用 UTF-8 + errors='replace'")
    return data.decode('utf-8', errors='replace'), 'utf-8'


def decode_with_fallback(
    data: bytes,
    encoding: Optional[str] = None
) -> str:
    """使用指定编码解码，失败时自动回退
    
    这是 smart_decode 的简化版本，只返回文本不返回编码
    
    Args:
        data: 要解码的字节数据
        encoding: 指定的编码，默认 'utf-8'
        
    Returns:
        解码后的文本
    """
    text, _ = smart_decode(data, preferred_encoding=encoding)
    return text


def safe_decode(
    data: bytes,
    encoding: str = 'utf-8',
    errors: str = 'replace'
) -> str:
    """安全解码 - 保证不会抛出异常
    
    Args:
        data: 要解码的字节数据
        encoding: 编码格式
        errors: 错误处理方式 ('replace', 'ignore', 'strict')
        
    Returns:
        解码后的文本
    """
    if not data:
        return ''
    try:
        return data.decode(encoding, errors=errors)
    except (UnicodeDecodeError, LookupError):
        return data.decode('utf-8', errors='replace')


# 向后兼容的别名
def decode_bytes(data: bytes) -> str:
    """简单解码函数（向后兼容）
    
    Args:
        data: 要解码的字节数据
        
    Returns:
        解码后的文本
    """
    return decode_with_fallback(data)


def ensure_utf8(text: str) -> str:
    """确保文本是有效的 UTF-8（向后兼容，已废弃）
    
    Args:
        text: 输入文本
        
    Returns:
        UTF-8 文本
    """
    # 这个函数的逻辑有问题，保留只是为了向后兼容
    # 新代码应该使用 smart_decode
    return text


__all__ = [
    'EncodingDetector',
    'smart_decode',
    'decode_with_fallback',
    'safe_decode',
    'decode_bytes',  # 向后兼容
    'ensure_utf8',   # 向后兼容
]
