// LogSearchResults 组件 - 优化版本
const LogSearchResults = {
    name: 'LogSearchResults',
    
    // ==================== 生命周期钩子 ====================
    async created() {
        await this.loadDependencies();
    },
    
    mounted() {
        this.addEventListeners();
        this.$nextTick(() => this.recomputeCompaction());
    },
    
    beforeUnmount() {
        this.removeEventListeners();
        this.clearFullscreenState();
    },
    
    // ==================== Props 配置 ====================
    props: {
        // 核心数据属性
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
        
        // 显示控制
        maxResults: {
            type: Number,
            default: 1000
        },
        showHostGrouping: {
            type: Boolean,
            default: true
        },
        emptyMessage: {
            type: String,
            default: '暂无搜索结果'
        }
    },
    
    // ==================== 计算属性 ====================
    computed: {
        groupedResults() {
            if (!this.searchResults?.hosts) return [];
            
            if (!this.showHostGrouping) {
                return this.createSingleGroup();
            }
            
            return this.createHostGroups();
        }
    },
    
    // ==================== 监听器 ====================
    watch: {
        searchResults: {
            handler() {
                this.$nextTick(() => this.recomputeCompaction());
            },
            deep: true
        },
        showHostGrouping() {
            this.$nextTick(() => this.recomputeCompaction());
        }
    },
    
    // ==================== 数据 ====================
    data() {
        return {
            // 常量配置
            CONSTANTS: {
                PRISM_LOAD_DELAY: 100,
                OVERFLOW_TOLERANCE: 1,
                MAX_RESULTS_DEFAULT: 1000
            },
            
            // 状态管理
            dependenciesLoaded: false,
            fullscreenKey: null,
            compactState: {},
            openOverflowFor: null
        };
    },
    
    // ==================== 方法 ====================
    methods: {
        // ---------- 生命周期辅助方法 ----------
        addEventListeners() {
            window.addEventListener('keydown', this.handleKeyDown);
            window.addEventListener('resize', this.recomputeCompaction);
        },
        
        removeEventListeners() {
            window.removeEventListener('keydown', this.handleKeyDown);
            window.removeEventListener('resize', this.recomputeCompaction);
            document.removeEventListener('click', this.handleDocumentClick, { capture: true });
        },
        
        clearFullscreenState() {
            if (this.fullscreenKey) {
                document.body.classList.remove('fullscreen-log-freeze');
            }
        },
        
        // ---------- DOM 工具方法 ----------
        getComponentRoot() {
            return this.$el instanceof HTMLElement 
                ? this.$el 
                : (this.$el?.$el) || document;
        },
        
        // ---------- 结果分组方法 ----------
        createSingleGroup() {
            const allResults = this.searchResults.hosts
                .filter(h => h?.success && Array.isArray(h.results))
                .flatMap(h => h.results);
            
            return [{
                key: 'all',
                host: 'all',
                results: allResults.slice(0, this.maxResults),
                hostResult: null,
                originalCount: allResults.length,
                isTruncated: allResults.length > this.maxResults
            }];
        },
        
        createHostGroups() {
            return this.searchResults.hosts.map(hostResult => {
                const hostResults = (hostResult?.success && Array.isArray(hostResult.results)) 
                    ? hostResult.results 
                    : [];
                
                const originalCount = hostResults.length;
                const isTruncated = this.maxResults && hostResults.length > this.maxResults;
                const results = isTruncated ? hostResults.slice(0, this.maxResults) : hostResults;
                
                const key = this.generateHostKey(hostResult);
                
                return {
                    key,
                    host: hostResult.host,
                    results,
                    hostResult,
                    originalCount,
                    isTruncated
                };
            });
        },
        
        generateHostKey(hostResult) {
            if (!hostResult) return 'unknown|0';
            
            const host = hostResult.host || 'unknown';
            const index = (hostResult.ssh_index !== undefined && hostResult.ssh_index !== null) 
                ? hostResult.ssh_index 
                : 0;
            
            return `${host}|${index}`;
        },
        
        // ---------- UI 交互方法 ----------
        recomputeCompaction() {
            this.$nextTick(() => {
                const root = this.getComponentRoot();
                const infos = root.querySelectorAll('.host-header .host-info[data-group-key]');
                const nextState = {};
                
                infos.forEach(el => {
                    const key = el.getAttribute('data-group-key');
                    if (!key) return;
                    
                    const isOverflow = el.scrollWidth > el.clientWidth + this.CONSTANTS.OVERFLOW_TOLERANCE;
                    nextState[key] = isOverflow;
                });
                
                this.compactState = nextState;
            });
        },
        
        toggleOverflowMenu(key) {
            const isClosing = this.openOverflowFor === key;
            this.openOverflowFor = isClosing ? null : key;
            
            this.$nextTick(() => {
                if (this.openOverflowFor) {
                    document.addEventListener('click', this.handleDocumentClick, { 
                        capture: true, 
                        once: false 
                    });
                } else {
                    document.removeEventListener('click', this.handleDocumentClick, { 
                        capture: true 
                    });
                }
            });
        },
        
        handleDocumentClick(e) {
            const root = this.getComponentRoot();
            const menu = root.querySelector('.host-actions .action-menu.open');
            
            if (menu && !menu.contains(e.target)) {
                this.openOverflowFor = null;
                document.removeEventListener('click', this.handleDocumentClick, { 
                    capture: true 
                });
            }
        },
        
        toggleFullscreen(key) {
            const isExiting = this.fullscreenKey === key;
            
            this.fullscreenKey = isExiting ? null : key;
            document.body.classList.toggle('fullscreen-log-freeze', !isExiting);
            
            this.$nextTick(() => {
                const root = this.getComponentRoot();
                const el = root.querySelector('.host-result-box.fullscreen-active .host-results');
                
                // 触发重绘以确保滚动条正确显示
                if (el) el.scrollTop = el.scrollTop;
                
                this.recomputeCompaction();
            });
        },
        
        handleKeyDown(e) {
            if (e.key === 'Escape' && this.fullscreenKey) {
                this.toggleFullscreen(this.fullscreenKey);
            }
        },
        
        // ---------- 依赖加载方法 ----------
        async loadDependencies() {
            try {
                await this.waitForPrism();
                
                if (window.Prism) {
                    this.initializePrism();
                    console.log('Prism.js loaded successfully with log language');
                } else {
                    console.warn('Prism.js not available, syntax highlighting disabled');
                }
                
                this.dependenciesLoaded = true;
                this.$nextTick(() => this.recomputeCompaction());
            } catch (error) {
                console.warn('Failed to initialize dependencies:', error);
                this.dependenciesLoaded = true;
                this.$nextTick(() => this.recomputeCompaction());
            }
        },
        
        async waitForPrism() {
            if (typeof window.Prism !== 'undefined') return;
            
            await new Promise(resolve => 
                setTimeout(resolve, this.CONSTANTS.PRISM_LOAD_DELAY)
            );
        },
        
        initializePrism() {
            window.Prism = window.Prism || {};
            window.Prism.manual = true;
            this.defineLogLanguage();
        },
        
        // ---------- 语法高亮方法 ----------
        defineLogLanguage() {
            if (!window.Prism) return;
            
            window.Prism.languages.log = {
                'timestamp': this.getTimestampPatterns(),
                'log-level': this.getLogLevelPatterns(),
                'http-status': this.getHttpStatusPatterns(),
                'ip-address': {
                    pattern: /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/,
                    alias: 'variable'
                },
                'url': {
                    pattern: /\bhttps?:\/\/[^\s<>"{}|\\^`[\]]+/i,
                    alias: 'url'
                },
                'file-path': this.getFilePathPatterns(),
                'uuid': {
                    pattern: /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i,
                    alias: 'char'
                },
                'email': {
                    pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/,
                    alias: 'string'
                },
                'json-structure': {
                    pattern: /[{}\[\]]/,
                    alias: 'punctuation'
                },
                'quoted-string': {
                    pattern: /"[^"]*"|'[^']*'/,
                    alias: 'string'
                },
                'number': {
                    pattern: /\b\d+\.?\d*\b/
                },
                'punctuation': /[{}[\](),.:;]/,
                'thread-id': {
                    pattern: /\[(?:Thread-|pool-|http-|worker-)?[0-9]+\]/i,
                    alias: 'variable'
                },
                'exception': {
                    pattern: /\b[A-Z][a-zA-Z0-9]*(?:Exception|Error|Throwable)\b/,
                    alias: 'important'
                }
            };
        },
        
        getTimestampPatterns() {
            return [
                {
                    pattern: /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?\b/,
                    alias: 'number'
                },
                {
                    pattern: /\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b/,
                    alias: 'number'
                },
                {
                    pattern: /\b\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b/,
                    alias: 'number'
                },
                {
                    pattern: /\b\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b/,
                    alias: 'number'
                },
                {
                    pattern: /\b1[0-9]{9}\b/,
                    alias: 'number'
                }
            ];
        },
        
        getLogLevelPatterns() {
            return [
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
            ];
        },
        
        getHttpStatusPatterns() {
            return [
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
            ];
        },
        
        getFilePathPatterns() {
            return [
                {
                    pattern: /(^|\s)(\/[^\s]*\.(?:log|txt|json|xml|conf|config|yaml|yml|properties|ini))\b/,
                    lookbehind: true,
                    alias: 'string'
                },
                {
                    pattern: /(^|\s)([A-Za-z]:\\[^\s]*\.(?:log|txt|json|xml|conf|config|yaml|yml|properties|ini))\b/,
                    lookbehind: true,
                    alias: 'string'
                }
            ];
        },
        
        highlightContent(content) {
            if (!content) return '';
            
            if (!this.isPrismReady()) {
                return this.escapeHtml(content);
            }
            
            try {
                let highlighted = window.Prism.highlight(
                    content, 
                    window.Prism.languages.log, 
                    'log'
                );
                
                if (this.searchKeyword?.trim()) {
                    highlighted = this.highlightSearchKeyword(highlighted);
                }
                
                return highlighted;
            } catch (error) {
                console.warn('Prism.js highlighting failed:', error);
                return this.escapeHtml(content);
            }
        },
        
        isPrismReady() {
            return window.Prism?.languages?.log && window.Prism.highlight;
        },
        
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        highlightSearchKeyword(content) {
            const escapedKeyword = this.searchKeyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            
            try {
                const regex = this.useRegex 
                    ? new RegExp(this.searchKeyword, 'gi')
                    : new RegExp(escapedKeyword, 'gi');
                
                return content.replace(regex, '<mark class="search-highlight">$&</mark>');
            } catch (e) {
                // 正则表达式无效时使用转义版本
                const regex = new RegExp(escapedKeyword, 'gi');
                return content.replace(regex, '<mark class="search-highlight">$&</mark>');
            }
        },
        
        // ---------- 文件操作方法 ----------
        async downloadLogFile(hostResult) {
            if (!hostResult?.search_result) {
                this.$message.error('无法获取日志文件信息');
                return;
            }
            
            const { file_path: filePath } = hostResult.search_result;
            const { host } = hostResult;
            
            if (!filePath) {
                this.$message.error('日志文件路径不存在');
                return;
            }
            
            try {
                this.$message.info(`正在准备下载 ${host} 的日志文件...`);
                
                const downloadUrl = this.buildDownloadUrl(host, filePath);
                const fileName = this.generateDownloadFileName(host, filePath);
                
                this.triggerDownload(downloadUrl, fileName);
                
                this.$message.success('下载已开始');
            } catch (error) {
                console.error('下载失败:', error);
                this.$message.error('下载失败: ' + error.message);
            }
        },
        
        buildDownloadUrl(host, filePath) {
            const params = new URLSearchParams({
                host,
                file_path: filePath
            });
            
            if (this.searchResults?.log_name) {
                params.append('log_name', this.searchResults.log_name);
            }
            
            return `/api/v1/logs/download?${params.toString()}`;
        },
        
        generateDownloadFileName(host, filePath) {
            const baseName = this.formatFileName(filePath);
            const timestamp = this.formatDate(new Date());
            return `${host}_${baseName}_${timestamp}.log`;
        },
        
        triggerDownload(url, fileName) {
            const link = document.createElement('a');
            link.href = url;
            link.download = fileName;
            link.style.display = 'none';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        },
        
        // ---------- 格式化工具方法 ----------
        formatFileName(filePath) {
            if (!filePath) return 'log';
            
            const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || 'log';
            return fileName.replace(/\.[^/.]+$/, '');
        },
        
        formatDate(date) {
            const pad = (num) => String(num).padStart(2, '0');
            
            const year = date.getFullYear();
            const month = pad(date.getMonth() + 1);
            const day = pad(date.getDate());
            const hour = pad(date.getHours());
            const minute = pad(date.getMinutes());
            const second = pad(date.getSeconds());
            
            return `${year}${month}${day}_${hour}${minute}${second}`;
        },
        
        formatHostPath(fullPath) {
            if (!fullPath) return '';
            
            const parts = fullPath.split(/[/\\]/).filter(Boolean);
            if (parts.length === 0) return fullPath;
            if (parts.length === 1) return parts[0];
            
            return `../${parts[parts.length - 1]}`;
        },
        
        // ---------- 导航方法 ----------
        openSftp(hostResult) {
            if (!hostResult) return;
            
            const logName = this.searchResults?.log_name || '';
            const idx = hostResult.ssh_index;
            const url = `/sftp?single=1&log_name=${encodeURIComponent(logName)}&ssh_index=${encodeURIComponent(idx)}`;
            
            window.open(url, '_blank');
        },
        
        openTerminal(hostResult) {
            if (!hostResult) return;
            
            const logName = this.searchResults?.log_name || '';
            const idx = hostResult.ssh_index;
            const url = `/terminals?single=1&log_name=${encodeURIComponent(logName)}&ssh_index=${encodeURIComponent(idx)}`;
            
            window.open(url, '_blank');
        }
    },
    
    // ==================== 模板 ====================
    template: `
        <!-- 依赖加载中 -->
        <div v-if="!dependenciesLoaded" class="loading-dependencies" v-loading="true" element-loading-text="正在加载语法高亮组件..." style="min-height: 100px;"></div>
        
        <!-- 有结果：直接渲染 host-result-box 作为外层 results-section 的直接子元素 -->
        <template v-else>
            <!-- 显示主机结果盒：有匹配结果 或 处于占位预搜索状态 -->
            <template v-if="searchResults && searchResults.hosts && searchResults.hosts.length && (searchResults.total_matches > 0 || searchResults.pre_search)">
                <div class="results-hosts-row" :class="{ 'grid-2x2': showHostGrouping && groupedResults.length === 4 }">
                <div class="host-result-box" :class="{ 'fullscreen-active': fullscreenKey === group.key }" v-for="group in groupedResults" :key="group.key">
                    <!-- 主机头部 -->
                    <div class="host-header" v-if="showHostGrouping">
                        <div class="host-info" :data-group-key="group.key">
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
                                <!-- 折叠模式：显示更多菜单按钮 -->
                                <template v-if="compactState[group.key]">
                                    <div class="action-menu" :class="{ open: openOverflowFor===group.key }">
                                        <button class="action-btn more-btn" @click.stop="toggleOverflowMenu(group.key)" title="更多操作" aria-label="更多">
                                            <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                                <circle cx="5" cy="12" r="1.6" fill="currentColor"/>
                                                <circle cx="12" cy="12" r="1.6" fill="currentColor"/>
                                                <circle cx="19" cy="12" r="1.6" fill="currentColor"/>
                                            </svg>
                                        </button>
                                        <div class="menu-popover" v-show="openOverflowFor===group.key">
                                            <button class="menu-item" @click="openOverflowFor=null; openSftp(group.hostResult)">
                                                <span class="mi-icon">
                                                    <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                                        <path d="M4 6h4.2c.4 0 .78.16 1.06.44l1.3 1.3c.28.28.66.44 1.06.44H19a1 1 0 0 1 1 1v7.5A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5V6Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>
                                                    </svg>
                                                </span>
                                                <span>文件管理</span>
                                            </button>
                                            <button class="menu-item" @click="openOverflowFor=null; openTerminal(group.hostResult)">
                                                <span class="mi-icon">
                                                    <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                                        <path d="M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.2" fill="none"/>
                                                        <path d="m7 9 3.5 3L7 15" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                                        <path d="M11.5 15H17" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                                                    </svg>
                                                </span>
                                                <span>在线终端</span>
                                            </button>
                                            <button class="menu-item" @click="openOverflowFor=null; toggleFullscreen(group.key)">
                                                <span class="mi-icon">
                                                    <svg viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
                                                        <path d="M4 9V5a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                                        <path d="M20 15v4a1 1 0 0 1-1 1h-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                                        <path d="M15 4h4a1 1 0 0 1 1 1v4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                                        <path d="M9 20H5a1 1 0 0 1-1-1v-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                                    </svg>
                                                </span>
                                                <span>放大查看</span>
                                            </button>
                                            <button class="menu-item" @click="openOverflowFor=null; downloadLogFile(group.hostResult)">
                                                <span class="mi-icon">
                                                    <svg viewBox="0 0 24 24" role="img" focusable="false" aria-hidden="true">
                                                        <path d="M12 4v11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                                        <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                                        <path d="M5 19h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                                                    </svg>
                                                </span>
                                                <span>下载日志</span>
                                            </button>
                                        </div>
                                    </div>
                                </template>
                                <!-- 常规模式：逐个按钮展示 -->
                                <template v-else>
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
                                    <button class="action-btn" :class="{ 'is-active': fullscreenKey === group.key }" @click="toggleFullscreen(group.key)" :title="fullscreenKey === group.key ? '退出全屏 (Esc)' : '放大查看'" aria-label="放大/还原">
                                        <svg v-if="fullscreenKey !== group.key" viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
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
                                </template>
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
                                    输入关键词并点击 "搜索"
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
