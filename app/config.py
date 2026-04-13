from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Lima Learning"
    environment: str = "development"
    port: int = 8080
    memory_db_path: str = "./data/lima_memory.db"
    memory_database_url: str | None = None
    worker_poll_seconds: int = 15
    auto_step_limit_per_tick: int = 1
    manager_backend: str = "rules"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 60
    executor_backend: str = "mock"
    aristotle_base_url: str | None = None
    aristotle_api_key: str | None = None
    aristotle_timeout_seconds: int = 120
    strict_live_aristotle: bool = False
    enable_self_improvement: bool = False
    public_base_url: str | None = None
    log_level: str = "INFO"
    operator_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        memory_db_path = os.getenv("MEMORY_DB_PATH", cls.memory_db_path)
        Path(memory_db_path).parent.mkdir(parents=True, exist_ok=True)
        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            environment=os.getenv("ENVIRONMENT", cls.environment),
            port=int(os.getenv("PORT", str(cls.port))),
            memory_db_path=memory_db_path,
            memory_database_url=os.getenv("MEMORY_DATABASE_URL") or None,
            worker_poll_seconds=int(
                os.getenv("WORKER_POLL_SECONDS", str(cls.worker_poll_seconds))
            ),
            auto_step_limit_per_tick=int(
                os.getenv(
                    "AUTO_STEP_LIMIT_PER_TICK", str(cls.auto_step_limit_per_tick)
                )
            ),
            manager_backend=os.getenv("MANAGER_BACKEND", cls.manager_backend),
            llm_base_url=os.getenv("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=os.getenv("LLM_API_KEY") or None,
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            llm_temperature=float(
                os.getenv("LLM_TEMPERATURE", str(cls.llm_temperature))
            ),
            llm_timeout_seconds=int(
                os.getenv("LLM_TIMEOUT_SECONDS", str(cls.llm_timeout_seconds))
            ),
            executor_backend=os.getenv("EXECUTOR_BACKEND", cls.executor_backend),
            aristotle_base_url=os.getenv("ARISTOTLE_BASE_URL") or None,
            aristotle_api_key=os.getenv("ARISTOTLE_API_KEY") or None,
            aristotle_timeout_seconds=int(
                os.getenv("ARISTOTLE_TIMEOUT_SECONDS", str(cls.aristotle_timeout_seconds))
            ),
            strict_live_aristotle=os.getenv("STRICT_LIVE_ARISTOTLE", "").lower() == "true",
            enable_self_improvement=os.getenv("ENABLE_SELF_IMPROVEMENT", "").lower() == "true",
            public_base_url=os.getenv("PUBLIC_BASE_URL") or None,
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            operator_api_key=os.getenv("OPERATOR_API_KEY") or None,
        )

    @property
    def manager_backend_resolved(self) -> str:
        if self.manager_backend == "llm" and self.llm_api_key:
            return "llm"
        if self.manager_backend == "llm" and not self.llm_api_key:
            return "rules"
        return self.manager_backend
