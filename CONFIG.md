# 日志配置说明

由于安全考虑，Web配置页面已被隐藏。请通过以下方式进行配置：

## 配置文件位置

默认配置文件路径：`~/.log_search_app/config.yaml`

可通过环境变量 `CONFIG_FILE_PATH` 指定其他路径。

## 配置文件格式

```yaml
# 日志配置
logs:
  - name: "Web服务器日志"
    path: "/var/log/nginx/access.log"
    group: "生产环境"
    description: "Nginx访问日志"
    sshs:
      - host: "192.168.1.100"
        port: 22
        username: "admin"
        password: "your_password"

  - name: "应用日志"
    path: "/app/logs/app-{YYYY}-{MM}-{DD}.log"
    group: "生产环境"
    description: "应用程序日志，支持日期变量"
    sshs:
      - host: "192.168.1.101"
        port: 22
        username: "appuser"
        password: "your_password"

# 系统设置
settings:
  search_mode: "keyword"
  context_span: 10
  max_results: 1000
```

## 日期变量支持

路径中支持以下日期变量：
- `{YYYY}` - 四位年份 (2023)
- `{MM}` - 两位月份 (01-12)
- `{DD}` - 两位日期 (01-31)
- `{N}` - 序号 (1, 2, 3...)

示例：
- `/var/log/app-{YYYY}-{MM}-{DD}.log` → `/var/log/app-2023-09-09.log`
- `/logs/app-{YYYY}-{MM}-{DD}-{N}.log` → `/logs/app-2023-09-09-1.log`

## 分组功能

- 使用 `group` 字段对日志进行分组
- 同一组的日志会在界面中归类显示
- 支持不同组有同名的日志配置

## 重新加载配置

修改配置文件后，重启应用即可生效。

## API接口

配置相关的API接口仍然可用：

- `GET /api/v1/config` - 获取配置（密码已脱敏）
- `PUT /api/v1/config` - 更新配置（需要完整配置）
- `GET /api/v1/logs` - 获取日志列表

这些接口主要供程序内部使用。
