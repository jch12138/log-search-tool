# 配置文件说明

## settings.ini - 应用配置文件

### 配置文件位置

应用会按以下顺序查找配置文件：

1. **环境变量指定** - `SETTINGS_FILE=/path/to/settings.ini`
2. **当前工作目录** - `./settings.ini`
3. **可执行文件目录** - `<exe_dir>/settings.ini`（打包后）

### 配置优先级

```
环境变量 > settings.ini > 代码默认值
```

### 快速开始

1. **复制配置文件模板**
   ```bash
   cp settings.ini settings.ini.backup  # 备份
   ```

2. **修改配置**
   - 直接编辑 `settings.ini` 文件
   - 修改后重启应用生效

3. **使用环境变量覆盖**（可选）
   ```bash
   export APP_PORT=9000
   export APP_DEBUG=true
   python run.py
   ```

### 配置项说明

#### [server] - 服务器配置
- `host` - 绑定地址（默认：0.0.0.0）
- `port` - 端口号（默认：8000）
- `debug` - 调试模式（默认：false）

#### [api] - API 配置
- `api_prefix` - API 路径前缀（默认：/api/v1）
- `max_content_length` - 请求体最大大小，字节（默认：16777216）

#### [log] - 日志配置
- `log_level` - 日志级别：DEBUG/INFO/WARNING/ERROR（默认：INFO）
- `log_dir` - 日志目录（默认：logs）
- `log_file` - 日志文件名（默认：app.log）
- `log_backup_count` - 保留天数（默认：7）
- `use_watched_log` - 多进程模式（默认：false）

#### [business] - 业务配置
- `config_file_path` - 业务日志配置文件（默认：./config.yaml）

#### [ssh] - SSH 配置
- `ssh_timeout` - 连接超时，秒（默认：30）
- `ssh_retry_attempts` - 重试次数（默认：3）

#### [search] - 搜索配置
- `max_search_results` - 最大结果行数（默认：10000）
- `search_timeout` - 搜索超时，秒（默认：30）

#### [terminal] - 终端配置
- `terminal_idle_timeout` - 空闲超时，秒（默认：1800）
- `terminal_idle_check_interval` - 检查间隔，秒（默认：30）

#### [cache] - 缓存配置
- `cache_ttl` - 缓存有效期，秒（默认：300）

### 打包后使用

打包后的可执行文件会自动在以下位置查找 `settings.ini`：

```
log-search-api-onedir/
├── log-search-api.exe (或 log-search-api)
├── settings.ini     ← 配置文件（自动复制到此处）
├── config.yaml      ← 业务日志配置（自动复制到此处）
├── start.bat        ← 启动脚本
└── _internal/       ← 应用内部文件
```

**打包时自动包含**：
- GitHub Actions 和本地打包脚本会自动将 `settings.ini` 和 `config.yaml` 复制到打包目录根目录
- 用户可以直接修改这两个文件来调整配置，无需重新打包

**修改配置**：
1. 找到解压后的 `settings.ini` 文件
2. 用文本编辑器打开并修改
3. 保存后重启应用即可生效

### 注意事项

1. **布尔值** - 使用 `true/false`（不区分大小写）
2. **数字** - 直接写数字，不要加引号
3. **字符串** - 可加可不加引号
4. **注释** - 使用 `#` 开头
5. **编码** - 文件必须是 UTF-8 编码

### 故障排查

**问题：修改配置不生效**
- 检查配置文件路径是否正确
- 确认已重启应用
- 检查是否有环境变量覆盖

**问题：配置文件读取失败**
- 检查文件编码是否为 UTF-8
- 检查语法是否正确（INI 格式）
- 查看应用日志获取详细错误信息
