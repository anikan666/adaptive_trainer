from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TextContent(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text body must not be empty")
        return v


class Message(BaseModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: Optional[TextContent] = None

    model_config = {"populate_by_name": True}


class Profile(BaseModel):
    name: str


class Contact(BaseModel):
    profile: Profile
    wa_id: str


class Metadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class Value(BaseModel):
    messaging_product: str
    metadata: Metadata
    contacts: Optional[list[Contact]] = None
    messages: Optional[list[Message]] = None


class Change(BaseModel):
    value: Value
    field: str


class Entry(BaseModel):
    id: str
    changes: list[Change]


class WebhookPayload(BaseModel):
    object: str
    entry: list[Entry]


class IncomingTextMessage(BaseModel):
    """Normalized representation of an incoming WhatsApp text message."""

    message_id: str
    sender_phone: str
    text: str
    timestamp: str
    phone_number_id: str

    @field_validator("message_id", "sender_phone", "timestamp", "phone_number_id")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty")
        return v

    @field_validator("text")
    @classmethod
    def text_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty")
        return v
