---
name: qd-browser
description: Web crawler CLI tool based on Playwright. Crawl web pages, download attachments, and save content as Markdown.
metadata: { "openclaw": { "emoji": "🕷️",  "requires": { "bins": ["uv", "python3"], "env":["SERPER_API_KEY", "BAIDU_API_KEY"]} } }
---

# qd-browser

Web crawler CLI tool based on Playwright for comprehensive web scraping.

## Features

- **Browser Automation**: Based on Playwright, supports dynamic web pages
- **Content Parsing**: Automatic extraction of main content, metadata, and attachment links
- **Markdown Export**: Convert web content to Markdown format
- **Attachment Download**: Batch download PDF, Word, Excel, and other attachments
- **Search Engine Integration**: Serper + Baidu search, automatic fallback to browser search
- **URL Deduplication**: Global access history, skip visited URLs
- **Auto Domain Subdirectories**: Automatically parse domain from URL as output subdirectory

## Prerequisites

### Dependencies Installation

```bash
# Install dependencies
uv sync

# Install Playwright Chromium browser
uv run playwright install chromium
```

### API Key Configuration (Optional)

For search functionality (`domain-download` and `web-download` commands), configure API keys:

```bash
SERPER_API_KEY=xxx
SERPER_API_KEY_1=xxx
SERPER_API_KEY_2=xxx

BAIDU_API_KEY=xxx
BAIDU_API_KEY_1=xxx
BAIDU_API_KEY_2=xxx
```

When all API keys fail, it will automatically use browser search as fallback.

## Usage

### Basic Usage

```bash
# View help
uv run qd-browser --help

# Crawl single page (auto download attachments, Chinese folders by default)
# Automatically parses domain from URL as subdirectory
uv run qd-browser url-download https://www.example.com

# Specify output directory
uv run qd-browser url-download --output-dir ./my-output https://example.com

# Use English folder naming
uv run qd-browser url-download --language en https://example.com

# Use stable URL hash as filename suffix (consistent across processes)
uv run qd-browser url-download --hash-url https://example.com

# Debug mode
uv run qd-browser url-download --debug https://example.com

# Don't skip visited URLs (force reprocess)
uv run qd-browser url-download --not-skip https://example.com
```

### Commands

#### `url-download` - Crawl single web page and download content (including attachments)

```bash
uv run qd-browser url-download [OPTIONS] URL
```

Automatically parses domain from URL as output subdirectory (e.g., `output/example.com/`).

Options:
- `--output-dir TEXT`: Output directory (default: ./output)
- `--language TEXT`: Language: zh (Chinese) or en (English), affects folder naming (default: zh)
- `--hash-url`: Use stable URL hash (MD5) as filename suffix
- `--debug`: Debug mode, save raw HTML
- `--url-title TEXT`: URL title/description for file naming
- `--not-skip`: Don't skip visited URLs (force reprocess)

#### `domain-download` - Batch crawl via search engine (including attachments)

```bash
uv run qd-browser domain-download <DOMAIN_OR_URL> <SEARCH_KEYWORDS>
```

Discover links under target domain via Serper and Baidu search, then batch crawl.
All results saved to domain-named subdirectory.

Options:
- `--output-dir TEXT`: Output directory (default: ./output)
- `--language TEXT`: Language: zh (Chinese) or en (English), affects folder naming (default: zh)
- `--hash-url`: Use stable URL hash (MD5) as filename suffix
- `--debug`: Debug mode, save raw HTML
- `--not-skip`: Don't skip visited URLs (force reprocess)

#### `web-download` - Web-wide search and batch crawl (including attachments)

```bash
uv run qd-browser web-download <SEARCH_KEYWORDS>
```

Web-wide search (no domain restriction), each URL automatically saved to its corresponding domain subdirectory.

Options:
- `--output-dir TEXT`: Output directory (default: ./output)
- `--language TEXT`: Language: zh (Chinese) or en (English), affects folder naming (default: zh)
- `--hash-url`: Use stable URL hash (MD5) as filename suffix
- `--debug`: Debug mode, save raw HTML
- `--not-skip`: Don't skip visited URLs (force reprocess)

#### `config` - Configuration and history management

```bash
# Show current config
uv run qd-browser config --settings
uv run qd-browser config -s

# History stats
uv run qd-browser config --stats
uv run qd-browser config -t

# List history
uv run qd-browser config --history
uv run qd-browser config -l

# Filter by status
uv run qd-browser config --history --by-status success

# Filter by domain
uv run qd-browser config --history --by-site example.com

# Filter by output directory
uv run qd-browser config --history --by-output-dir ./output

# Filter by URL
uv run qd-browser config --history --by-url https://example.com
uv run qd-browser config --history -c example.com

# Remove URL from history
uv run qd-browser config --remove-url https://example.com
uv run qd-browser config -r https://example.com

# Remove all records for specific domain
uv run qd-browser config --remove-site example.com

# Remove all records for specific output directory
uv run qd-browser config --remove-output-dir ./output

# Remove all records with specific status
uv run qd-browser config --remove-status failed

# Clear all history
uv run qd-browser config --init
```

## Configuration

Can be configured via environment variables with `QD_` prefix:

```bash
QD_OUTPUT_DIR=./my-output
```

Or create `.env` file in project root for configuration.

### URL History

Global URL access history saved at:
- Windows: `C:\Users\USERNAME\.qd_browser\visited.json`
- Linux/Mac: `~/.qd_browser/visited.json`

## Project Structure

```
qd-browser/
├── src/qd_browser/
│   ├── __init__.py          # Package init
│   ├── cli.py               # CLI entry
│   ├── config.py            # Config management
│   ├── browser.py           # Browser management
│   ├── crawler.py           # Crawler core
│   ├── parser.py            # Content parsing
│   ├── downloader.py        # File download
│   ├── utils.py             # Utility functions
│   ├── search.py            # Search functionality
│   └── history.py           # URL history
├── output/                  # Output directory
│   └── attachments/         # Attachment download directory
├── pyproject.toml           # Project config
└── README.md
```

## Tech Stack

- **playwright**: Browser automation
- **typer**: CLI framework
- **beautifulsoup4**: HTML parsing
- **trafilatura**: Web content extraction + HTML to Markdown
- **rich**: Terminal beautification
- **pydantic-settings**: Config management
- **httpx**: HTTP client
- **tldextract**: Domain parsing

## Current Status

Fully functional.
