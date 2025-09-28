// LogSearchResults 组件
const LogSearchResults = {
    name: 'LogSearchResults',
    
    // 组件依赖加载
    async created() {
        await this.loadDependencies();
        // this.injectStyles();  // 移除样式注入调用
    },
    mounted() {
        window.addEventListener('keydown', this.handleKeyDown);
    },
    beforeUnmount() {
        window.removeEventListener('keydown', this.handleKeyDown);
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
            dependenciesLoaded: false,
            fullscreenHost: null
        };
    },
    
    methods: {
        toggleFullscreen(host){
            if(this.fullscreenHost === host){
                this.fullscreenHost = null;
                document.body.classList.remove('fullscreen-log-freeze');
            } else {
                this.fullscreenHost = host;
                document.body.classList.add('fullscreen-log-freeze');
            }
            this.$nextTick(()=>{
                const el = document.querySelector('.host-result-box.fullscreen-active .host-results');
                if(el){ el.scrollTop = el.scrollTop; }
            });
        },
        handleKeyDown(e){
            if(e.key === 'Escape' && this.fullscreenHost){
                this.toggleFullscreen(this.fullscreenHost);
            }
        },
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
            // 移除样式注入：样式已移至静态文件 log-results.css
            // 保留函数以兼容旧版，现为无操作
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
        ,
        openSftp(hostResult){
            if(!hostResult) return;
            const logName = (this.searchResults && this.searchResults.log_name) || '';
            const idx = hostResult.ssh_index;
            const url = `/sftp?single=1&log_name=${encodeURIComponent(logName)}&ssh_index=${encodeURIComponent(idx)}`;
            window.open(url, '_blank');
        },
        openTerminal(hostResult){
            if(!hostResult) return;
            const logName = (this.searchResults && this.searchResults.log_name) || '';
            const idx = hostResult.ssh_index;
            const url = `/terminals?single=1&log_name=${encodeURIComponent(logName)}&ssh_index=${encodeURIComponent(idx)}`;
            window.open(url, '_blank');
        }
    },
    
    template: `
        <!-- 依赖加载中 -->
        <div v-if="!dependenciesLoaded" class="loading-dependencies" v-loading="true" element-loading-text="正在加载语法高亮组件..." style="min-height: 100px;"></div>
        
        <!-- 有结果：直接渲染 host-result-box 作为外层 results-section 的直接子元素 -->
        <template v-else>
            <!-- 显示主机结果盒：有匹配结果 或 处于占位预搜索状态 -->
            <template v-if="searchResults && searchResults.hosts && searchResults.hosts.length && (searchResults.total_matches > 0 || searchResults.pre_search)">
                <div class="results-hosts-row">
                <div class="host-result-box" :class="{ 'fullscreen-active': fullscreenHost === group.host }" v-for="group in groupedResults" :key="group.host">
                    <!-- 主机头部 -->
                    <div class="host-header" v-if="showHostGrouping">
                        <div class="host-info">
                            <div class="host-left-info host-tags">
                                <span class="host-icon" aria-hidden="true" style="color:#409eff;display:inline-flex;">\
                                    <svg viewBox="0 0 24 24" width="16" height="16" role="img" focusable="false" aria-hidden="true">\
                                        <rect x="3" y="4" width="18" height="6" rx="2" ry="2" fill="none" stroke="currentColor" stroke-width="1.4"/>\
                                        <rect x="3" y="14" width="18" height="6" rx="2" ry="2" fill="none" stroke="currentColor" stroke-width="1.4"/>\
                                        <circle cx="7" cy="7" r="1" fill="currentColor"/>\
                                        <circle cx="7" cy="17" r="1" fill="currentColor"/>\
                                    </svg>\
                                </span>
                                <span class="el-tag el-tag--primary el-tag--light el-tag--small" :title="'主机: '+group.host">[[ group.host ]]</span>
                                <span class="el-tag el-tag--info el-tag--light el-tag--small" :title="'匹配条数'">[[ group.results.length ]] 条</span>
                                                                <span class="el-tag el-tag--warning el-tag--light el-tag--small host-path-tag" v-if="group.hostResult && group.hostResult.search_result && group.hostResult.search_result.file_path"
                                                                            :title="group.hostResult.search_result.file_path">
                                                                        [[ formatHostPath(group.hostResult.search_result.file_path) ]]
                                                                </span>
                            </div>
                            <div class="host-actions">
                                                                <button class="action-btn" @click="openSftp(group.hostResult)" :title="'文件管理 '+group.host" aria-label="文件管理">
                                                                    <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                                                        <path d="M4 6h4.2c.4 0 .78.16 1.06.44l1.3 1.3c.28.28.66.44 1.06.44H19a1 1 0 0 1 1 1v7.5A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5V6Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>
                                                                    </svg>
                                                                </button>
                                                                <button class="action-btn" @click="openTerminal(group.hostResult)" :title="'在线终端 '+group.host" aria-label="在线终端">
                                                                    <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                                                        <path d="M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.2" fill="none"/>
                                                                        <path d="m7 9 3.5 3L7 15" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                                                        <path d="M11.5 15H17" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                                                                    </svg>
                                                                </button>
                                <button class="action-btn" :class="{ 'is-active': fullscreenHost === group.host }" @click="toggleFullscreen(group.host)" :title="fullscreenHost === group.host ? '退出全屏 (Esc)' : '放大查看'" aria-label="放大/还原">
                                    <svg v-if="fullscreenHost !== group.host" viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
                                        <path d="M4 9V5a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M20 15v4a1 1 0 0 1-1 1h-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M15 4h4a1 1 0 0 1 1 1v4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M9 20H5a1 1 0 0 1-1-1v-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                    </svg>
                                    <svg v-else viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
                                        <path d="M9 9H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M15 15h4a1 1 0 0 1 1 1v3.99a1 1 0 0 1-1.01 1.01H15" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M20 9h-4a1 1 0 0 1-1-1V4.99A1 1 0 0 1 15.99 4H20a1 1 0 0 1 1 1v4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M4 15h4a1 1 0 0 1 1 1v4.01A1 1 0 0 1 8.01 21H4a1 1 0 0 1-1-1v-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                    </svg>
                                </button>
                                <button class="action-btn" @click="downloadLogFile(group.hostResult)" title="下载日志文件" aria-label="下载日志">
                                    <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                        <path d="M12 4v11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                        <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                        <path d="M5 19h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                                    </svg>
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
                                    <span style="color: #606266;">结果过多，已显示前 [[ group.results.length ]] 条</span>
                                    <div style="margin-top: 4px; color: #909399; font-size: 12px;">
                                        原始匹配数: [[ group.originalCount ]] 条，请使用更具体的关键词缩小搜索范围
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-else class="host-no-results">
                            <!-- 占位预搜索提示 -->
                            <div v-if="searchResults.pre_search" class="no-results-message" style="background:transparent;">
                                <i class="fas fa-clock" style="color: #ffffff80; margin-right: 8px;"></i>
                                <span style="color: #ffffffb3; font-weight:400;">等待搜索</span>
                                <div style="margin-top: 4px; color: #ffffff40; font-size: 12px; letter-spacing:.5px;">
                                    输入关键词并点击 “搜索”
                                </div>
                            </div>
                            <!-- 搜索失败的情况 -->
                            <div v-else-if="group.hostResult && !group.hostResult.success" class="no-results-message">
                                <i class="fas fa-exclamation-triangle" style="color: #f56c6c; margin-right: 8px;"></i>
                                <span style="color: #f56c6c;">搜索失败</span>
                                <div style="margin-top: 4px; color: #f56c6c; font-size: 12px;">
                                    错误: [[ group.hostResult.error || '连接失败' ]]
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
            <div v-else-if="searchResults && searchResults.total_matches === 0 && !searchResults.pre_search" class="empty-results">
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
                    <div class="el-empty__description">[[ emptyMessage ]]</div>
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
