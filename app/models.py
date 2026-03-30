from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    sku = Column(String, unique=True)
    barcode = Column(String, unique=True, index=True)
    price = Column(Float)
    cost = Column(Float)
    is_active = Column(Boolean, default=True)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    qty = Column(Float)
    type = Column(String)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)


# 🔥 USERS
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String)  # admin / cashier


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"))
    user_id = Column(Integer, ForeignKey("users.id"))  # 🔥 جديد
    total = Column(Float)
    status = Column(String)
    payment_method = Column(String)


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    qty = Column(Float)
    price = Column(Float)