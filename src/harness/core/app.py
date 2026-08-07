"""Application context: wires persistence, events, providers, and the agent runtime.

One instance is built per process (`create_application`) and threaded through the API,
CLI, and tests. Keeping this in `core` (not `api`) preserves the API-first rule: nothing
here depends on FastAPI, so the TUI or a future client can build the same context.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe

from harness.agents.registry import RunRegistry
from harness.agents.seeds import seed_agents
from harness.artifacts.store import ArtifactBlobStore
from harness.context.compiler import ContextCompiler
from harness.context.tokens import HeuristicEstimator
from harness.core.config import HarnessConfig
from harness.core.domain import Binding
from harness.core.errors import NotFoundError
from harness.core.secrets import SecretStore
from harness.events.bus import EventBus
from harness.events.model import Event
from harness.jobs.manager import JobManager
from harness.persistence.db import Database
from harness.persistence.repos import (
    ContactRepo,
    EventStore,
    MessageRepo,
    PersonaRepo,
    RoleRepo,
    RunRepo,
    SecretRefRepo,
    SessionRepo,
    TeamRepo,
)
from harness.persistence.repos_artifacts import ArtifactRepo
from harness.persistence.repos_context import TranscriptStateRepo
from harness.persistence.repos_control_plane import HostRepo, ModelProfileRepo, ProviderConfigRepo
from harness.persistence.repos_jobs import JobRepo
from harness.persistence.repos_model_instances import ModelInstanceRepo
from harness.persistence.repos_permissions import PermissionDecisionRepo, PermissionPolicyRepo
from harness.persistence.repos_tools import ToolRunRepo
from harness.persistence.repos_workspaces import WorkspaceRepo
from harness.providers.language.base import LanguageProvider
from harness.providers.language.factory import build_provider
from harness.providers.language.fake import FakeProvider
from harness.providers.language.registry import ProviderRegistry
from harness.tools.builtin import echo_tool
from harness.tools.lifecycle import ToolExecutor
from harness.tools.permission_engine import PermissionEngine
from harness.tools.registry import ToolRegistry
from harness.tools.workspace_tools import register_workspace_tools

# System-default binding when no contact/role override applies. The fake provider is
# always registered so the server is usable with zero external configuration.
SYSTEM_DEFAULT_BINDING = Binding(provider="fake", model="fake-mini")


@dataclass
class Application:
    config: HarnessConfig
    db: Database
    bus: EventBus
    events: EventStore
    roles: RoleRepo
    personas: PersonaRepo
    contacts: ContactRepo
    teams: TeamRepo
    sessions: SessionRepo
    messages: MessageRepo
    runs: RunRepo
    secret_refs: SecretRefRepo
    secret_store: SecretStore
    jobs: JobRepo
    job_manager: JobManager
    provider_configs: ProviderConfigRepo
    hosts: HostRepo
    workspaces: WorkspaceRepo
    model_profiles: ModelProfileRepo
    model_instances: ModelInstanceRepo
    providers: ProviderRegistry
    tools: ToolRegistry
    tool_runs: ToolRunRepo
    tool_executor: ToolExecutor
    permission_policies: PermissionPolicyRepo
    permission_decisions: PermissionDecisionRepo
    permission_engine: PermissionEngine
    artifacts: ArtifactRepo
    artifact_blobs: ArtifactBlobStore
    transcript_state: TranscriptStateRepo
    run_registry: RunRegistry
    compiler: ContextCompiler
    api_token: str
    system_binding: Binding = field(default_factory=lambda: SYSTEM_DEFAULT_BINDING)

    async def publish(self, event: Event) -> Event:
        return await self.bus.publish(event)

    async def get_or_build_provider(self, provider_config_id: str) -> LanguageProvider:
        """Return the live adapter for a persisted provider config, building and
        registering it on first use. Secrets are resolved just-in-time, never cached
        in a form callers could read back (SPEC/SECURITY_PRIVACY.md).
        """
        try:
            return self.providers.get(provider_config_id)
        except NotFoundError:
            pass
        config = await self.provider_configs.get(provider_config_id)
        secret_value = None
        if config.secret_ref_id:
            secret_ref = await self.secret_refs.get(config.secret_ref_id)
            secret_value = self.secret_store.get(secret_ref.kind, secret_ref.target)
        provider = build_provider(config, secret_value)
        self.providers.register(provider)
        return provider

    async def close(self) -> None:
        await self.db.close()


def _load_or_create_token(data_dir: Path) -> str:
    token_path = data_dir / "api_token"
    if token_path.exists():
        return token_path.read_text().strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    token = token_urlsafe(32)
    token_path.write_text(token)
    os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)
    return token


async def create_application(config: HarnessConfig | None = None) -> Application:
    config = config or HarnessConfig()
    db_path: str
    if config.ui.demo_mode:
        db_path = ":memory:"
        token = "demo-mode-token"
    else:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(config.data_dir / "harness.sqlite3")
        token = _load_or_create_token(config.data_dir)

    db = Database(db_path)
    await db.migrate()

    event_store = EventStore(db)

    async def persist(event: Event) -> Event:
        return await event_store.append(event)

    bus = EventBus(persist=persist)

    roles = RoleRepo(db)
    personas = PersonaRepo(db)
    contacts = ContactRepo(db)
    teams = TeamRepo(db)
    sessions = SessionRepo(db)
    messages = MessageRepo(db)
    runs = RunRepo(db)
    secret_refs = SecretRefRepo(db)
    secret_store = SecretStore(config.data_dir)
    jobs = JobRepo(db)
    job_manager = JobManager(repo=jobs, bus=bus)
    provider_configs = ProviderConfigRepo(db)
    hosts = HostRepo(db)
    workspaces = WorkspaceRepo(db)
    model_profiles = ModelProfileRepo(db)
    model_instances = ModelInstanceRepo(db)

    await seed_agents(roles, personas)

    providers = ProviderRegistry()
    providers.register(FakeProvider())

    permission_policies = PermissionPolicyRepo(db)
    permission_decisions = PermissionDecisionRepo(db)
    permission_engine = PermissionEngine(permission_policies, permission_decisions)

    tools = ToolRegistry()
    tools.register(echo_tool())
    register_workspace_tools(tools, workspaces, hosts, secret_refs, secret_store)
    tool_runs = ToolRunRepo(db)
    tool_executor = ToolExecutor(tools, tool_runs, bus, permission_engine)

    artifacts = ArtifactRepo(db)
    artifact_blobs = ArtifactBlobStore(config.data_dir / "artifacts")
    transcript_state = TranscriptStateRepo(db)
    run_registry = RunRegistry()

    compiler = ContextCompiler(HeuristicEstimator(), config.context)

    return Application(
        config=config,
        db=db,
        bus=bus,
        events=event_store,
        roles=roles,
        personas=personas,
        contacts=contacts,
        teams=teams,
        sessions=sessions,
        messages=messages,
        runs=runs,
        secret_refs=secret_refs,
        secret_store=secret_store,
        jobs=jobs,
        job_manager=job_manager,
        provider_configs=provider_configs,
        hosts=hosts,
        workspaces=workspaces,
        model_profiles=model_profiles,
        model_instances=model_instances,
        providers=providers,
        tools=tools,
        tool_runs=tool_runs,
        tool_executor=tool_executor,
        permission_policies=permission_policies,
        permission_decisions=permission_decisions,
        permission_engine=permission_engine,
        artifacts=artifacts,
        artifact_blobs=artifact_blobs,
        transcript_state=transcript_state,
        run_registry=run_registry,
        compiler=compiler,
        api_token=token,
    )
