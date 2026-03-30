from app.models import Product, Invoice, InvoiceItem, StockMovement

def create_invoice(data, db):

    total = 0
    items_data = []

    for item in data.items:

        p = db.query(Product).filter(Product.sku == item.sku).first()

        if not p:
            return {"error": f"{item.sku} not found"}

        total += p.price * item.qty

        items_data.append((p, item.qty, p.price))

    inv = Invoice(
        customer_id=data.customer_id,
        total=total,
        status="paid",
        payment_method=data.payment_method
    )

    db.add(inv)
    db.flush()

    for p, qty, price in items_data:

        db.add(InvoiceItem(
            invoice_id=inv.id,
            product_id=p.id,
            qty=qty,
            price=price
        ))

        db.add(StockMovement(
            product_id=p.id,
            qty=-qty,
            type="sale"
        ))

    db.commit()

    return {"invoice_id": inv.id}