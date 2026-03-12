from typing import Optional
from pydantic import BaseModel, Field


class TextContent(BaseModel):
    body: str


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
