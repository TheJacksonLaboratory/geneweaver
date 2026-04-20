"""Namespace for defining schemas related to messaging."""

import enum

from pydantic import BaseModel


class MessageType(enum.Enum):
    """Enum for defining the type of message."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    """Base class for defining a message."""

    message: str
    message_type: MessageType
    detail: str | None = None


class UserMessage(Message):
    """Class for defining a message for a user."""

    ...


class SystemMessage(Message):
    """Class for defining a message for the system."""

    ...


class MessageResponse(BaseModel):
    """Class for defining a response containing messages."""

    user_messages: list[UserMessage] | None = None
    system_messages: list[SystemMessage] | None = None
