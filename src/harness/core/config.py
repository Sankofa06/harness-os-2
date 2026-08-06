"""Configuration with explicit precedence: CLI/init kwargs > env (HARNESS_*) > YAML > defaults.

Mirrors CONFIG/examples/harness.example.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

_CONFIG_FILE_ENV = "HARNESS_CONFIG_FILE"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 4096


class AuthConfig(BaseModel):
    # Loopback clients may skip the bearer token when local_trust is true (DECISIONS.md D-005).
    # Non-loopback clients always require the token.
    local_trust: bool = True


class ContextConfig(BaseModel):
    default_budget_tokens: int = 8192
    bootstrap_target_tokens: int = 4096
    full_capability_soft_limit_tokens: int = 16384
    lazy_tools: bool = True
    lazy_skills: bool = True
    lazy_mcp: bool = True
    # How much of the budget a single compile may give to conversation history.
    history_fraction: float = 0.5


class RoutingConfig(BaseModel):
    automatic_placement: bool = False
    prefer_loaded_models: bool = True


class SecurityConfig(BaseModel):
    telemetry_export: bool = False
    remote_workspace_roots_required: bool = True
    # Origins allowed to call the API cross-origin (e.g. the WebUI dev server, which
    # runs on a different port than `harness serve`). Empty in production builds that
    # serve the WebUI from the same origin as the API.
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )


class UiConfig(BaseModel):
    demo_mode: bool = False


def default_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "harness"


class HarnessConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    data_dir: Path = Field(default_factory=default_data_dir)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file = os.environ.get(_CONFIG_FILE_ENV)
        yaml_source = YamlConfigSettingsSource(
            settings_cls, yaml_file=Path(yaml_file) if yaml_file else None
        )
        return (init_settings, env_settings, dotenv_settings, yaml_source)


def load_config(
    config_file: Path | None = None, overrides: dict[str, Any] | None = None
) -> HarnessConfig:
    """Load configuration. ``overrides`` (e.g. CLI flags) take highest precedence."""
    previous = os.environ.get(_CONFIG_FILE_ENV)
    if config_file is not None:
        os.environ[_CONFIG_FILE_ENV] = str(config_file)
    try:
        config = HarnessConfig(**(overrides or {}))
    finally:
        if config_file is not None:
            if previous is None:
                os.environ.pop(_CONFIG_FILE_ENV, None)
            else:
                os.environ[_CONFIG_FILE_ENV] = previous
    # SPEC/UI_UX.md names the demo switch HARNESS_DEMO_MODE.
    if os.environ.get("HARNESS_DEMO_MODE") in {"1", "true", "yes"}:
        config.ui.demo_mode = True
    return config
