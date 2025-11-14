# Account API 使用文档

## 概述

Account API 提供账户查询和交易明细查询功能，通过 ESB 服务与核心银行系统对接。

## API 端点

### 1. 余额查询
**POST** `/api/v1/account/balance-query`

查询账户余额信息。

#### 请求参数
```json
{
  "account": "6228481234567890",  // 必填：账号
  "env": "sita"                   // 可选：环境 (sita/sitb/uat)
}
```

#### 响应示例
```json
{
  "success": true,
  "data": {
    "service": {
      "SYS_HEAD": {
        "ServiceCode": "12003000085",
        "RetCode": "0000",
        "RetMsg": "交易成功"
      },
      "BODY": {
        "array": {
          "BtchAcctInfQuryArray": {
            "CstAcctNo": "6228481234567890",
            "AcctBal": "100000.00",
            "AvlBal": "100000.00",
            "FrzAmt": "0.00"
          }
        }
      }
    }
  }
}
```

#### ESB 服务信息
- **Service Code**: bp186L
- **Transaction Code**: 12003000085
- **Scene**: 68

### 2. 交易明细查询
**POST** `/api/v1/account/query-detail`

查询账户交易明细，支持分页和日期范围。

#### 请求参数
```json
{
  "account": "6228481234567890",     // 必填：账号
  "begTms": 0,                       // 可选：开始条数，默认 0
  "quryTms": 20,                     // 可选：查询条数，默认 20
  "beginDate": "2025-01-01",         // 可选：开始日期 (YYYY-MM-DD)
  "endDate": "2025-01-31",           // 可选：结束日期 (YYYY-MM-DD)
  "env": "sita"                      // 可选：环境 (sita/sitb/uat)
}
```

#### 响应示例
```json
{
  "success": true,
  "data": {
    "service": {
      "SYS_HEAD": {
        "ServiceCode": "12002000011",
        "RetCode": "0000",
        "RetMsg": "交易成功"
      },
      "BODY": {
        "TtlTms": "50",
        "array": {
          "AcctTxnDtlQuryArray": [
            {
              "TxnDt": "2025-01-15",
              "TxnTm": "14:30:00",
              "TxnAmt": "1000.00",
              "TxnTyp": "转账",
              "OppAcctNo": "6228489876543210",
              "Rmk": "工资"
            }
          ]
        }
      }
    }
  }
}
```

#### ESB 服务信息
- **Service Code**: cb186Y
- **Transaction Code**: 12002000011
- **Scene**: 29

## 代码使用示例

### Python 示例

```python
import requests

# 余额查询
response = requests.post('http://localhost:5000/api/v1/account/balance-query', json={
    "account": "6228481234567890",
    "env": "sita"
})
print(response.json())

# 交易明细查询
response = requests.post('http://localhost:5000/api/v1/account/query-detail', json={
    "account": "6228481234567890",
    "begTms": 0,
    "quryTms": 20,
    "beginDate": "2025-01-01",
    "endDate": "2025-01-31",
    "env": "sita"
})
print(response.json())
```

### JavaScript 示例

```javascript
// 余额查询
fetch('/api/v1/account/balance-query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    account: '6228481234567890',
    env: 'sita'
  })
})
.then(res => res.json())
.then(data => console.log(data));

// 交易明细查询
fetch('/api/v1/account/query-detail', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    account: '6228481234567890',
    begTms: 0,
    quryTms: 20,
    beginDate: '2025-01-01',
    endDate: '2025-01-31',
    env: 'sita'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

### cURL 示例

```bash
# 余额查询
curl -X POST http://localhost:5000/api/v1/account/balance-query \
  -H "Content-Type: application/json" \
  -d '{
    "account": "6228481234567890",
    "env": "sita"
  }'

# 交易明细查询
curl -X POST http://localhost:5000/api/v1/account/query-detail \
  -H "Content-Type: application/json" \
  -d '{
    "account": "6228481234567890",
    "begTms": 0,
    "quryTms": 20,
    "beginDate": "2025-01-01",
    "endDate": "2025-01-31",
    "env": "sita"
  }'
```

## 环境配置

支持以下环境：

| 环境代码 | 环境名称 | ESB 地址 | 端口 |
|---------|---------|---------|------|
| sita    | SIT-A   | 12.99.223.102 | 39030 |
| sitb    | SIT-B   | 12.99.223.101 | 39030 |
| uat     | UAT     | app.esb.nb | 39030 |
| default | 默认    | 配置文件 | 配置文件 |

在请求中通过 `env` 参数指定环境，不指定则使用配置文件中的默认环境。

## 技术细节

### 请求构造

每个 ESB 请求都包含：
- **TraceId**: 追踪 ID (UUID hex)
- **SpanId**: 跨度 ID (UUID hex)
- **ConsumerSeqNo**: 消费者序列号 (UUID hex)
- **CnsmrTxnDt**: 消费者交易日期 (YYYY-MM-DD)
- **CnsmrTxnTm**: 消费者交易时间 (HH:MM:SS)

### 固定参数

- **CnlCd**: TG (渠道代码)
- **TxnInstCd**: 07097 (交易机构代码)
- **TxnTlr**: 1101WY (交易柜员)
- **ConsumerId**: TG (消费者 ID)
- **OrgConsumerId**: TG (原始消费者 ID)

## 错误处理

所有 API 在发生错误时返回 500 状态码和错误信息：

```json
{
  "error": "错误描述信息"
}
```

常见错误：
- **连接超时**: ESB 服务器连接超时
- **解析错误**: XML 响应解析失败
- **业务错误**: ESB 返回业务错误码

## 日志记录

所有 ESB 请求和响应都会自动记录日志：
- 请求前: `[ESB SEND] (host:port) service_code`
- 响应后: `[ESB RECV] (host:port) service_code`

可在应用日志中查看完整的 XML 报文。

## 注意事项

1. **账号格式**: 确保账号格式正确，通常为 16-19 位数字
2. **日期格式**: 日期必须使用 `YYYY-MM-DD` 格式
3. **分页查询**: 交易明细查询支持分页，通过 `begTms` 和 `quryTms` 控制
4. **环境选择**: 开发测试时使用 sita/sitb 环境，生产环境使用默认配置
5. **超时设置**: ESB 默认超时 30 秒，可在配置文件中调整

## 安全建议

1. **生产环境**: 建议添加认证中间件（如原代码中的 `@require_whitelist`）
2. **参数验证**: 建议添加输入参数的格式验证
3. **敏感信息**: 日志中注意脱敏处理账号等敏感信息
4. **访问控制**: 限制 API 访问权限，避免未授权访问

## 扩展功能

如需添加白名单验证，可以参考原代码创建 validators 模块：

```python
# app/middleware/validators.py
from functools import wraps
from flask import request, jsonify

def require_whitelist(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 实现白名单验证逻辑
        client_ip = request.remote_addr
        # 检查 IP 是否在白名单中
        # if not is_whitelisted(client_ip):
        #     return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated_function
```

然后在路由中使用：
```python
from app.middleware.validators import require_whitelist

@account_bp.route('/balance-query', methods=['POST'])
@require_whitelist
def balance_query():
    # ...
```
