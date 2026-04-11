"""LLM 模块 - 使用 NVIDIA 免费模型"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import dotenv
from openai import OpenAI
from rich.console import Console

from .config import settings
from .utils import clean_filename

console = Console()

# 爬取任务识别的系统提示词
CRAWL_TASK_SYSTEM_PROMPT = """我们有一个网页爬取工具，可以从指定的域名网站，通过搜索引擎发现相关链接并批量爬取网页内容。

你的任务是分析用户的请求，判断是否需要使用这个爬取工具。

## 如果用户想要搜索和下载网页资料，提取以下信息并以严格的 JSON 格式返回：
{
    "is_crawl_task": true,
    "domains": ["域名1", "域名2", ...],
    "query": "搜索关键词",
    "output_dir": "输出目录或 null"
}

## 如果用户只是想让你直接生成内容（写文章、写诗、写代码等），返回：
{
    "is_crawl_task": false
}

## 重要要求：

1. **domains（域名列表 - 必须输出，不能为空！
   - 根据用户的需求，结合你的知识，推荐合适的域名
   - 例如：用户要找 ESG 资料，推荐：["sasb.org", "globalreporting.org", "ifrs.org"
   - 只提取主域名（如 example.com，不要带 www 或 http）
   - 至少提供 1 个域名，推荐 2-5 个域名

2. **query搜索关键词 - 必须输出！**
   - 简洁明了的搜索关键词
   - 例如："ESG 官方指南"、"企业社会责任报告"

3. **output_dir输出目录 - 可选**
   - 如果用户明确指定了保存位置，输出目录路径
   - 如果用户没有说，设为 null

## 只返回 JSON，不要有其他任何文字说明！"""

# 模型优先级排序规则（用于对获取到的模型进行排序）
MODEL_PRIORITY = {
    # Llama 3.1 系列（最强）
    "llama-3.1-405b": 1,
    "llama-3.1-70b": 2,
    "llama-3.1-8b": 3,
    # Llama 3 系列
    "llama-3-70b": 4,
    "llama-3-8b": 5,
    # Mistral 系列
    "mistral-large": 6,
    "mixtral-8x7b": 7,
    # Qwen 系列（中文优化）
    "qwen2.5-72b": 8,
    "qwen2.5-32b": 9,
    # Gemma 系列
    "gemma-2-27b": 10,
    "gemma-2-9b": 11,
}


def get_model_priority(model_id: str) -> int:
    """获取模型的优先级分数

    Args:
        model_id: 模型 ID，如 "meta/llama-3.1-405b-instruct"

    Returns:
        优先级分数，数字越小优先级越高
    """
    for key, priority in MODEL_PRIORITY.items():
        if key in model_id:
            return priority
    # 未知模型，给一个较低的优先级
    return 100


def load_env() -> None:
    """加载 .env 文件（如果存在）"""
    dotenv.load_dotenv(override=True)


class NVIDIALLM:
    """NVIDIA LLM 客户端，支持模型池 fallback"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_pool: list[str] | None = None,
    ):
        """初始化 NVIDIA LLM 客户端

        Args:
            api_key: NVIDIA API Key，默认从环境变量 NVAPI_KEY 读取
            base_url: NVIDIA API Base URL，默认从环境变量 NVIDIA_BASE_URL 读取
            model_pool: 模型池列表，按优先级排序
        """
        load_env()

        self.api_key = api_key or os.getenv("NVAPI_KEY")
        self.base_url = base_url or os.getenv(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )

        if not self.api_key:
            raise ValueError(
                "NVIDIA API Key 未设置，请设置 NVAPI_KEY 环境变量或在 .env 文件中配置"
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # 如果没有指定 model_pool，则动态从 NVIDIA API 获取
        if model_pool is None:
            self.model_pool = self.fetch_available_models()
        else:
            self.model_pool = model_pool

    def fetch_available_models(self, max_models: int = 5) -> list[str]:
        """从 NVIDIA API 获取当前可用的 chat 类型模型

        Args:
            max_models: 最多返回的模型数量

        Returns:
            按优先级排序的模型 ID 列表
        """
        try:
            console.print("[blue]正在从 NVIDIA API 获取可用模型列表...[/blue]")
            models = self.client.models.list()

            # 筛选支持 chat 的模型
            chat_models = []
            for model in models.data:
                model_id = model.id
                # 只保留 instruct 或 chat 类型的模型
                if any(keyword in model_id.lower() for keyword in ["instruct", "chat"]):
                    chat_models.append(model_id)

            # 按优先级排序
            chat_models.sort(key=get_model_priority)

            # 取前 max_models 个
            result = chat_models[:max_models]

            console.print(f"[green]获取到 {len(result)} 个可用模型:[/green]")
            for i, model in enumerate(result, 1):
                console.print(f"  [cyan]{i}.[/cyan] {model}")

            return result

        except Exception as e:
            console.print(f"[yellow]从 NVIDIA API 获取模型列表失败: {e}[/yellow]")
            console.print("[yellow]使用备用模型列表[/yellow]")
            # 返回备用模型列表
            fallback_models = [
                "meta/llama-3.1-405b-instruct",
                "meta/llama-3.1-70b-instruct",
                "meta/llama-3.1-8b-instruct",
                "meta/llama-3-70b-instruct",
                "meta/llama-3-8b-instruct",
            ]
            console.print(f"[yellow]备用模型列表: {fallback_models}[/yellow]")
            return fallback_models

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> dict[str, Any]:
        """使用模型池生成内容，支持自动 fallback

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            top_p: top_p 参数

        Returns:
            包含生成结果的字典
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error: Exception | None = None

        for model in self.model_pool:
            try:
                console.print(f"[blue]尝试使用模型: {model}[/blue]")

                completion = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )

                result = {
                    "model": model,
                    "content": completion.choices[0].message.content,
                    "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                    "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                    "total_tokens": completion.usage.total_tokens if completion.usage else 0,
                    "success": True,
                }

                console.print(f"[green]成功使用模型: {model}[/green]")
                return result

            except Exception as e:
                last_error = e
                console.print(f"[yellow]模型 {model} 调用失败: {e}[/yellow]")
                console.print(f"[yellow]尝试下一个模型...[/yellow]")
                continue

        # 所有模型都失败
        error_msg = f"所有模型都调用失败。最后一个错误: {last_error}"
        console.print(f"[red]{error_msg}[/red]")
        return {
            "model": None,
            "content": None,
            "error": str(last_error) if last_error else "Unknown error",
            "success": False,
        }


def parse_crawl_task(prompt: str, llm_client: NVIDIALLM) -> dict[str, Any]:
    """使用 LLM 分析提示词，判断是否是爬取任务并提取信息

    Args:
        prompt: 用户提示词
        llm_client: NVIDIALLM 客户端实例

    Returns:
        包含解析结果的字典
    """
    result = llm_client.generate(
        prompt=prompt,
        system_prompt=CRAWL_TASK_SYSTEM_PROMPT,
        max_tokens=1000,
        temperature=0.1,
        top_p=0.9,
    )

    if not result.get("success"):
        return {"is_crawl_task": False, "error": result.get("error")}

    content = result.get("content", "")
    if not content:
        return {"is_crawl_task": False}

    # 调试输出 LLM 返回内容
    console.print(f"[blue]LLM 返回内容:[/blue]")
    console.print(content)
    console.print()

    # 尝试提取 JSON
    try:
        # 查找 JSON 部分
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            json_str = json_match.group(0)
            console.print(f"[blue]提取到 JSON: {json_str}[/blue]")
            parsed = json.loads(json_str)

            # 验证并确保数据完整性
            if parsed.get("is_crawl_task"):
                # 确保 domains 是列表且不为空
                domains = parsed.get("domains", [])
                if not isinstance(domains, list):
                    domains = [domains] if domains else []
                parsed["domains"] = domains

                # 确保 query 存在
                if not parsed.get("query"):
                    parsed["query"] = prompt

                console.print(f"[green]解析结果:[/green]")
                console.print(f"  domains: {parsed.get('domains')}")
                console.print(f"  query: {parsed.get('query')}")
                console.print(f"  output_dir: {parsed.get('output_dir')}")

            return parsed
    except Exception as e:
        console.print(f"[yellow]解析爬取任务信息失败: {e}[/yellow]")
        console.print(f"[yellow]LLM 返回内容: {content}[/yellow]")

    return {"is_crawl_task": False}


def save_llm_result(
    result: dict[str, Any],
    output_dir: str | Path,
    prompt: str,
    filename_prefix: str | None = None,
) -> Path:
    """保存 LLM 生成结果到文件

    Args:
        result: generate() 返回的结果
        output_dir: 输出目录
        prompt: 原始提示词
        filename_prefix: 文件名前缀（可选）

    Returns:
        保存的文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if filename_prefix:
        base_name = clean_filename(filename_prefix, max_length=50)
    else:
        # 使用 prompt 的前 30 个字符作为文件名
        prompt_preview = prompt[:30].strip()
        base_name = clean_filename(prompt_preview, max_length=50) or "llm_output"

    filename = f"{base_name}_{timestamp}.md"
    filepath = output_path / filename

    # 构建文件内容
    content = []
    content.append(f"# LLM 生成结果\n")
    content.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append(f"\n**使用模型**: {result.get('model', 'N/A')}")

    if result.get("total_tokens"):
        content.append(f"\n**Token 使用**:")
        content.append(f"- Prompt: {result.get('prompt_tokens', 0)}")
        content.append(f"- Completion: {result.get('completion_tokens', 0)}")
        content.append(f"- Total: {result.get('total_tokens', 0)}")

    content.append(f"\n---\n")
    content.append(f"\n## 提示词\n")
    content.append(prompt)
    content.append(f"\n---\n")
    content.append(f"\n## 生成内容\n")

    if result.get("success") and result.get("content"):
        content.append(result["content"])
    else:
        content.append(f"**生成失败**: {result.get('error', 'Unknown error')}")

    filepath.write_text("\n".join(content), encoding="utf-8")
    return filepath


def llm_download(
    prompt: str,
    output_dir: str = "./output",
    model_pool: list[str] | None = None,
    language: str = "zh",
    crawl_task_callback: Any | None = None,
) -> dict[str, Any]:
    """LLM 下载命令的核心逻辑

    Args:
        prompt: 用户提示词
        output_dir: 输出目录
        model_pool: 自定义模型池（可选）
        language: 语言设置
        crawl_task_callback: 爬取任务回调函数，如果是爬取任务则调用此函数

    Returns:
        包含结果的字典
    """
    # 设置全局配置
    settings.output_dir = output_dir
    settings.language = language

    console.print()
    console.print("[blue]========== LLM 处理 ==========[/blue]")
    console.print(f"提示词: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    console.print()

    # 初始化 LLM 客户端
    llm = NVIDIALLM(model_pool=model_pool)

    # 首先判断是否是爬取任务
    console.print("[blue]正在分析任务类型...[/blue]")
    crawl_info = parse_crawl_task(prompt, llm)

    # 如果是爬取任务且有回调函数，执行爬取
    if crawl_info.get("is_crawl_task") and crawl_task_callback:
        console.print("[green]检测到爬取任务！[/green]")
        console.print(f"[cyan]域名: {crawl_info.get('domains', [])}[/cyan]")
        console.print(f"[cyan]搜索关键词: {crawl_info.get('query', '')}[/cyan]")
        if crawl_info.get("output_dir"):
            console.print(f"[cyan]输出目录: {crawl_info.get('output_dir')}[/cyan]")

        # 调用回调执行爬取
        result = crawl_task_callback(
            crawl_info=crawl_info,
            output_dir=output_dir,
            language=language,
        )
        return result

    # 否则执行普通内容生成
    console.print("[blue]执行普通内容生成...[/blue]")
    result = llm.generate(
        prompt=prompt,
        system_prompt=None,
        max_tokens=4096,
        temperature=0.7,
        top_p=0.9,
    )

    # 保存结果
    if result.get("success"):
        filepath = save_llm_result(
            result=result,
            output_dir=output_dir,
            prompt=prompt,
            filename_prefix=None,
        )
        result["saved_path"] = filepath

        console.print()
        console.print(f"[green]结果已保存到: {filepath}[/green]")

        # 显示内容预览
        content = result.get("content", "")
        if content:
            console.print()
            console.print("[blue]内容预览:[/blue]")
            preview = content[:500]
            console.print(preview)
            if len(content) > 500:
                console.print("[yellow]...[/yellow]")

    return result
