# qd-browser

基于 Playwright 的综合爬虫 CLI 工具。

## 功能特性

- **浏览器自动化**: 基于 Playwright，支持动态网页爬取
- **内容解析**: 自动提取网页正文、元数据、附件链接
- **Markdown 导出**: 将网页内容转换为 Markdown 格式保存
- **附件下载**: 批量下载页面中的 PDF、Word、Excel 等附件
- **搜索引擎集成**: Serper + 百度搜索，API 失败自动 fallback 到浏览器搜索
- **URL 去重**: 全局访问历史记录，支持跳过已访问 URL
- **自动域名子目录**: 自动从 URL 解析域名作为输出子目录

## 安装

```bash
# 安装依赖
uv sync

# 安装 Playwright Chromium 浏览器
uv run playwright install chromium
```

## 使用方法

### 基本用法

```bash
# 查看帮助
uv run qd-browser --help

# 爬取单个网页（自动下载附件，默认中文文件夹）
# 自动从 URL 解析域名作为子目录
uv run qd-browser url-download https://www.example.com

# 指定输出目录
uv run qd-browser url-download --output-dir ./my-output https://example.com

# 使用英文文件夹命名
uv run qd-browser url-download --language en https://example.com

# 使用稳定的 URL 哈希作为文件名后缀（跨进程一致）
uv run qd-browser url-download --hash-url https://example.com

# 调试模式
uv run qd-browser url-download --debug https://example.com

# 不跳过已访问的 URL（强制重新处理）
uv run qd-browser url-download --not-skip https://example.com
```

### 命令说明

#### `url-download` - 爬取单个网页并下载内容（包含附件）

```bash
uv run qd-browser url-download [OPTIONS] URL
```

自动从 URL 解析域名作为输出子目录（例如 `output/example.com/`）。

选项:
- `--output-dir TEXT`: 输出目录（默认: ./output）
- `--language TEXT`: 语言：zh（中文）或 en（英文），影响文件夹命名（默认: zh）
- `--hash-url`: 使用稳定的 URL 哈希（MD5）作为文件名后缀
- `--debug`: 调试模式，保存原始 HTML
- `--url-title TEXT`: URL 的标题/描述，用于文件命名
- `--not-skip`: 不跳过已访问的 URL（强制重新处理）

#### `domain-download` - 通过搜索引擎批量爬取（包含附件）

```bash
uv run qd-browser domain-download <域名或URL> <搜索关键词>
```

通过 Serper 和百度搜索发现目标域名下的链接，然后批量爬取。
所有结果保存到以域名为名的子目录下。

选项:
- `--output-dir TEXT`: 输出目录（默认: ./output）
- `--language TEXT`: 语言：zh（中文）或 en（英文），影响文件夹命名（默认: zh）
- `--hash-url`: 使用稳定的 URL 哈希（MD5）作为文件名后缀
- `--debug`: 调试模式，保存原始 HTML
- `--not-skip`: 不跳过已访问的 URL（强制重新处理）

#### `web-download` - 全网搜索并批量爬取（包含附件）

```bash
uv run qd-browser web-download <搜索关键词>
```

全网搜索（不限制域名），每个 URL 自动保存到其对应域名的子目录下。

选项:
- `--output-dir TEXT`: 输出目录（默认: ./output）
- `--language TEXT`: 语言：zh（中文）或 en（英文），影响文件夹命名（默认: zh）
- `--hash-url`: 使用稳定的 URL 哈希（MD5）作为文件名后缀
- `--debug`: 调试模式，保存原始 HTML
- `--not-skip`: 不跳过已访问的 URL（强制重新处理）

#### `config` - 配置和历史记录管理

```bash
# 显示当前配置
uv run qd-browser config --settings
uv run qd-browser config -s

# 历史记录统计
uv run qd-browser config --stats
uv run qd-browser config -t

# 列出历史记录
uv run qd-browser config --history
uv run qd-browser config -l

# 按状态过滤
uv run qd-browser config --history --by-status success

# 按域名过滤
uv run qd-browser config --history --by-site example.com

# 按输出目录过滤
uv run qd-browser config --history --by-output-dir ./output

# 按 URL 过滤
uv run qd-browser config --history --by-url https://example.com
uv run qd-browser config --history -c example.com

# 从历史记录中移除 URL
uv run qd-browser config --remove-url https://example.com
uv run qd-browser config -r https://example.com

# 移除指定域名的所有记录
uv run qd-browser config --remove-site example.com

# 移除指定输出目录的所有记录
uv run qd-browser config --remove-output-dir ./output

# 移除指定状态的所有记录
uv run qd-browser config --remove-status failed

# 清空所有历史记录
uv run qd-browser config --init
```

## 配置

可以通过环境变量配置，前缀为 `QD_`:

```bash
QD_OUTPUT_DIR=./my-output
```

也可以在项目根目录创建 `.env` 文件进行配置。

### 搜索 API 配置

支持多个 API key 用于 fallback：

```bash
SERPER_API_KEY=xxx
SERPER_API_KEY_1=xxx
SERPER_API_KEY_2=xxx

BAIDU_API_KEY=xxx
BAIDU_API_KEY_1=xxx
BAIDU_API_KEY_2=xxx
```

当所有 API key 都失败时，会自动使用浏览器进行搜索作为备用。

### URL 历史记录

全局 URL 访问历史保存在：
- Windows: `C:\Users\用户名\.qd_browser\visited.json`
- Linux/Mac: `~/.qd_browser/visited.json`

## 项目结构

```
qd-browser/
├── src/qd_browser/
│   ├── __init__.py          # 包初始化
│   ├── cli.py               # CLI 入口
│   ├── config.py            # 配置管理
│   ├── browser.py           # 浏览器管理
│   ├── crawler.py           # 爬虫核心
│   ├── parser.py            # 内容解析
│   ├── downloader.py        # 文件下载
│   ├── utils.py            # 工具函数
│   ├── search.py           # 搜索功能
│   └── history.py          # URL 历史记录
├── output/                  # 输出目录
│   └── attachments/         # 附件下载目录
├── pyproject.toml           # 项目配置
└── README.md
```

## 技术栈

- **playwright**: 浏览器自动化
- **typer**: CLI 框架
- **beautifulsoup4**: HTML 解析
- **trafilatura**: 网页正文提取 + HTML 转 Markdown
- **rich**: 终端美化
- **pydantic-settings**: 配置管理
- **httpx**: HTTP 客户端
- **tldextract**: 域名解析
