import pytest

from harness.core.domain import Binding, Contact, Persona, Role, Run
from harness.core.errors import ConflictError, NotFoundError
from harness.core.ids import new_id
from harness.persistence.repos import ContactRepo, MessageRepo, RoleRepo, RunRepo, SessionRepo


@pytest.mark.asyncio
async def test_contact_identity_survives_binding_change(db) -> None:
    contacts = ContactRepo(db)
    roles = RoleRepo(db)
    role = await roles.create(Role(id=new_id("role"), name="coder"))
    contact = await contacts.create(
        Contact(
            id=new_id("con"),
            handle="builder",
            display_name="Builder",
            role_id=role.id,
            binding=Binding(provider="fake", model="fake-mini"),
        )
    )

    updated = await contacts.update(contact.id, binding=Binding(provider="openai", model="gpt-x"))

    assert updated.id == contact.id
    assert updated.handle == contact.handle
    assert updated.binding.provider == "openai"


@pytest.mark.asyncio
async def test_contact_handle_must_be_unique(db) -> None:
    contacts = ContactRepo(db)
    await contacts.create(Contact(id=new_id("con"), handle="dup", display_name="A"))
    with pytest.raises(ConflictError):
        await contacts.create(Contact(id=new_id("con"), handle="dup", display_name="B"))


@pytest.mark.asyncio
async def test_contact_not_found(db) -> None:
    contacts = ContactRepo(db)
    with pytest.raises(NotFoundError):
        await contacts.get("con_missing")


@pytest.mark.asyncio
async def test_session_and_message_round_trip(db) -> None:
    contacts = ContactRepo(db)
    contact = await contacts.create(Contact(id=new_id("con"), handle="reviewer", display_name="R"))
    sessions = SessionRepo(db)
    session = await sessions.create("demo", [contact.id])
    assert session.contact_ids == [contact.id]

    messages = MessageRepo(db)
    await messages.create(session.id, "user", "hello")
    await messages.create(session.id, "assistant", "hi", contact_id=contact.id)
    history = await messages.list_for_session(session.id)
    assert [m.role for m in history] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_run_status_transitions_and_snapshot(db) -> None:
    contacts = ContactRepo(db)
    contact = await contacts.create(Contact(id=new_id("con"), handle="tester", display_name="T"))
    sessions = SessionRepo(db)
    session = await sessions.create("s", [contact.id])
    runs = RunRepo(db)
    run = await runs.create(Run(id=new_id("run"), session_id=session.id, contact_id=contact.id))
    assert run.status == "queued"

    from harness.core.domain import ResolvedBinding

    snapshot_id = await runs.save_snapshot(
        ResolvedBinding(provider="fake", model="fake-mini", sources={"model": "system"})
    )
    await runs.set_status(run.id, "running", snapshot_id=snapshot_id)
    fetched = await runs.get(run.id)
    assert fetched.status == "running"
    assert fetched.binding_snapshot_id == snapshot_id

    snapshot = await runs.get_snapshot(snapshot_id)
    assert snapshot.model == "fake-mini"

    await runs.set_status(run.id, "succeeded")
    fetched = await runs.get(run.id)
    assert fetched.status == "succeeded"
    assert fetched.finished_at is not None


@pytest.mark.asyncio
async def test_persona_stacking_precedence_deterministic(db) -> None:
    from harness.persistence.repos import PersonaRepo

    personas = PersonaRepo(db)
    a = await personas.create(Persona(id=new_id("per"), name="a", precedence=50))
    b = await personas.create(Persona(id=new_id("per"), name="b", precedence=200))
    fetched = await personas.list()
    assert {p.name for p in fetched} == {"a", "b"}
    assert a.precedence < b.precedence
