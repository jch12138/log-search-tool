# Windows 打包与运行

## 生成产物

GitHub Actions 工作流会生成两个工件：
- log-search-api-onefile.exe：单文件可执行
- log-search-api-onedir.zip：目录形式（包含依赖与资源）

## 运行

- onefile：
  - 双击或在命令行执行 `log-search-api-onefile.exe`
- onedir：
  - 解压 zip 后，进入 `log-search-api` 目录，运行 `log-search-api.exe`

默认监听地址：0.0.0.0:8000（可通过环境变量覆盖，例如 LOG_LEVEL/LOG_DIR 等）。

若访问 UI，打开浏览器访问对应服务器地址，例如：http://127.0.0.1:8000/
