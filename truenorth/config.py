import os
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class LLMProvider(StrEnum):
    ANTHROPIC = "ANTHROPIC"
    LOCAL = "LOCAL"


class EmbeddingsProvider(StrEnum):
    LOCAL = "LOCAL"


class AutonomyMode(StrEnum):
    NOTIFY_ONLY = "NOTIFY_ONLY"
    AUTONOMOUS = "AUTONOMOUS"


class TradingMode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class LLMConfig(BaseModel):
    provider: LLMProvider
    model: str
    max_tokens: int = Field(gt=0)


class EmbeddingsConfig(BaseModel):
    provider: EmbeddingsProvider


class ExperimentsConfig(BaseModel):
    primary: str
    additional: list[str] = []

    @property
    def all_prompts(self) -> list[str]:
        return [self.primary] + self.additional


class ExecutionConfig(BaseModel):
    autonomy: AutonomyMode
    trading: TradingMode


class RiskConfig(BaseModel):
    max_position_pct: float = Field(gt=0, le=1)
    min_position_pct: float = Field(gt=0, le=1)
    max_daily_buys: int = Field(gt=0)
    buy_threshold: float = Field(ge=-1, le=1)
    sell_threshold: float = Field(ge=-1, le=1)
    entry_update_threshold: float = Field(
        gt=0, le=1
    )  # cancel and reissue pending buy if suggested entry differs by more than this fraction
    target_update_threshold: float = Field(
        gt=0, le=1
    )  # cancel and reissue take-profit if suggested target differs by more than this fraction
    max_entry_discount: float = Field(gt=0, le=1)  # skip buy if model's suggested entry is more than this fraction below last price

    @model_validator(mode="after")
    def sell_below_buy(self) -> "RiskConfig":
        if self.sell_threshold >= self.buy_threshold:
            raise ValueError("sell_threshold must be less than buy_threshold")
        return self


class Config(BaseModel):
    # from .env
    database_url: str
    alpaca_api_key: str
    alpaca_secret_key: str
    massive_api_key: str
    anthropic_api_key: str | None
    langfuse_public_key: str | None
    langfuse_secret_key: str | None

    # from config.yaml
    llm: LLMConfig
    embeddings: EmbeddingsConfig
    execution: ExecutionConfig
    experiments: ExperimentsConfig
    risk: RiskConfig

    @model_validator(mode="after")
    def anthropic_key_required_for_anthropic_provider(self) -> "Config":
        if self.llm.provider == LLMProvider.ANTHROPIC and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when llm.provider is ANTHROPIC")
        return self


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _env(key: str) -> str:
    value = os.environ.get(key)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def _env_optional(key: str) -> str | None:
    return os.environ.get(key)


def load_config(config_path: Path) -> Config:
    y = _load_yaml(config_path)

    return Config(
        database_url=_env("DATABASE_URL"),
        alpaca_api_key=_env("ALPACA_API_KEY"),
        alpaca_secret_key=_env("ALPACA_SECRET_KEY"),
        massive_api_key=_env("MASSIVE_API_KEY"),
        anthropic_api_key=_env_optional("ANTHROPIC_API_KEY"),
        langfuse_public_key=_env_optional("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=_env_optional("LANGFUSE_SECRET_KEY"),
        llm=LLMConfig(**y["llm"]),
        embeddings=EmbeddingsConfig(**y["embeddings"]),
        execution=ExecutionConfig(**y["execution"]),
        experiments=ExperimentsConfig(**y["experiments"]),
        risk=RiskConfig(**y["risk_management"]),
    )
