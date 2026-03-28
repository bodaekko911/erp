from pydantic import BaseModel
from typing import List

class Item(BaseModel):
    sku: str
    qty: float

class InvoiceCreate(BaseModel):
    customer_id: str
    payment_method: str
    items: List[Item]