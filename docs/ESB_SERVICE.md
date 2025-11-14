# ESB Service 使用文档

## 概述

ESB (Enterprise Service Bus) 服务用于通过 XML 协议与企业服务总线进行通信。

## 项目结构

```
app/services/esb/
├── __init__.py      # 模块导出
└── service.py       # ESB 服务实现

app/api/routes/
└── esb.py           # ESB API 路由
```

## 核心组件

### 1. EsbService 类

主要方法：
- `send_xml(xml_str: str) -> str`: 发送原始 XML 字符串
- `send(magic_num: str, service_code: str, head: dict, body: dict) -> (bool, dict)`: 发送结构化请求
- `dict_to_xml_body(d: dict) -> str`: 字典转 XML

### 2. 服务代码常量 (SERVICE)

预定义的服务代码映射：
```python
SERVICE = {
    "BALANCE_QUERY": "cb186Y",      # 余额查询
    "IDENTIFY_QUERY": "cb186J",     # 身份查询
    "BANK_BY_ACCOUNT": "cb182Z",    # 账户银行查询
    "PAY_INNER": "1866",            # 内部支付
    "PAY_BATCH": "1866-BATCH",      # 批量支付
    "CHECK_ACCT_EXISTS": "bp186B",  # 检查账户存在
}
```

### 3. 环境配置

支持多环境切换：
- **sita**: SIT-A 环境 (12.99.223.102:39030)
- **sitb**: SIT-B 环境 (12.99.223.101:39030)
- **uat**: UAT 环境 (app.esb.nb:39030)
- **default**: 使用 Flask 配置中的 `ESB_HOST`, `ESB_PORT`, `ESB_TIMEOUT`

## API 端点

### 1. 发送 ESB 请求
**POST** `/api/v1/esb/send`

请求示例：
```json
{
  "magic_num": "ESB00001",
  "service_code": "BALANCE_QUERY",
  "head": {
    "user_id": "admin",
    "timestamp": "20250115120000"
  },
  "body": {
    "account": "123456789",
    "query_type": "balance"
  },
  "env": "sita"
}
```

响应示例：
```json
{
  "success": true,
  "response": {
    "service": {
      "SYS_HEAD": {...},
      "BODY": {...}
    }
  }
}
```

### 2. 获取服务列表
**GET** `/api/v1/esb/services`

响应示例：
```json
{
  "services": {
    "BALANCE_QUERY": "cb186Y",
    "IDENTIFY_QUERY": "cb186J",
    ...
  }
}
```

### 3. 测试连接
**POST** `/api/v1/esb/test`

请求示例：
```json
{
  "env": "sita"
}
```

响应示例：
```json
{
  "success": true,
  "host": "12.99.223.102",
  "port": 39030,
  "timeout": 30
}
```

## 代码使用示例

### 在 Python 代码中使用

```python
from app.services import EsbService, get_esb, SERVICE

# 方式 1: 直接创建实例
esb = EsbService(host="12.99.223.102", port=39030, timeout=30)

# 方式 2: 使用 get_esb() 工厂函数（推荐）
# 会根据请求上下文中的 env 参数自动选择环境
esb = get_esb()

# 发送请求
success, response = esb.send(
    magic_num="ESB00001",
    service_code=SERVICE["BALANCE_QUERY"],
    head={"user_id": "admin"},
    body={"account": "123456789"}
)

if success:
    print(response)
```

### 在 API 路由中使用

```python
from flask import Blueprint, request, jsonify
from app.services import get_esb, SERVICE

bp = Blueprint('my_api', __name__)

@bp.route('/query', methods=['POST'])
def query_balance():
    data = request.get_json()
    
    # get_esb() 会自动读取请求中的 env 参数
    esb = get_esb()
    
    success, response = esb.send(
        magic_num="ESB00001",
        service_code=SERVICE["BALANCE_QUERY"],
        head={"user_id": "admin"},
        body={"account": data.get("account")}
    )
    
    return jsonify({
        "success": success,
        "data": response
    })
```

## 配置说明

在 Flask 配置文件或 `settings.ini` 中添加：

```ini
[esb]
ESB_HOST = localhost
ESB_PORT = 39030
ESB_TIMEOUT = 30
```

## 日志

ESB 服务会自动记录所有请求和响应：
- 发送请求时: `[ESB SEND] (host:port) service_code\nXML内容`
- 接收响应时: `[ESB RECV] (host:port) service_code\nXML内容`

日志级别为 INFO，可在 Flask 日志配置中调整。

## 依赖

- `xmltodict==0.13.0`: XML 与字典转换
- `Flask`: Web 框架（已包含在项目中）

## 注意事项

1. **环境选择**: 请求中的 `env` 参数会覆盖配置文件中的默认 ESB 地址
2. **超时设置**: 默认 30 秒，可根据实际网络情况调整
3. **XML 格式**: ESB 协议要求前 8 个字符为 magic_num，响应解析时会自动跳过
4. **嵌套数据**: `dict_to_xml_body` 支持嵌套字典和列表的转换
5. **错误处理**: 所有 ESB 操作都应包裹在 try-except 中处理网络异常

## 测试

```python
# 测试环境连接
import requests

response = requests.post('http://localhost:5000/api/v1/esb/test', json={
    "env": "sita"
})
print(response.json())

# 测试发送请求
response = requests.post('http://localhost:5000/api/v1/esb/send', json={
    "service_code": "BALANCE_QUERY",
    "head": {"user_id": "test"},
    "body": {"account": "123456"},
    "env": "sita"
})
print(response.json())
```
