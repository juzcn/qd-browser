# qd-browser 项目需求文档

## 项目概述
基于 Playwright 浏览器自动化的综合爬虫 CLI 工具，包含搜索、爬取、下载、解析、智能 LLM 爬取功能。

## 技术选型
- **浏览器自动化**: Playwright
- **包管理**: uv
- **Python 版本**: 3.13
- **CLI 框架**: typer
- **HTML 解析**: beautifulsoup4 + trafilatura
- **Markdown 转换**: trafilatura（纯净输出）
- **终端美化**: rich
- **配置管理**: pydantic-settings, python-dotenv
- **HTTP 客户端**: httpx, requests
- **域名解析**: tldextract
- **LLM SDK**: openai（用于 NVIDIA API）
- **构建后端**: hatchling

## 核心功能
1. **页面爬取**: 使用浏览器访问网页、提取内容 ✅
2. **文件下载**: 下载网页中的附件资源（PDF、Word、图片等）✅
3. **内容解析**: HTML 转 Markdown、正文提取、结构化输出 ✅
4. **批量爬取**: 通过搜索引擎发现链接并批量处理 ✅
5. **搜索功能**: 集成 Serper 和百度搜索，API 失败时自动 fallback 到浏览器搜索 ✅
6. **URL 去重**: 全局历史记录，支持跳过已访问 URL ✅
7. **智能 LLM 爬取**: 使用 NVIDIA 免费大模型理解用户自然语言需求，自动提取搜索关键词、域名列表和输出目录，然后调用 domain-download 进行批量爬取，不花一分钱！✅
8. **动态模型池**: 从 NVIDIA API 自动获取当前可用模型 ✅
9. **智能体友好模式**: 支持 `--json`、`--quiet`、`--no-color` 全局选项，所有命令输出机器可读 JSON，方便 AI 智能体通过 stdout/stderr 调用 ✅

## CLI 配置
- **总是使用无头浏览器**: 无 --headless 选项
- **统一输出目录**: --output-dir 在子命令中
- **语言选项**: --language，默认 zh（中文），文件夹命名：zh→"附件"，en→"attachments"
- **URL 哈希**: --hash-url，使用稳定的 MD5 哈希作为文件名后缀（默认不开启）
- **总是下载附件**: 无 --download 选项，自动下载页面中的附件
- **调试模式**: --debug 选项，仅在子命令中使用，不从环境变量读取
- **默认跳过已访问**: 默认跳过历史记录中已访问的 URL，使用 --not-skip 强制重新处理
- **自动域名子目录**: 自动从 URL 解析域名作为输出子目录（不带 www 前缀）
- **智能体友好全局选项**（所有命令通用）:
  - `--json`: 输出机器可读的 JSON 格式
  - `--quiet` / `-q`: 静默模式，只输出错误和最终结果
  - `--no-color`: 禁用彩色输出

## 已实现模块
- `cli.py`: CLI 命令行入口，提供 `url-download`、`domain-download`、`web-download`、`llm-download`、`config` 命令
- `crawler.py`: 爬虫核心，整合浏览器、解析器、下载器
- `browser.py`: 浏览器管理器，封装 Playwright
- `parser.py`: 内容解析器，提取正文、元数据、附件链接
- `downloader.py`: 文件下载器，支持断点续传显示
- `config.py`: 配置管理，基于 pydantic-settings
- `utils.py`: 工具函数（哈希、文件名清理、URL 检测、域名验证）
- `search.py`: 搜索功能（Serper/百度 API + 浏览器搜索 fallback）
- `history.py`: URL 访问历史记录管理
- `llm.py`: LLM 模块（NVIDIA API、动态模型池、智能任务解析）

## 代码结构
- `process_single_url`: 处理单个 URL 的核心逻辑
- `process_single_domain`: 处理单个域名搜索和爬取的核心逻辑（domain-download 和 llm-download 共用）

## 使用示例
```bash
# 爬取单个网页（自动下载附件）
uv run qd-browser url-download https://example.com

# 调试模式（保存原始 HTML）
uv run qd-browser url-download --debug https://example.com

# 批量爬取（通过搜索引擎发现链接，默认跳过已访问）
uv run qd-browser domain-download example.com "搜索关键词"

# 不跳过已访问的 URL（强制重新处理）
uv run qd-browser domain-download --not-skip example.com "搜索关键词"

# LLM 普通内容生成
uv run qd-browser llm-download "写一篇关于人工智能的文章"

# LLM 智能爬取任务（自动识别并执行）
uv run qd-browser llm-download "帮我找一些企业编写ESG的官方指南"

# 查看历史记录统计
uv run qd-browser config --stats

# 列出历史记录
uv run qd-browser config --history

# 清空历史记录
uv run qd-browser config --init
```

## PyPI 发布
- 包名: qd-browser
- 当前版本: 0.1.0
- PyPI 地址: https://pypi.org/project/qd-browser/

## 开发历史
- 2026-04-10: first release
- 2026-04-11: 添加 llm-download 命令、动态模型池、智能爬取任务、发布到 PyPI
- 2026-04-15: 添加智能体友好模式（--json、--quiet、--no-color），所有命令支持机器可读 JSON 输出