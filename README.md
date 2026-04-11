# qd-browser

[![PyPI version](https://img.shields.io/pypi/v/qd-browser.svg)](https://pypi.org/project/qd-browser/)
[![PyPI downloads](https://img.shields.io/pypi/dm/qd-browser.svg)](https://pypi.org/project/qd-browser/)
[![License](https://img.shields.io/pypi/l/qd-browser.svg)](https://pypi.org/project/qd-browser/)
[![Python versions](https://img.shields.io/pypi/pyversions/qd-browser.svg)](https://pypi.org/project/qd-browser/)

基于 Playwright 的综合爬虫 CLI 工具，可以按URL、域名和提示词爬取网页和下载文件。

## 功能特性

- **浏览器自动化**: 基于 Playwright，支持动态网页爬取
- **内容解析**: 自动提取网页正文、元数据、附件链接
- **Markdown 导出**: 将网页内容转换为 Markdown 格式保存
- **附件下载**: 批量下载页面中的 PDF、Word、Excel 等附件
- **搜索引擎集成**: Serper + 百度搜索，API 失败自动 fallback 到浏览器搜索
- **URL 去重**: 全局访问历史记录，支持跳过已访问 URL
- **自动域名子目录**: 自动从 URL 解析域名作为输出子目录
- **智能 LLM 爬取**: 使用 NVIDIA 免费模型（Llama 3.1 等）理解用户意图，自动提取搜索关键词、域名列表和输出目录，然后调用 domain-download 进行批量爬取，不花一分钱！

## 安装

### 方式一：从 PyPI 安装（推荐）

```bash
# 使用 pip 安装
pip install qd-browser

# 使用 uv 安装
uv pip install qd-browser

# 安装后需要安装 Playwright 浏览器
playwright install chromium
```

### 方式二：从 Git 安装

```bash
# 使用 pip 从 Git 安装
pip install git+https://github.com/juzcn/qd-browser.git

# 安装特定分支
pip install git+https://github.com/juzcn/qd-browser.git@main

# 安装特定 tag
pip install git+https://github.com/juzcn/qd-browser.git@v0.1.0

# 使用 uv 从 Git 安装
uv pip install git+https://github.com/juzcn/qd-browser.git

# 安装后需要安装 Playwright 浏览器
playwright install chromium
```

### 方式三：从源码安装（开发者）

```bash
# 克隆仓库
git clone https://github.com/juzcn/qd-browser.git
cd qd-browser

# 使用 uv 安装依赖
uv sync

# 安装 Playwright Chromium 浏览器
uv run playwright install chromium
```

### 方式四：从本地分发包安装

```bash
# 安装 wheel 包
pip install qd_browser-0.1.0-py3-none-any.whl

# 或安装源码包
pip install qd-browser-0.1.0.tar.gz

# 使用 uv 安装
uv pip install ./dist/qd_browser-0.1.0-py3-none-any.whl
```

## 开发者：构建分发包

```bash
# 安装构建工具
uv sync --dev

# 构建 sdist 和 wheel
uv run python -m build

# 生成的包在 dist/ 目录下
ls dist/
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

#### `llm-download` - 智能 LLM 爬取（免费使用 NVIDIA 大模型）

```bash
# 智能爬取示例 - 用自然语言描述你的需求
uv run qd-browser llm-download "去上交所、深交所和北交所网站爬取esg编写指南"

# 另一个示例
uv run qd-browser llm-download "帮我找一些企业编写ESG的官方指南"

# 指定输出目录
uv run qd-browser llm-download "去证监会网站找最新的公告" --output-dir ./my-docs

# 调试模式
uv run qd-browser llm-download "测试" --debug
```

**工作原理**：
1. 使用 NVIDIA API Catalog 提供的免费大模型（Llama 3.1 等）理解你的自然语言需求
2. 自动提取：
   - **搜索关键词**（query）
   - **域名列表**（支持多个域名）
   - **输出目录**（可选）
3. 自动调用 `domain-download` 对每个域名进行搜索和批量爬取
4. **完全免费**，用户只需提供 NVIDIA API Key，不花一分钱！

**模型池**：
- 自动从 NVIDIA API 获取当前可用模型
- 按优先级排序后使用前 5 个最强模型
- 支持自动 fallback

选项:
- `--output-dir TEXT`: 输出目录（默认: ./output）
- `--language TEXT`: 语言：zh（中文）或 en（英文）（默认: zh）
- `--debug`: 调试模式，显示详细错误信息

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

### NVIDIA LLM API 配置

使用 `llm-download` 命令需要配置：

```bash
NVAPI_KEY=nvapi-xxx
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

获取 API Key: https://build.nvidia.com/

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
│   ├── history.py          # URL 历史记录
│   └── llm.py              # LLM 生成（NVIDIA API）
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
- **openai**: OpenAI SDK（用于 NVIDIA API）
- **hatchling**: 构建后端

## 开发者：发布到 PyPI

### 1. 构建分发包

```bash
# 清理旧的构建
rm -rf dist/ build/ *.egg-info/

# 构建 sdist 和 wheel
uv run python -m build
```

### 2. 上传到 TestPyPI（测试）

```bash
# 安装 twine
uv pip install twine

# 上传到 TestPyPI
uv run twine upload --repository testpypi dist/*
```

### 3. 从 TestPyPI 测试安装

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ qd-browser
```

### 4. 上传到 PyPI（正式发布）

```bash
# 上传到 PyPI
uv run twine upload dist/*
```

### PyPI 账号配置

在 `~/.pypirc` 中配置：

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-你的token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-你的testtoken
```
