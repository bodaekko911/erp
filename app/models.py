from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    sku = Column(String, unique=True)
    price = Column(Float)
    cost = Column(Float)
    is_active = Column(Boolean, default=True)

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    qty = Column(Float)
    type = Column(String)

# 🔥 Customer with ID from Excel
class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)   # 🔥 بدل Integer
    name = Column(String)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    total = Column(Float)
    status = Column(String)
    payment_method = Column(String)

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    product_id = Column(Integer)
    qty = Column(Float)
    price = Column(Float)