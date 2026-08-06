from pathlib import Path

from harness.core.config import HarnessConfig, load_config


def test_defaults_match_spec_example() -> None:
    config = HarnessConfig()
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 4096
    assert config.context.default_budget_tokens == 8192
    assert config.context.bootstrap_target_tokens == 4096
    assert config.context.full_capability_soft_limit_tokens == 16384
    assert config.routing.automatic_placement is False
    assert config.security.telemetry_export is False


def test_env_overrides_defaults(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_SERVER__PORT", "9000")
    config = HarnessConfig()
    assert config.server.port == 9000


def test_init_kwargs_override_env(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_SERVER__PORT", "9000")
    config = HarnessConfig(server={"port": 1234})
    assert config.server.port == 1234


def test_yaml_file_loads_and_is_overridden_by_env(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "harness.yaml"
    config_file.write_text("server:\n  port: 5555\n")
    monkeypatch.delenv("HARNESS_SERVER__PORT", raising=False)
    config = load_config(config_file=config_file)
    assert config.server.port == 5555

    monkeypatch.setenv("HARNESS_SERVER__PORT", "6666")
    config = load_config(config_file=config_file)
    assert config.server.port == 6666


def test_demo_mode_env_flag(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_DEMO_MODE", "1")
    config = load_config()
    assert config.ui.demo_mode is True
