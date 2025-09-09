from app.services.utils.encoding import decode_bytes

def test_decode_utf8():
    assert decode_bytes('中文'.encode('utf-8')) == '中文'

def test_decode_gb2312():
    data = '测试'.encode('gb2312')
    assert decode_bytes(data) == '测试'
