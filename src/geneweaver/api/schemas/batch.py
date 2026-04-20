"""Module for defining schemas for batch endpoints."""

from pydantic import BaseModel

from geneweaver.api.schemas.messages import MessageResponse


class BatchResponse(BaseModel):
    """Class for defining a response containing batch results."""

    genesets: list[int]
    messages: MessageResponse
