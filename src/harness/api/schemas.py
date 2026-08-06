"""API request/response schemas kept separate from core domain models.

The web client generates its TypeScript types from the OpenAPI document produced by
these schemas (SPEC/API_CONTRACT.md), so this module is the single source of truth for
wire shapes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from harness.core.domain import Binding


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class RoleCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""


class PersonaCreate(BaseModel):
    name: str
    description: str = ""
    prompt: str = ""
    precedence: int = 100


class ContactCreate(BaseModel):
    handle: str
    display_name: str
    role: str | None = None
    personas: list[str] = Field(default_factory=list)
    binding: Binding = Field(default_factory=Binding)


class ContactUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    personas: list[str] | None = None
    binding: Binding | None = None


class TeamCreate(BaseModel):
    handle: str
    display_name: str
    members: list[str] = Field(default_factory=list)


class SessionCreate(BaseModel):
    title: str = ""
    contacts: list[str] = Field(default_factory=list)


class MessageCreate(BaseModel):
    content: str


class BindingOverride(BaseModel):
    binding: Binding | None = None


class RunOutcomeResponse(BaseModel):
    run_id: str
    contact_handle: str
    content: str
    status: str


class MessagesResponse(BaseModel):
    correlation_id: str
    runs: list[RunOutcomeResponse]
