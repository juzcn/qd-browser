"""配置管理模块"""


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 浏览器配置
    headless: bool = True
    slow_mo: float = 0.0
    browser_timeout: int = 30000

    # 下载配置
    max_concurrent_downloads: int = 5

    # 爬取配置
    user_agent: str | None = None
    default_wait_time: float = 1.0

    # 输出配置
    output_dir: str = "./output"
    save_markdown: bool = True
    debug: bool = False
    language: str = "zh"
    domain: str | None = None
    hash_url: bool = False

    # LLM 配置
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.7
    llm_top_p: float = 0.9

    @property
    def save_html(self) -> bool:
        """是否保存原始 HTML（debug 模式）"""
        return self.debug

    @property
    def base_output_dir(self) -> str:
        """基础输出目录（考虑 domain）"""
        from pathlib import Path

        if self.domain:
            return str(Path(self.output_dir) / self.domain)
        return self.output_dir

    @property
    def download_dir(self) -> str:
        """下载目录（输出目录下的子目录，根据语言命名）"""
        from pathlib import Path

        dir_name = "attachments"
        if self.language == "zh":
            dir_name = "附件"
        return str(Path(self.base_output_dir) / dir_name)

    model_config = {
        "env_prefix": "QD_",
        "env_file": ".env",
        "extra": "ignore",
        "env_exclude": {"debug"},
    }


settings = Settings()
