"""Contacts / Roles / Personas / Teams CRUD (SPEC/API_CONTRACT.md)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request

from harness.api.auth import require_auth
from harness.api.schemas import ContactCreate, ContactUpdate, PersonaCreate, RoleCreate, TeamCreate
from harness.core.app import Application
from harness.core.domain import Contact, Persona, Role, Team
from harness.core.errors import NotFoundError, ValidationFailedError
from harness.core.ids import new_id

router = APIRouter(dependencies=[Depends(require_auth)], tags=["agents"])


def _app(request: Request) -> Application:
    return cast(Application, request.app.state.harness)


@router.get("/roles")
async def list_roles(request: Request) -> list[Role]:
    return await _app(request).roles.list()


@router.post("/roles", status_code=201)
async def create_role(request: Request, body: RoleCreate) -> Role:
    role = Role(id=new_id("role"), **body.model_dump())
    return await _app(request).roles.create(role)


@router.get("/personas")
async def list_personas(request: Request) -> list[Persona]:
    return await _app(request).personas.list()


@router.post("/personas", status_code=201)
async def create_persona(request: Request, body: PersonaCreate) -> Persona:
    persona = Persona(id=new_id("per"), **body.model_dump())
    return await _app(request).personas.create(persona)


async def _resolve_role_id(app: Application, role_handle: str | None) -> str | None:
    if role_handle is None:
        return None
    role = await app.roles.get_by_name(role_handle)
    if role is None:
        raise ValidationFailedError(f"unknown role: {role_handle}")
    return role.id


async def _resolve_persona_ids(app: Application, names: list[str]) -> list[str]:
    ids = []
    for name in names:
        persona = await app.personas.get_by_name(name)
        if persona is None:
            raise ValidationFailedError(f"unknown persona: {name}")
        ids.append(persona.id)
    return ids


@router.get("/contacts")
async def list_contacts(request: Request) -> list[Contact]:
    return await _app(request).contacts.list()


@router.post("/contacts", status_code=201)
async def create_contact(request: Request, body: ContactCreate) -> Contact:
    app = _app(request)
    role_id = await _resolve_role_id(app, body.role)
    persona_ids = await _resolve_persona_ids(app, body.personas)
    contact = Contact(
        id=new_id("con"),
        handle=body.handle,
        display_name=body.display_name,
        role_id=role_id,
        persona_ids=persona_ids,
        binding=body.binding,
    )
    return await app.contacts.create(contact)


@router.get("/contacts/{contact_id}")
async def get_contact(request: Request, contact_id: str) -> Contact:
    return await _app(request).contacts.get(contact_id)


@router.patch("/contacts/{contact_id}")
async def update_contact(request: Request, contact_id: str, body: ContactUpdate) -> Contact:
    app = _app(request)
    role_id = await _resolve_role_id(app, body.role) if body.role is not None else None
    persona_ids = (
        await _resolve_persona_ids(app, body.personas) if body.personas is not None else None
    )
    return await app.contacts.update(
        contact_id,
        display_name=body.display_name,
        role_id=role_id,
        persona_ids=persona_ids,
        binding=body.binding,
    )


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(request: Request, contact_id: str) -> None:
    await _app(request).contacts.delete(contact_id)


@router.get("/teams")
async def list_teams(request: Request) -> list[Team]:
    return await _app(request).teams.list()


@router.post("/teams", status_code=201)
async def create_team(request: Request, body: TeamCreate) -> Team:
    app = _app(request)
    member_ids = []
    for handle in body.members:
        contact = await app.contacts.get_by_handle(handle)
        if contact is None:
            raise NotFoundError(f"contact not found: {handle}")
        member_ids.append(contact.id)
    team = Team(
        id=new_id("team"), handle=body.handle, display_name=body.display_name, member_ids=member_ids
    )
    return await app.teams.create(team)
