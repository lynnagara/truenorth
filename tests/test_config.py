from pathlib import Path

from truenorth.config import (
    AutonomyMode,
    EmbeddingsProvider,
    LLMProvider,
    TradingMode,
    load_config,
)

ENV_EXAMPLE = Path(__file__).parent.parent / ".env.example"
CONFIG_EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


def _load_env_file(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def test_load_config(monkeypatch):
    for key, value in _load_env_file(ENV_EXAMPLE).items():
        monkeypatch.setenv(key, value)

    config = load_config(config_path=CONFIG_EXAMPLE)

    assert config.database_url == "postgresql://truenorth:truenorth@localhost:5432/truenorth"

    assert config.llm.provider == LLMProvider.LOCAL
    assert config.llm.model == "llama3.2"
    assert config.llm.max_tokens == 2000

    assert config.embeddings.provider == EmbeddingsProvider.LOCAL

    assert config.execution.autonomy == AutonomyMode.NOTIFY_ONLY
    assert config.execution.trading == TradingMode.PAPER

    assert config.risk.max_position_pct == 0.10
    assert config.risk.min_position_pct == 0.03
    assert config.risk.max_daily_buys == 5
    assert config.risk.buy_threshold == 0.65
