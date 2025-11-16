"""通用编码检测和解码工具

提供智能编码检测和多编码回退机制，适用于 SSH、SFTP、Terminal 等场景。
支持混合编码场景：系统 UTF-8 但文件可能是 GBK。
"""

import logging
import re
from typing import Tuple, Optional, Dict, List

logger = logging.getLogger(__name__)

# 中文环境常见编码优先级列表（按使用频率排序）
_ENCODING_CANDIDATES = ['utf-8', 'gb18030', 'gbk', 'gb2312', 'big5', 'shift_jis', 'latin-1']

# 编码缓存：避免重复检测
_encoding_cache: Dict[str, str] = {}


def _detect_encoding_by_bom(data: bytes) -> Optional[str]:
    """通过 BOM (Byte Order Mark) 检测编码"""
    if data.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    elif data.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif data.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    return None


def _has_chinese_chars(text: str) -> bool:
    """检查文本中是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def _calculate_confidence(text: str, encoding: str) -> float:
    """计算编码的置信度（基于替换字符数量和中文特征）
    
    Returns:
        0.0-1.0 之间的置信度分数
    """
    if not text:
        return 0.0
    
    text_len = len(text)
    if text_len == 0:
        return 0.0
    
    # 计算替换字符比例（越少越好）
    replacement_ratio = text.count('\ufffd') / text_len
    if replacement_ratio > 0.1:  # 超过 10% 是替换字符，基本认为失败
        return 0.0
    
    confidence = 1.0 - replacement_ratio
    
    # 如果包含中文字符，检查中文标点的完整性
    if _has_chinese_chars(text):
        chinese_punctuations = ['，', '。', '；', '：', '！', '？', '、', '《', '》', '"', '"']
        has_chinese_punct = any(p in text for p in chinese_punctuations)
        if has_chinese_punct:
            confidence += 0.1
        
        # GBK/GB18030 在中文环境中常见，加分
        if encoding.lower() in ['gbk', 'gb18030', 'gb2312']:
            confidence += 0.05
    
    return min(confidence, 1.0)


def _try_decode_with_confidence(data: bytes, encoding: str) -> Tuple[Optional[str], float]:
    """尝试使用指定编码解码，并返回置信度"""
    try:
        text = data.decode(encoding)
        confidence = _calculate_confidence(text, encoding)
        return text, confidence
    except (UnicodeDecodeError, LookupError):
        return None, 0.0


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
    fallback_encodings: Optional[List[str]] = None,
    enable_auto_detect: bool = True
) -> Tuple[str, str]:
    """智能解码字节数据（增强版）
    
    优先使用 preferred_encoding，失败后尝试 fallback_encodings，
    并根据置信度选择最佳编码。支持混合编码环境。
    
    Args:
        data: 要解码的字节数据
        preferred_encoding: 首选编码（例如从 locale 检测到的系统编码）
        fallback_encodings: 备选编码列表，默认使用常见中文编码
        enable_auto_detect: 是否启用自动编码检测（基于置信度）
        
    Returns:
        (解码后的文本, 实际使用的编码)
        
    Examples:
        >>> # UTF-8 文件
        >>> text, enc = smart_decode(b'\\xe4\\xb8\\xad\\xe6\\x96\\x87')
        >>> print(text, enc)
        中文 utf-8
        
        >>> # GBK 文件（即使系统是 UTF-8）
        >>> text, enc = smart_decode(b'\\xd6\\xd0\\xce\\xc4', preferred_encoding='utf-8')
        >>> print(text, enc)
        中文 gbk
    """
    if not data:
        return '', preferred_encoding or 'utf-8'
    
    # 1. 检查 BOM
    bom_encoding = _detect_encoding_by_bom(data)
    if bom_encoding:
        try:
            text = data.decode(bom_encoding)
            logger.debug(f"通过 BOM 检测到编码: {bom_encoding}")
            return text, bom_encoding.replace('-sig', '')
        except (UnicodeDecodeError, LookupError):
            pass
    
    # 使用默认备选编码
    if fallback_encodings is None:
        fallback_encodings = _ENCODING_CANDIDATES.copy()
    
    # 2. 如果启用自动检测，尝试所有编码并选择置信度最高的
    if enable_auto_detect:
        best_text = None
        best_encoding = None
        best_confidence = 0.0
        
        # 构建尝试列表（首选编码优先）
        encodings_to_try = []
        if preferred_encoding:
            encodings_to_try.append(preferred_encoding)
        encodings_to_try.extend([e for e in fallback_encodings if e != preferred_encoding])
        
        for encoding in encodings_to_try:
            text, confidence = _try_decode_with_confidence(data, encoding)
            if text is not None and confidence > best_confidence:
                best_text = text
                best_encoding = encoding
                best_confidence = confidence
                
                # 如果置信度很高（>0.9），提前返回
                if confidence > 0.9:
                    logger.debug(f"高置信度编码: {encoding} ({confidence:.2f})")
                    return best_text, best_encoding
        
        # 返回最佳结果
        if best_text is not None and best_confidence > 0.5:
            if best_encoding != preferred_encoding:
                logger.info(f"自动检测文件编码: {best_encoding} (系统: {preferred_encoding}, 置信度: {best_confidence:.2f})")
            return best_text, best_encoding
    
    # 3. 回退到原有逻辑：按顺序尝试编码
    # 首先尝试首选编码
    if preferred_encoding:
        try:
            text = data.decode(preferred_encoding)
            # 检查替换符比例（<2% 认为成功）
            if text.count('\ufffd') / max(len(text), 1) < 0.02:
                return text, preferred_encoding
        except (UnicodeDecodeError, LookupError) as e:
            logger.debug(f"首选编码 {preferred_encoding} 解码失败: {e}")
    
    # 尝试备选编码列表
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
    
    # 4. 最终回退：UTF-8 + replace
    logger.warning("所有编码尝试失败，使用 UTF-8 + errors='replace'")
    return data.decode('utf-8', errors='replace'), 'utf-8'


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


__all__ = [
    'EncodingDetector',
    'smart_decode',
    'safe_decode',
]
