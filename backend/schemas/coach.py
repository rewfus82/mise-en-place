from __future__ import annotations

from pydantic import BaseModel


class CoachAskRequest(BaseModel):
    question: str
