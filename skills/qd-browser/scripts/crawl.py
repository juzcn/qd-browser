#!/usr/bin/env python3
"""qd-browser skill wrapper - directly calls the qd-browser CLI"""

import json
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python crawl.py <JSON>"}))
        return 1

    try:
        args = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON"}))
        return 1

    command = args.get("command", "url-download")
    url = args.get("url")
    query = args.get("query")
    domain = args.get("domain")
    output_dir = args.get("output_dir", "./output")
    language = args.get("language", "zh")
    debug = args.get("debug", False)
    not_skip = args.get("not_skip", False)
    hash_url = args.get("hash_url", False)
    url_title = args.get("url_title")

    # Build command
    cmd = ["uv", "run", "qd-browser", command]

    if command == "url-download":
        if not url:
            print(json.dumps({"error": "url required for url-download"}))
            return 1
        cmd.append(url)
    elif command == "domain-download":
        if not domain or not query:
            print(json.dumps({"error": "domain and query required for domain-download"}))
            return 1
        cmd.append(domain)
        cmd.append(query)
    elif command == "web-download":
        if not query:
            print(json.dumps({"error": "query required for web-download"}))
            return 1
        cmd.append(query)
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        return 1

    # Add options
    cmd.extend(["--output-dir", output_dir])
    cmd.extend(["--language", language])
    if hash_url:
        cmd.append("--hash-url")
    if debug:
        cmd.append("--debug")
    if not_skip:
        cmd.append("--not-skip")
    if url_title and command == "url-download":
        cmd.extend(["--url-title", url_title])

    # Run from project root
    project_root = Path(__file__).parent.parent.parent
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        print(json.dumps({
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }, ensure_ascii=False))
        return result.returncode
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
