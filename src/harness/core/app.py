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

from harness.agents.seeds import seed_agents
from harness.context.compiler import ContextCompiler
from harness.context.tokens import HeuristicEstimator
from harness.core.config import HarnessConfig
from harness.core.domain import Binding
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
from harness.persistence.repos_jobs import JobRepo
from harness.providers.language.fake import FakeProvider
from harness.providers.language.registry import ProviderRegistry

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
    providers: ProviderRegistry
    compiler: ContextCompiler
    api_token: str
    system_binding: Binding = field(default_factory=lambda: SYSTEM_DEFAULT_BINDING)

    async def publish(self, event: Event) -> Event:
        return await self.bus.publish(event)

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

    await seed_agents(roles, personas)

    providers = ProviderRegistry()
    providers.register(FakeProvider())

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
        providers=providers,
        compiler=compiler,
        api_token=token,
    )
