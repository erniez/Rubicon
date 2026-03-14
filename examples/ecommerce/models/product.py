"""Product domain model."""

from models.base import BaseModel


class Product(BaseModel):
    name: str
    price: float
    description: str
    sku: str
