"""Repositories mapping SQLite rows to domain models. All access goes through these."""

from __future__ import annotations

import json
from typing import Any

from harness.core.domain import (
    Binding,
    Contact,
    Message,
    MessageRole,
    Persona,
    ResolvedBinding,
    Role,
    Run,
    RunMetrics,
    RunStatus,
    SecretRef,
    Session,
    Team,
)
from harness.core.errors import ConflictError, NotFoundError
from harness.core.ids import new_id
from harness.events.model import Event, EventResource
from harness.persistence.db import Database


class SecretRefRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, secret_ref: SecretRef) -> SecretRef:
        if await self._db.fetch_one(
            "SELECT id FROM secret_refs WHERE name = :n", {"n": secret_ref.name}
        ):
            raise ConflictError(f"secret ref name already exists: {secret_ref.name}")
        await self._db.execute(
            "INSERT INTO secret_refs (id, name, kind, target) VALUES (:id, :name, :kind, :target)",
            secret_ref.model_dump(),
        )
        return secret_ref

    async def get(self, secret_ref_id: str) -> SecretRef:
        row = await self._db.fetch_one(
            "SELECT * FROM secret_refs WHERE id = :id", {"id": secret_ref_id}
        )
        if row is None:
            raise NotFoundError(f"secret ref not found: {secret_ref_id}")
        return SecretRef(id=row["id"], name=row["name"], kind=row["kind"], target=row["target"])

    async def list(self) -> list[SecretRef]:
        rows = await self._db.fetch_all("SELECT * FROM secret_refs ORDER BY name")
        return [
            SecretRef(id=r["id"], name=r["name"], kind=r["kind"], target=r["target"]) for r in rows
        ]

    async def delete(self, secret_ref_id: str) -> None:
        await self.get(secret_ref_id)
        await self._db.execute("DELETE FROM secret_refs WHERE id = :id", {"id": secret_ref_id})


class RoleRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, role: Role) -> Role:
        if await self._db.fetch_one("SELECT id FROM roles WHERE name = :n", {"n": role.name}):
            raise ConflictError(f"role name already exists: {role.name}")
        await self._db.execute(
            "INSERT INTO roles (id, name, description, system_prompt, builtin) "
            "VALUES (:id, :name, :description, :system_prompt, :builtin)",
            {**role.model_dump(exclude={"builtin"}), "builtin": int(role.builtin)},
        )
        return role

    async def get(self, role_id: str) -> Role:
        row = await self._db.fetch_one("SELECT * FROM roles WHERE id = :id", {"id": role_id})
        if row is None:
            raise NotFoundError(f"role not found: {role_id}")
        return _role(row)

    async def get_by_name(self, name: str) -> Role | None:
        row = await self._db.fetch_one("SELECT * FROM roles WHERE name = :n", {"n": name})
        return _role(row) if row else None

    async def list(self) -> list[Role]:
        return [_role(r) for r in await self._db.fetch_all("SELECT * FROM roles ORDER BY name")]


class PersonaRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, persona: Persona) -> Persona:
        if await self._db.fetch_one("SELECT id FROM personas WHERE name = :n", {"n": persona.name}):
            raise ConflictError(f"persona name already exists: {persona.name}")
        await self._db.execute(
            "INSERT INTO personas (id, name, description, prompt, precedence, builtin) "
            "VALUES (:id, :name, :description, :prompt, :precedence, :builtin)",
            {**persona.model_dump(exclude={"builtin"}), "builtin": int(persona.builtin)},
        )
        return persona

    async def get(self, persona_id: str) -> Persona:
        row = await self._db.fetch_one("SELECT * FROM personas WHERE id = :id", {"id": persona_id})
        if row is None:
            raise NotFoundError(f"persona not found: {persona_id}")
        return _persona(row)

    async def get_by_name(self, name: str) -> Persona | None:
        row = await self._db.fetch_one("SELECT * FROM personas WHERE name = :n", {"n": name})
        return _persona(row) if row else None

    async def list(self) -> list[Persona]:
        rows = await self._db.fetch_all("SELECT * FROM personas ORDER BY name")
        return [_persona(r) for r in rows]


class ContactRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, contact: Contact) -> Contact:
        if await self._db.fetch_one(
            "SELECT id FROM contacts WHERE handle = :h", {"h": contact.handle}
        ):
            raise ConflictError(f"contact handle already exists: {contact.handle}")
        await self._db.execute(
            "INSERT INTO contacts (id, handle, display_name, role_id, binding_json) "
            "VALUES (:id, :handle, :display_name, :role_id, :binding_json)",
            {
                "id": contact.id,
                "handle": contact.handle,
                "display_name": contact.display_name,
                "role_id": contact.role_id,
                "binding_json": contact.binding.model_dump_json(),
            },
        )
        await self._set_personas(contact.id, contact.persona_ids)
        return contact

    async def update(
        self,
        contact_id: str,
        *,
        display_name: str | None = None,
        role_id: str | None = None,
        binding: Binding | None = None,
        persona_ids: list[str] | None = None,
    ) -> Contact:
        await self.get(contact_id)
        if display_name is not None:
            await self._db.execute(
                "UPDATE contacts SET display_name = :v, updated_at = datetime('now') "
                "WHERE id = :id",
                {"v": display_name, "id": contact_id},
            )
        if role_id is not None:
            await self._db.execute(
                "UPDATE contacts SET role_id = :v, updated_at = datetime('now') WHERE id = :id",
                {"v": role_id, "id": contact_id},
            )
        if binding is not None:
            await self._db.execute(
                "UPDATE contacts SET binding_json = :v, updated_at = datetime('now') "
                "WHERE id = :id",
                {"v": binding.model_dump_json(), "id": contact_id},
            )
        if persona_ids is not None:
            await self._db.execute(
                "DELETE FROM contact_personas WHERE contact_id = :id", {"id": contact_id}
            )
            await self._set_personas(contact_id, persona_ids)
        return await self.get(contact_id)

    async def _set_personas(self, contact_id: str, persona_ids: list[str]) -> None:
        for position, persona_id in enumerate(persona_ids):
            await self._db.execute(
                "INSERT INTO contact_personas (contact_id, persona_id, position) "
                "VALUES (:c, :p, :pos)",
                {"c": contact_id, "p": persona_id, "pos": position},
            )

    async def get(self, contact_id: str) -> Contact:
        row = await self._db.fetch_one("SELECT * FROM contacts WHERE id = :id", {"id": contact_id})
        if row is None:
            raise NotFoundError(f"contact not found: {contact_id}")
        return await self._hydrate(row)

    async def get_by_handle(self, handle: str) -> Contact | None:
        row = await self._db.fetch_one("SELECT * FROM contacts WHERE handle = :h", {"h": handle})
        return await self._hydrate(row) if row else None

    async def list(self) -> list[Contact]:
        rows = await self._db.fetch_all("SELECT * FROM contacts ORDER BY handle")
        return [await self._hydrate(r) for r in rows]

    async def delete(self, contact_id: str) -> None:
        await self.get(contact_id)
        await self._db.execute("DELETE FROM contacts WHERE id = :id", {"id": contact_id})

    async def _hydrate(self, row: Any) -> Contact:
        personas = await self._db.fetch_all(
            "SELECT persona_id FROM contact_personas WHERE contact_id = :id ORDER BY position",
            {"id": row["id"]},
        )
        return Contact(
            id=row["id"],
            handle=row["handle"],
            display_name=row["display_name"],
            role_id=row["role_id"],
            persona_ids=[p["persona_id"] for p in personas],
            binding=Binding.model_validate_json(row["binding_json"]),
        )


class TeamRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, team: Team) -> Team:
        if await self._db.fetch_one("SELECT id FROM teams WHERE handle = :h", {"h": team.handle}):
            raise ConflictError(f"team handle already exists: {team.handle}")
        await self._db.execute(
            "INSERT INTO teams (id, handle, display_name) VALUES (:id, :handle, :display_name)",
            {"id": team.id, "handle": team.handle, "display_name": team.display_name},
        )
        for position, contact_id in enumerate(team.member_ids):
            await self._db.execute(
                "INSERT INTO team_members (team_id, contact_id, position) VALUES (:t, :c, :p)",
                {"t": team.id, "c": contact_id, "p": position},
            )
        return team

    async def get_by_handle(self, handle: str) -> Team | None:
        row = await self._db.fetch_one("SELECT * FROM teams WHERE handle = :h", {"h": handle})
        if row is None:
            return None
        members = await self._db.fetch_all(
            "SELECT contact_id FROM team_members WHERE team_id = :id ORDER BY position",
            {"id": row["id"]},
        )
        return Team(
            id=row["id"],
            handle=row["handle"],
            display_name=row["display_name"],
            member_ids=[m["contact_id"] for m in members],
        )

    async def list(self) -> list[Team]:
        rows = await self._db.fetch_all("SELECT handle FROM teams ORDER BY handle")
        teams = []
        for row in rows:
            team = await self.get_by_handle(row["handle"])
            assert team is not None
            teams.append(team)
        return teams


class SessionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, title: str, contact_ids: list[str]) -> Session:
        session_id = new_id("ses")
        await self._db.execute(
            "INSERT INTO sessions (id, title) VALUES (:id, :title)",
            {"id": session_id, "title": title},
        )
        for contact_id in contact_ids:
            await self.add_member(session_id, contact_id)
        return await self.get(session_id)

    async def add_member(self, session_id: str, contact_id: str) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO session_members (session_id, contact_id) VALUES (:s, :c)",
            {"s": session_id, "c": contact_id},
        )

    async def get(self, session_id: str) -> Session:
        row = await self._db.fetch_one("SELECT * FROM sessions WHERE id = :id", {"id": session_id})
        if row is None:
            raise NotFoundError(f"session not found: {session_id}")
        members = await self._db.fetch_all(
            "SELECT contact_id FROM session_members WHERE session_id = :id", {"id": session_id}
        )
        return Session(
            id=row["id"],
            title=row["title"],
            state=row["state"],
            workspace_id=row["workspace_id"],
            contact_ids=[m["contact_id"] for m in members],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list(self) -> list[Session]:
        rows = await self._db.fetch_all("SELECT id FROM sessions ORDER BY created_at DESC")
        return [await self.get(r["id"]) for r in rows]

    async def update_title(self, session_id: str, title: str) -> Session:
        await self.get(session_id)
        await self._db.execute(
            "UPDATE sessions SET title = :t, updated_at = datetime('now') WHERE id = :id",
            {"t": title, "id": session_id},
        )
        return await self.get(session_id)

    async def delete(self, session_id: str) -> None:
        await self.get(session_id)
        await self._db.execute("DELETE FROM sessions WHERE id = :id", {"id": session_id})

    async def get_member_override(self, session_id: str, contact_id: str) -> Binding | None:
        row = await self._db.fetch_one(
            "SELECT binding_override_json FROM session_members "
            "WHERE session_id = :s AND contact_id = :c",
            {"s": session_id, "c": contact_id},
        )
        if row is None or row["binding_override_json"] is None:
            return None
        return Binding.model_validate_json(row["binding_override_json"])

    async def set_member_override(
        self, session_id: str, contact_id: str, binding: Binding | None
    ) -> None:
        await self._db.execute(
            "UPDATE session_members SET binding_override_json = :b "
            "WHERE session_id = :s AND contact_id = :c",
            {
                "b": binding.model_dump_json() if binding else None,
                "s": session_id,
                "c": contact_id,
            },
        )


class MessageRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        *,
        contact_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(
            id=new_id("msg"),
            session_id=session_id,
            role=role,
            content=content,
            contact_id=contact_id,
            run_id=run_id,
            metadata=metadata or {},
        )
        await self._db.execute(
            "INSERT INTO messages (id, session_id, role, contact_id, run_id, content, "
            "metadata_json) VALUES (:id, :session_id, :role, :contact_id, :run_id, :content, "
            ":metadata_json)",
            {
                **message.model_dump(exclude={"metadata", "created_at"}),
                "metadata_json": json.dumps(message.metadata),
            },
        )
        return message

    async def list_for_session(self, session_id: str, *, limit: int = 500) -> list[Message]:
        rows = await self._db.fetch_all(
            "SELECT * FROM messages WHERE session_id = :s ORDER BY created_at, rowid LIMIT :limit",
            {"s": session_id, "limit": limit},
        )
        return [
            Message(
                id=r["id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                contact_id=r["contact_id"],
                run_id=r["run_id"],
                metadata=json.loads(r["metadata_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]


class RunRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, run: Run) -> Run:
        await self._db.execute(
            "INSERT INTO runs (id, session_id, contact_id, message_id, status, "
            "binding_snapshot_id, correlation_id, parent_run_id) VALUES (:id, "
            ":session_id, :contact_id, :message_id, :status, :binding_snapshot_id, "
            ":correlation_id, :parent_run_id)",
            run.model_dump(exclude={"error", "started_at", "finished_at"}),
        )
        return run

    async def get(self, run_id: str) -> Run:
        row = await self._db.fetch_one("SELECT * FROM runs WHERE id = :id", {"id": run_id})
        if row is None:
            raise NotFoundError(f"run not found: {run_id}")
        return _run(row)

    async def list_for_session(self, session_id: str) -> list[Run]:
        rows = await self._db.fetch_all(
            "SELECT * FROM runs WHERE session_id = :id ORDER BY created_at", {"id": session_id}
        )
        return [_run(r) for r in rows]

    async def set_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
        snapshot_id: str | None = None,
    ) -> None:
        updates = ["status = :status"]
        params: dict[str, Any] = {"status": status, "id": run_id}
        if status == "running":
            updates.append("started_at = datetime('now')")
        if status in ("succeeded", "failed", "canceled"):
            updates.append("finished_at = datetime('now')")
        if error is not None:
            updates.append("error = :error")
            params["error"] = error
        if snapshot_id is not None:
            updates.append("binding_snapshot_id = :snap")
            params["snap"] = snapshot_id
        await self._db.execute(f"UPDATE runs SET {', '.join(updates)} WHERE id = :id", params)

    async def save_snapshot(self, snapshot: ResolvedBinding) -> str:
        snapshot_id = new_id("bnd")
        await self._db.execute(
            "INSERT INTO binding_snapshots (id, snapshot_json) VALUES (:id, :json)",
            {"id": snapshot_id, "json": snapshot.model_dump_json()},
        )
        return snapshot_id

    async def get_snapshot(self, snapshot_id: str) -> ResolvedBinding:
        row = await self._db.fetch_one(
            "SELECT snapshot_json FROM binding_snapshots WHERE id = :id", {"id": snapshot_id}
        )
        if row is None:
            raise NotFoundError(f"binding snapshot not found: {snapshot_id}")
        return ResolvedBinding.model_validate_json(row["snapshot_json"])

    async def save_metrics(self, metrics: RunMetrics) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO run_metrics (run_id, input_tokens, output_tokens, "
            "cached_tokens, context_tokens, ttft_ms, tokens_per_second, duration_ms, "
            "finish_reason, retries, tool_calls, tool_failures, cost_estimate, outcome, "
            "budget_json) VALUES (:run_id, :input_tokens, :output_tokens, :cached_tokens, "
            ":context_tokens, :ttft_ms, :tokens_per_second, :duration_ms, :finish_reason, "
            ":retries, :tool_calls, :tool_failures, :cost_estimate, :outcome, :budget_json)",
            {
                **metrics.model_dump(exclude={"budget"}),
                "budget_json": json.dumps(metrics.budget) if metrics.budget else None,
            },
        )

    async def get_metrics(self, run_id: str) -> RunMetrics | None:
        row = await self._db.fetch_one(
            "SELECT * FROM run_metrics WHERE run_id = :id", {"id": run_id}
        )
        if row is None:
            return None
        data = dict(row)
        budget_json = data.pop("budget_json", None)
        return RunMetrics(**data, budget=json.loads(budget_json) if budget_json else None)


class EventStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def append(self, event: Event) -> Event:
        seq = await self._db.execute_returning_rowid(
            "INSERT INTO events (event_id, type, timestamp, correlation_id, resource_type, "
            "resource_id, context_json, payload_json, payload_version) VALUES (:event_id, "
            ":type, :timestamp, :correlation_id, :resource_type, :resource_id, :context_json, "
            ":payload_json, :payload_version)",
            {
                "event_id": event.event_id,
                "type": event.type,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id,
                "resource_type": event.resource.type if event.resource else None,
                "resource_id": event.resource.id if event.resource else None,
                "context_json": json.dumps(event.context),
                "payload_json": json.dumps(event.payload),
                "payload_version": event.payload_version,
            },
        )
        return event.model_copy(update={"seq": seq})

    async def replay(self, since_seq: int = 0, *, limit: int = 1000) -> list[Event]:
        rows = await self._db.fetch_all(
            "SELECT * FROM events WHERE seq > :since ORDER BY seq LIMIT :limit",
            {"since": since_seq, "limit": limit},
        )
        return [
            Event(
                event_id=r["event_id"],
                type=r["type"],
                timestamp=r["timestamp"],
                correlation_id=r["correlation_id"],
                resource=(
                    EventResource(type=r["resource_type"], id=r["resource_id"])
                    if r["resource_type"]
                    else None
                ),
                context=json.loads(r["context_json"]),
                payload=json.loads(r["payload_json"]),
                payload_version=r["payload_version"],
                seq=r["seq"],
            )
            for r in rows
        ]


def _role(row: Any) -> Role:
    return Role(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        system_prompt=row["system_prompt"],
        builtin=bool(row["builtin"]),
    )


def _persona(row: Any) -> Persona:
    return Persona(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        prompt=row["prompt"],
        precedence=row["precedence"],
        builtin=bool(row["builtin"]),
    )


def _run(row: Any) -> Run:
    return Run(
        id=row["id"],
        session_id=row["session_id"],
        contact_id=row["contact_id"],
        message_id=row["message_id"],
        status=row["status"],
        binding_snapshot_id=row["binding_snapshot_id"],
        correlation_id=row["correlation_id"],
        parent_run_id=row["parent_run_id"],
        error=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
