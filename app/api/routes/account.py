"""Account API routes for ESB account and payment operations."""

import socket
import xmltodict
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import uuid
import logging
from xml.parsers.expat import ExpatError

log = logging.getLogger(__name__)

account_bp = Blueprint('account', __name__)


class EsbService:
    """Enterprise Service Bus client for XML-based communication."""
    
    def __init__(self, host, port, timeout=30):
        """Initialize ESB service.
        
        Args:
            host: ESB server hostname or IP address
            port: ESB server port
            timeout: Socket timeout in seconds (default: 30)
        """
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_xml(self, xml_str: str) -> str:
        """Send raw XML string to ESB server and receive response.
        
        Args:
            xml_str: XML string to send
            
        Returns:
            Response XML string from ESB server
        """
        data = xml_str.encode("utf-8")
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(data)
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                block = sock.recv(4096)
                if not block:
                    break
                chunks.append(block)
        return b"".join(chunks).decode("utf-8")

    def send(self, magic_num: str, service_code: str, head: dict, body: dict):
        """Send structured ESB request and receive parsed response.
        
        Args:
            magic_num: Magic number prefix for ESB protocol
            service_code: Service code to invoke
            head: System header dictionary
            body: Request body dictionary
            
        Returns:
            Tuple of (success: bool, response: dict)
        """
        # 构造 XML 报文
        xml = f"""{magic_num}<?xml version="1.0" encoding="UTF-8"?><service><SYS_HEAD>{self.dict_to_xml_body(head)}</SYS_HEAD><APP_HEAD/><LOCAL_HEAD><TranCode>{service_code}</TranCode></LOCAL_HEAD><BODY>{self.dict_to_xml_body(body)}</BODY></service>""".strip()

        # 发送前打印报文（service_code + 目标IP + XML）
        log.info(f"[ESB SEND] ({self.host}:{self.port}) {service_code}\n{xml}\n")

        # 发送
        resp_xml = self.send_xml(xml)

        # 接收后打印报文
        log.info(f"[ESB RECV] ({self.host}:{self.port}) {service_code}\n{resp_xml}\n")

        # 检查响应是否为空或无效
        if not resp_xml or len(resp_xml) <= 8:
            log.error(f"Empty or invalid ESB response. Raw Response: {resp_xml}")
            return False, {"error": "ESB响应为空或无效", "raw_response": resp_xml}

        # 转 dict (跳过前8个字符的magic_num)
        try:
            resp_dict = xmltodict.parse(resp_xml[8:])
        except ExpatError as e:
            log.error(f"Failed to parse ESB response XML. Error: {e}, Raw Response: {resp_xml}")
            return False, {"error": "ESB响应解析失败", "details": f"无法解析返回的XML内容: {e}", "raw_response": resp_xml}
        except Exception as e:
            log.error(f"Unknown error during ESB response parsing. Error: {e}, Raw Response: {resp_xml}")
            return False, {"error": "处理ESB响应时发生未知错误", "details": str(e), "raw_response": resp_xml}

        return True, resp_dict

    def dict_to_xml_body(self, d: dict) -> str:
        """Convert dictionary to XML body string.
        
        Supports nested dictionaries and lists.
        
        Args:
            d: Dictionary to convert
            
        Returns:
            XML string representation
        """
        def to_xml(data):
            if isinstance(data, dict):
                return "".join(f"<{k}>{to_xml(v)}</{k}>" for k, v in data.items())
            elif isinstance(data, list):
                return "".join(f"<item>{to_xml(item)}</item>" for item in data)
            else:
                return "" if data is None else str(data)
    
        return to_xml(d)


def get_esb():
    """Get ESB service instance based on configuration and request context.
    
    Supports environment override via 'env' parameter in request JSON:
    - 'sita': SIT-A environment (12.99.223.102:39030)
    - 'sitb': SIT-B environment (12.99.223.101:39030)
    - 'uat': UAT environment (app.esb.nb:39030)
    - default: Uses Flask config ESB_HOST/ESB_PORT
    
    Returns:
        EsbService instance configured for the requested environment
    """
    cfg = current_app.config

    # 允许请求中带 env 参数指定 ESB 地址
    override = request.get_json(silent=True) or {}
    env = override.get("env", "").replace("-", "")

    if env == 'sita':
        return EsbService(
            "12.99.223.102",
            39030,
            cfg.get("ESB_TIMEOUT", 30)
        )
    if env == 'sitb':
        return EsbService(
            "12.99.223.101",
            39030,
            cfg.get("ESB_TIMEOUT", 30)
        )
    if env == 'uat':
        return EsbService(
            "app.esb.nb",
            39030,
            cfg.get("ESB_TIMEOUT", 30)
        )

    # 默认使用 config 中的 ESB
    return EsbService(
        cfg.get("ESB_HOST", "localhost"),
        cfg.get("ESB_PORT", 39030),
        cfg.get("ESB_TIMEOUT", 30)
    )


@account_bp.route('/balance-query', methods=['POST'])
def balance_query():
    """Query account balance via ESB.
    
    Request JSON:
        {
            "account": "账号",
            "env": "sita"  // Optional: environment override
        }
    
    Returns:
        ESB response with account balance information
    """
    try:
        req = request.get_json(force=True)
        
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex
        
        now = datetime.now()
        tx_date = now.strftime("%Y-%m-%d")
        tx_time = now.strftime("%H:%M:%S")
        
        head = {
            "ServiceCode": "12003000085",
            "ServiceScene": "68",
            "ConsumerId": "TG",
            "OrgConsumerId": "TG",
            "ConsumerSeqNo": uuid.uuid4().hex
        }
        
        body = {
            "TraceId": trace_id,
            "SpanId": span_id,
            "SvcCd": "bp186L",
            "CnlCd": "TG",
            "TxnInstCd": "07097",
            "TxnTlr": "1101WY",
            "CnsmrTxnDt": now.strftime("%Y-%m-%d"),
            "CnsmrTxnTm": "11:32:19",
            "QuryLogtAcctFlg": "N",
            "array": {
                "BtchAcctInfQuryArray": {
                    "CstAcctNo": req.get("account", ""),
                    "SubAcctSeqNo": ""
                }
            }
        }
        
        ok, res = get_esb().send("00000752", "bp186L", head, body)
        
        return jsonify({
            "success": ok,
            "data": res
        })
        
    except Exception as e:
        log.error(f"Balance query failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@account_bp.route('/query-detail', methods=['POST'])
def query_detail():
    """Query account transaction details via ESB.
    
    Request JSON:
        {
            "account": "账号",
            "begTms": 0,           // Optional: 开始条数
            "quryTms": 20,         // Optional: 查询条数
            "beginDate": "2025-01-01",  // Optional: 开始日期
            "endDate": "2025-01-31",    // Optional: 结束日期
            "env": "sita"          // Optional: environment override
        }
    
    Returns:
        ESB response with transaction details
    """
    try:
        req = request.get_json(force=True)
        
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex
        
        now = datetime.now()
        tx_date = now.strftime("%Y-%m-%d")
        tx_time = now.strftime("%H:%M:%S")
        
        head = {
            "ServiceCode": "12002000011",
            "ServiceScene": "29",
            "ConsumerId": "TG",
            "OrgConsumerId": "TG",
            "ConsumerSeqNo": uuid.uuid4().hex
        }
        
        body = {
            "TraceId": trace_id,
            "SpanId": span_id,
            "SvcCd": "cb186Y",
            "CnlCd": "TG",
            "TxnInstCd": "07097",
            "TxnTlr": "1101WY",
            "CnsmrTxnDt": tx_date,
            "CnsmrTxnTm": tx_time,
            
            # 业务查询参数
            "CstAcctNo": req.get("account", ""),
            "SubAcctSeqNo": "",
            "BegTms": req.get("begTms", 0),
            "QuryTms": req.get("quryTms", 20),
            "BegDt": req.get("beginDate", ""),
            "EndDt": req.get("endDate", ""),
        }
        
        ok, res = get_esb().send("00000741", "cb186Y", head, body)
        
        return jsonify({
            "success": ok,
            "data": res
        })
        
    except Exception as e:
        log.error(f"Query detail failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
