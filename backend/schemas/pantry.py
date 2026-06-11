from __future__ import annotations
from pydantic import BaseModel


class PantryItemOut(BaseModel):
    id: int
    item: str
    quantity: str
    category: str


class AddPantryRequest(BaseModel):
    items: list[dict]


class ParsePantryRequest(BaseModel):
    text: str


class ParseImageRequest(BaseModel):
    data: str                      # base64-encoded image bytes (no data: URI prefix)
    mime_type: str = "image/jpeg"


class ParsePantryResponse(BaseModel):
    added: list[str]
    skipped: list[str]
