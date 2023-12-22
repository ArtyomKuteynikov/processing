from datetime import datetime
from typing import List, Union, Any
from pydantic import BaseModel


class CreateOrder(BaseModel):
    key: str
    exchange_direction: int
    website: int
    amount: float | None = None
    quantity: float | None = None
    comment: str | None = None
    payment_detail: str | None = None
    initials: str | None = None
    side: str | None = 'IN'