// LogSearchResults 组件
const LogSearchResults = {
    name: 'LogSearchResults',
    
    // 组件依赖加载
    async created() {
        await this.loadDependencies();
        this.injectStyles();
    },
    
    props: {
        // 数据相关参数
        searchResults: {
            type: Object,
            default: () => null
        },
        searchKeyword: {
            type: String,
            default: ''
        },
        useRegex: {
            type: Boolean,
            default: false
        },
        
        // 显示控制参数
        height: {
            type: String,
            default: '400px'
        },
        maxResults: {
            type: Number,
            default: 1000  // 每台主机最多显示1000条结果
        },
        showSearchStats: {
            type: Boolean,
            default: true
        },
        showHostGrouping: {
            type: Boolean,
            default: true
        },
        emptyMessage: {
            type: String,
            default: '暂无搜索结果'
        },
        
        // 高亮配置参数
        enabledHighlighters: {
            type: Object,
            default: () => ({
                logLevels: true,
                timestamps: true,
                network: true,
                xml: true,
                sql: true,
                json: true,
                filePaths: true,
                urls: true,
                emails: true,
                uuids: true
            })
        },
        
        // 性能优化参数
        virtualScroll: {
            type: Boolean,
            default: false
        },
        lazyLoad: {
            type: Boolean,
            default: false
        },
        
        // 样式定制参数
        customClass: {
            type: String,
            default: ''
        },
        fontSize: {
            type: String,
            default: '14px'  // 调整为适中的字体大小
        },
        fontFamily: {
            type: String,
            default: "'Microsoft YaHei', '微软雅黑', 'Fira Code', 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace"  // 微软雅黑 + Fira Code
        },
        lineHeight: {
            type: Number,
            default: 1.4
        },
        theme: {
            type: String,
            default: 'light'
        }
    },
    
    computed: {
        // 按主机分组搜索结果（逻辑保持不变）
        groupedResults() {
            if (!this.searchResults || !this.searchResults.hosts) return [];
            if (!this.showHostGrouping) {
                const allResults = [];
                this.searchResults.hosts.forEach(h => {
                    if (h && h.success && Array.isArray(h.results)) allResults.push(...h.results);
                });
                return [{ host: 'all', results: allResults.slice(0, this.maxResults) }];
            }
            const groups = [];
            this.searchResults.hosts.forEach(hostResult => {
                let hostResults = (hostResult && hostResult.success && Array.isArray(hostResult.results)) ? hostResult.results : [];
                const originalCount = hostResults.length;
                let isTruncated = false;
                if (this.maxResults && hostResults.length > this.maxResults) {
                    hostResults = hostResults.slice(0, this.maxResults);
                    isTruncated = true;
                }
                groups.push({
                    host: hostResult.host,
                    results: hostResults,
                    hostResult: hostResult,
                    originalCount,
                    isTruncated
                });
            });
            return groups;
        }
    },
    
    data() {
        return {
            // 依赖加载状态
            dependenciesLoaded: false
        };
    },
    
    methods: {
        // 动态加载依赖
        async loadDependencies() {
            try {
                // 检查是否已加载 Prism.js (现在从本地加载)
                if (typeof window.Prism === 'undefined') {
                    // 等待一下让本地Prism.js文件加载完成
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                
                // 如果仍然没有加载，说明可能有问题，但继续工作
                if (typeof window.Prism !== 'undefined') {
                    // 设置 Prism 手动模式
                    window.Prism = window.Prism || {};
                    window.Prism.manual = true;
                    
                    // 定义自定义日志语言
                    this.defineLogLanguage();
                    console.log('Prism.js loaded successfully with log language (local version)');
                } else {
                    console.warn('Prism.js not available, syntax highlighting disabled');
                }
                
                this.dependenciesLoaded = true;
            } catch (error) {
                console.warn('Failed to initialize dependencies:', error);
                this.dependenciesLoaded = true; // 即使失败也继续工作
            }
        },
        
        // 定义日志语言语法
        defineLogLanguage() {
            if (!window.Prism) return;
            
            // 定义日志语言的语法规则
            window.Prism.languages.log = {
                // 时间戳 - 最高优先级
                'timestamp': [
                    {
                        // ISO 8601 格式: 2024-09-05T14:30:45.123Z
                        pattern: /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?\b/,
                        alias: 'number'
                    },
                    {
                        // 标准日期时间: 2024-09-05 14:30:45.123
                        pattern: /\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b/,
                        alias: 'number'
                    },
                    {
                        // 月-日 时间格式: 08-07 09:03:57.766
                        pattern: /\b\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b/,
                        alias: 'number'
                    },
                    {
                        // 简单时间格式: 09:03:57.766
                        pattern: /\b\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b/,
                        alias: 'number'
                    },
                    {
                        // Unix 时间戳: 1609459200
                        pattern: /\b1[0-9]{9}\b/,
                        alias: 'number'
                    }
                ],
                
                // 日志级别 - 高优先级
                'log-level': [
                    {
                        pattern: /\b(?:FATAL|CRITICAL)\b/i,
                        alias: 'important'
                    },
                    {
                        pattern: /\bERROR\b/i,
                        alias: 'important'
                    },
                    {
                        pattern: /\bWARN(?:ING)?\b/i,
                        alias: 'builtin'
                    },
                    {
                        pattern: /\bINFO\b/i,
                        alias: 'keyword'
                    },
                    {
                        pattern: /\b(?:DEBUG|TRACE|VERBOSE)\b/i,
                        alias: 'comment'
                    }
                ],
                
                // HTTP 状态码
                'http-status': [
                    {
                        pattern: /\b(?:200|201|202|204|301|302|304)\b/,
                        alias: 'string'
                    },
                    {
                        pattern: /\b(?:400|401|403|404|405|406|408|409|410|422|429)\b/,
                        alias: 'builtin'
                    },
                    {
                        pattern: /\b(?:500|501|502|503|504|505)\b/,
                        alias: 'important'
                    }
                ],
                
                // IP 地址
                'ip-address': {
                    pattern: /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/,
                    alias: 'variable'
                },
                
                // URL
                'url': {
                    pattern: /\bhttps?:\/\/[^\s<>"{}|\\^`[\]]+/i,
                    alias: 'url'
                },
                
                // 文件路径
                'file-path': [
                    {
                        // Unix 路径
                        pattern: /(^|\s)(\/[^\s]*\.(?:log|txt|json|xml|conf|config|yaml|yml|properties|ini))\b/,
                        lookbehind: true,
                        alias: 'string'
                    },
                    {
                        // Windows 路径
                        pattern: /(^|\s)([A-Za-z]:\\[^\s]*\.(?:log|txt|json|xml|conf|config|yaml|yml|properties|ini))\b/,
                        lookbehind: true,
                        alias: 'string'
                    }
                ],
                
                // UUID
                'uuid': {
                    pattern: /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i,
                    alias: 'char'
                },
                
                // 邮箱地址
                'email': {
                    pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/,
                    alias: 'string'
                },
                
                // JSON 对象/数组标识
                'json-structure': {
                    pattern: /[{}\[\]]/,
                    alias: 'punctuation'
                },
                
                // 引用的字符串
                'quoted-string': {
                    pattern: /"[^"]*"|'[^']*'/,
                    alias: 'string'
                },
                
                // 数字（简化版本，避免与时间戳冲突）
                'number': {
                    pattern: /\b\d+\.?\d*\b/
                },
                
                // 特殊符号和分隔符
                'punctuation': /[{}[\](),.:;]/,
                
                // 线程/进程 ID
                'thread-id': {
                    pattern: /\[(?:Thread-|pool-|http-|worker-)?[0-9]+\]/i,
                    alias: 'variable'
                },
                
                // 异常类名
                'exception': {
                    pattern: /\b[A-Z][a-zA-Z0-9]*(?:Exception|Error|Throwable)\b/,
                    alias: 'important'
                }
            };
        },
        
        // 注入组件相关样式
        injectStyles() {
            if (document.getElementById('log-search-results-styles')) {
                return; // 样式已注入
            }
            
            const style = document.createElement('style');
            style.id = 'log-search-results-styles';
            style.textContent = `
                /* 简化层级后样式：直接在 results-section 下渲染 host-result-box */
                .loading-dependencies {
                    flex: 1;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 200px;
                }
                
                /* 独立容器，避免影响全局 .results-section 布局 */
                .results-hosts-row {
                    display: flex;
                    flex-direction: row;
                    gap: 20px;
                    align-items: stretch;
                    padding: 0; /* 去掉底部内边距 */
                    box-sizing: border-box;
                    flex-wrap: nowrap;
                    width: 100%;
                    flex: 1;             /* 占满父容器高度 */
                    min-height: 0;       /* 允许内部滚动 */
                }
                .results-hosts-row > .host-result-box { flex:1; }
                
                .host-result-box {
                    flex: 1;
                    min-width: 0; /* 允许收缩 */
                    border: 1px solid #e4e7ed;
                    border-radius: 8px;
                    overflow: hidden;
                    background: white;
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    min-height: 0; /* 关键：使内部 .host-results 可滚动 */
                }
                
                /* 只在有足够空间时设置最小宽度 */
                @media (min-width: 768px) { .results-hosts-row > .host-result-box { min-width: 300px; } }
                @media (max-width: 767px) {
                    .results-hosts-row { flex-direction: column !important; gap:10px; flex-wrap: nowrap; }
                    .results-hosts-row > .host-result-box { min-height:200px; max-height:300px; }
                }
                
                .host-header {
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    padding: 12px 16px;
                    border-bottom: 1px solid #e4e7ed;
                    position: sticky;
                    top: 0;
                    z-index: 10;
                }
                
                .host-info {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    justify-content: space-between;
                }
                
                .host-left-info {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .host-icon {
                    font-size: 16px;
                }
                
                .host-name {
                    font-weight: 600;
                    color: #303133;
                    font-size: 14px;
                }
                
                .host-count {
                    color: #909399;
                    font-size: 12px;
                    background: #f0f2f5;
                    padding: 2px 6px;
                    border-radius: 10px;
                }

                /* 复用 el-tag 风格的主机信息标签 */
                .host-tags { display: flex; align-items: center; gap: 6px; flex-wrap: nowrap; }
                .host-tags .el-tag { margin: 0; display: inline-flex; align-items: center; max-width: 220px; }
                .host-tags .el-tag .el-tag__content { display: inline-flex; align-items: center; }
                .host-path-tag { max-width: 320px; font-family: 'Fira Code','SF Mono',monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
                @media (max-width: 1400px){ .host-path-tag { max-width: 240px; } }
                @media (max-width: 1100px){ .host-path-tag { max-width: 180px; } }
                @media (max-width: 900px){ .host-path-tag { display:none; } }
                
                .host-actions {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                
                .download-btn {
                    padding: 6px 12px;
                    font-size: 12px;
                    border: 1px solid #e4e7ed;
                    background: #fafbfc;
                    color: #909399;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 4px;
                    min-width: 60px;
                    text-align: center;
                    font-weight: 400;
                    line-height: 1;
                }
                
                .download-btn:hover {
                    background: #f0f2f5;
                    border-color: #c0c4cc;
                    color: #606266;
                    transform: translateY(-1px);
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }
                
                .download-btn:active {
                    background: #e4e7ed;
                    border-color: #b3b8c3;
                    transform: translateY(0);
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
                }
                
                .download-btn:focus {
                    outline: none;
                    border-color: #409eff;
                    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
                }
                
                .download-btn i {
                    font-size: 11px;
                    margin: 0;
                }
                
                .download-btn span {
                    margin: 0;
                    white-space: nowrap;
                }
                
                .host-results {
                    flex: 1;
                    overflow-y: auto;
                    padding: 0;
                    background: #282c34;
                    padding-bottom: 12px;
                    min-height: 0; /* 防止 flex 子元素撑开父级导致不滚动 */
                }
                
                .host-results::-webkit-scrollbar {
                    width: 8px;
                }
                
                .host-results::-webkit-scrollbar-track {
                    background: #f1f1f1;
                    border-radius: 4px;
                }
                
                .host-results::-webkit-scrollbar-thumb {
                    background: #c0c4cc;
                    border-radius: 4px;
                }
                
                .host-results::-webkit-scrollbar-thumb:hover {
                    background: #909399;
                }
                
                .result-line {
                    background: #282c34;
                    transition: background-color 0.2s;
                }
                
                .result-line:hover {
                    background: #2c313c;
                }
                
                .result-content {
                    padding: 8px 16px;
                    font-family: 'Microsoft YaHei', '微软雅黑', 'Fira Code', 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
                    font-size: 14px;  /* 稍微调小字体 */
                    font-weight: 400;  /* 标准字重 */
                    line-height: 1.6;  /* 增加行高提升可读性 */
                    white-space: pre-wrap;
                    overflow-x: auto;
                    word-break: break-all;
                    margin: 0;
                    /* One Dark Pro 背景和文字颜色 */
                    background: #282c34;
                    color: #abb2bf;
                }
                
                .result-content code[class*="language-"],
                .result-content pre[class*="language-"] {
                    font-family: 'Microsoft YaHei', '微软雅黑', 'Fira Code', 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
                    font-size: 16px;  /* 与主要内容保持一致 */
                    font-weight: 400;
                    line-height: 1.6;
                    background: transparent;
                    margin: 0;
                    padding: 0;
                    border: none;
                    border-radius: 0;
                }
                
                .empty-results, .no-data {
                    flex: 1;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    /* 保持与卡片一致的浅色背景 */
                }
                
                /* One Dark Pro 主题配色 */
                .result-content {
                    background: #282c34;
                    color: #abb2bf;
                }
                
                /* Prism.js One Dark Pro 配色扩展 */
                .token.comment { color: #5c6370; font-style: italic; }
                .token.keyword { color: #c678dd; font-weight: bold; }
                .token.builtin { color: #e5c07b; font-weight: bold; }
                .token.important { color: #e06c75; font-weight: bold; }
                .token.number { color: #d19a66; }
                .token.string { color: #98c379; }
                .token.variable { color: #61afef; }
                .token.char { color: #56b6c2; }
                .token.url { color: #61afef; text-decoration: underline; }
                .token.punctuation { color: #abb2bf; }
                
                /* 日志级别专用配色 */
                .token.log-level.important { color: #e06c75; } /* ERROR, FATAL */
                .token.log-level.builtin { color: #e5c07b; }    /* WARN */
                .token.log-level.keyword { color: #61afef; }    /* INFO */
                .token.log-level.comment { color: #5c6370; }    /* DEBUG, TRACE */
                
                /* HTTP 状态码配色 */
                .token.http-status.string { color: #98c379; }     /* 2xx 成功 */
                .token.http-status.builtin { color: #e5c07b; }    /* 4xx 客户端错误 */
                .token.http-status.important { color: #e06c75; }  /* 5xx 服务器错误 */
                
                /* 时间戳配色 */
                .token.timestamp { color: #d19a66; }
                
                /* 搜索高亮样式 */
                mark.search-highlight {
                    background-color: #e5c07b;
                    padding: 1px 3px;
                    border-radius: 3px;
                    font-weight: bold;
                    color: #282c34;
                    box-shadow: 0 1px 3px rgba(229, 192, 123, 0.3);
                    border: none;
                }
                
                /* 兼容旧样式 */
                .log-error { color: #e06c75; font-weight: bold; }
                .log-warn { color: #e5c07b; font-weight: bold; }
                .log-info { color: #61afef; font-weight: bold; }
                .log-debug { color: #5c6370; font-weight: bold; }
                .log-timestamp { color: #d19a66; }
                .log-ip { color: #61afef; }
                .log-status-200 { color: #98c379; font-weight: bold; }
                .log-status-error { color: #e06c75; font-weight: bold; }
                
                /* 主机无结果样式 */
                .host-no-results {
                    flex: 1;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 40px 20px;
                    /* 无结果提示保持浅色背景 */
                    background: #fafafa;
                    border-radius: 6px;
                    margin: 10px;
                }
                
                .no-results-message {
                    text-align: center;
                    font-size: 14px;
                }
                
                /* 截断提示样式 */
                .truncation-notice {
                    border-top: 1px solid #e4e7ed;
                    background: #f5f7fa;
                    padding: 12px 16px;
                    margin-top: 8px;
                    border-radius: 0 0 6px 6px;
                }
                
                .truncation-message {
                    text-align: center;
                    font-size: 13px;
                }
            `;
            document.head.appendChild(style);
        },
        
        // 高亮日志内容
        highlightContent(content) {
            if (!content) return '';
            
            // 如果 Prism.js 还未加载完成，使用简单的转义
            if (!window.Prism || !window.Prism.languages || !window.Prism.languages.log || !window.Prism.highlight) {
                const div = document.createElement('div');
                div.textContent = content;
                return div.innerHTML;
            }
            
            try {
                // 使用 Prism.js 进行语法高亮
                let highlighted = window.Prism.highlight(content, window.Prism.languages.log, 'log');
                
                // 搜索关键词高亮 (最后执行，避免覆盖其他高亮)
                if (this.searchKeyword && this.searchKeyword.trim()) {
                    const escapedKeyword = this.searchKeyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    if (this.useRegex) {
                        try {
                            const regex = new RegExp(this.searchKeyword, 'gi');
                            highlighted = highlighted.replace(regex, '<mark class="search-highlight">$&</mark>');
                        } catch (e) {
                            const regex = new RegExp(escapedKeyword, 'gi');
                            highlighted = highlighted.replace(regex, '<mark class="search-highlight">$&</mark>');
                        }
                    } else {
                        const regex = new RegExp(escapedKeyword, 'gi');
                        highlighted = highlighted.replace(regex, '<mark class="search-highlight">$&</mark>');
                    }
                }
                
                return highlighted;
                
            } catch (error) {
                console.warn('Prism.js highlighting failed:', error);
                // 降级到简单的 HTML 转义
                const div = document.createElement('div');
                div.textContent = content;
                return div.innerHTML;
            }
        },
        
        // 下载日志文件
        async downloadLogFile(hostResult) {
            if (!hostResult || !hostResult.search_result) {
                this.$message.error('无法获取日志文件信息');
                return;
            }
            
            try {
                const filePath = hostResult.search_result.file_path;
                const host = hostResult.host;
                
                if (!filePath) {
                    this.$message.error('日志文件路径不存在');
                    return;
                }
                
                // 显示下载提示
                this.$message.info(`正在准备下载 ${host} 的日志文件...`);
                
                // 构建下载URL参数
                const params = new URLSearchParams({
                    host: host,
                    file_path: filePath
                });
                
                // 如果有日志名称，也传递过去
                if (this.searchResults && this.searchResults.log_name) {
                    params.append('log_name', this.searchResults.log_name);
                }
                
                const downloadUrl = `/api/v1/logs/download?${params.toString()}`;
                
                // 创建隐藏的下载链接
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = `${host}_${this.formatFileName(filePath)}_${this.formatDate(new Date())}.log`;
                link.style.display = 'none';
                
                // 添加到文档并触发下载
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                this.$message.success('下载已开始');
                
            } catch (error) {
                console.error('下载失败:', error);
                this.$message.error('下载失败: ' + error.message);
            }
        },
        
        // 格式化文件名
        formatFileName(filePath) {
            if (!filePath) return 'log';
            
            // 提取文件名（去掉路径）
            const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || 'log';
            
            // 去掉扩展名
            return fileName.replace(/\.[^/.]+$/, '');
        },
        
        // 格式化日期为文件名友好格式
        formatDate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hour = String(date.getHours()).padStart(2, '0');
            const minute = String(date.getMinutes()).padStart(2, '0');
            const second = String(date.getSeconds()).padStart(2, '0');
            
            return `${year}${month}${day}_${hour}${minute}${second}`;
        }
        ,
        // 截断显示路径（保留文件名，路径过长时省略前半部分，仅展示末尾若干目录 + 文件名）
        formatHostPath(fullPath) {
            if (!fullPath) return '';
            const parts = fullPath.split(/[/\\]/).filter(Boolean);
            if (parts.length === 0) return fullPath;
            const fileName = parts[parts.length - 1];
            // 若没有目录结构就直接返回文件名
            if (parts.length === 1) return fileName;
            // 按需求显示为 ../文件名
            return `../${fileName}`;
        }
    },
    
    template: `
        <!-- 依赖加载中 -->
        <div v-if="!dependenciesLoaded" class="loading-dependencies" v-loading="true" element-loading-text="正在加载语法高亮组件..." style="min-height: 100px;"></div>
        
        <!-- 有结果：直接渲染 host-result-box 作为外层 results-section 的直接子元素 -->
        <template v-else>
            <template v-if="searchResults && searchResults.total_matches > 0">
                <div class="results-hosts-row">
                <div class="host-result-box" v-for="group in groupedResults" :key="group.host">
                    <!-- 主机头部 -->
                    <div class="host-header" v-if="showHostGrouping">
                        <div class="host-info">
                            <div class="host-left-info host-tags">
                                <i class="fas fa-server host-icon" style="color:#409eff;"></i>
                                <span class="el-tag el-tag--primary el-tag--light el-tag--small" :title="'主机: '+group.host">{{ group.host }}</span>
                                <span class="el-tag el-tag--info el-tag--light el-tag--small" :title="'匹配条数'">{{ group.results.length }} 条</span>
                                <span class="el-tag el-tag--warning el-tag--light el-tag--small host-path-tag" v-if="group.hostResult && group.hostResult.search_result && group.hostResult.search_result.file_path"
                                      :title="group.hostResult.search_result.file_path">
                                    {{ formatHostPath(group.hostResult.search_result.file_path) }}
                                </span>
                            </div>
                            <div class="host-actions">
                                <button class="download-btn" @click="downloadLogFile(group.hostResult)" title="下载日志文件">
                                    <span>下载日志</span>
                                </button>
                            </div>
                        </div>
                    </div>
                    <!-- 主机结果列表 -->
                    <div class="host-results">
                        <div v-if="group.results.length > 0">
                            <div class="result-line" v-for="(line, index) in group.results" :key="index">
                                <div class="result-content" v-html="highlightContent(line)"></div>
                            </div>
                            <!-- 截断提示 -->
                            <div v-if="group.isTruncated" class="truncation-notice">
                                <div class="truncation-message">
                                    <i class="fas fa-info-circle" style="color: #409eff; margin-right: 8px;"></i>
                                    <span style="color: #606266;">结果过多，已显示前 {{ group.results.length }} 条</span>
                                    <div style="margin-top: 4px; color: #909399; font-size: 12px;">
                                        原始匹配数: {{ group.originalCount }} 条，请使用更具体的关键词缩小搜索范围
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-else class="host-no-results">
                            <!-- 搜索失败的情况 -->
                            <div v-if="group.hostResult && !group.hostResult.success" class="no-results-message">
                                <i class="fas fa-exclamation-triangle" style="color: #f56c6c; margin-right: 8px;"></i>
                                <span style="color: #f56c6c;">搜索失败</span>
                                <div style="margin-top: 4px; color: #f56c6c; font-size: 12px;">
                                    错误: {{ group.hostResult.error || '连接失败' }}
                                </div>
                            </div>
                            <!-- 搜索成功但无匹配结果的情况 -->
                            <div v-else class="no-results-message">
                                <i class="fas fa-check-circle" style="color: #67c23a; margin-right: 8px;"></i>
                                <span style="color: #909399;">搜索完成，未找到匹配内容</span>
                                <div style="margin-top: 4px; color: #c0c4cc; font-size: 12px;">
                                    该主机已成功搜索，但没有找到包含关键词的日志
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                </div>
            </template>
            
            <!-- 空结果提示 -->
            <div v-else-if="searchResults && searchResults.total_matches === 0" class="empty-results">
                <div class="el-empty">
                    <div class="el-empty__image">
                        <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" width="120" height="120">
                            <g fill="none" stroke="#dcdfe6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="25" cy="25" r="20"/>
                                <path d="m40 40 15 15"/>
                                <path d="m18 18 14 14m0-14L18 32" stroke="#f56c6c" stroke-width="2.5"/>
                            </g>
                        </svg>
                    </div>
                    <div class="el-empty__description">{{ emptyMessage }}</div>
                </div>
            </div>
            
            <!-- 无数据状态 -->
            <div v-else class="no-data">
                <div class="el-empty">
                    <div class="el-empty__image">
                        <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" width="120" height="120">
                            <g fill="none" stroke="#dcdfe6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14 8h24l8 8v36a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4V12a4 4 0 0 1 4-4z"/>
                                <path d="M38 8v8h8"/>
                                <line x1="18" y1="24" x2="42" y2="24"/>
                                <line x1="18" y1="32" x2="42" y2="32"/>
                                <line x1="18" y1="40" x2="30" y2="40"/>
                                <circle cx="35" cy="45" r="6" stroke="#909399"/>
                                <path d="m39 49 4 4" stroke="#909399"/>
                            </g>
                        </svg>
                    </div>
                    <div class="el-empty__description">请执行搜索以查看结果</div>
                </div>
            </div>
        </template>
    `
};

// 导出组件
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LogSearchResults;
} else if (typeof window !== 'undefined') {
    window.LogSearchResults = LogSearchResults;
}
