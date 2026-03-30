import pandas as pd
from app.models import Product, Customer, StockMovement


def import_all(db):

    # ================= PRODUCTS =================
    products_df = pd.read_excel("products.xlsx")
    products_df["SKU"] = products_df["SKU"].astype(str).str.strip()

    for _, row in products_df.iterrows():
        sku = row["SKU"]

        existing = db.query(Product).filter(Product.sku == sku).first()

        if existing:
            existing.name = str(row["Item"]).strip()
            existing.price = row["Sales price"] if not pd.isna(row["Sales price"]) else 0
            existing.cost = row["Unit Cost"] if not pd.isna(row["Unit Cost"]) else 0
        else:
            db.add(Product(
                sku=sku,
                name=str(row["Item"]).strip(),
                price=row["Sales price"] if not pd.isna(row["Sales price"]) else 0,
                cost=row["Unit Cost"] if not pd.isna(row["Unit Cost"]) else 0,
                is_active=True
            ))

    db.commit()

    # ================= CUSTOMERS =================
    customers_df = pd.read_excel("Customers.xlsx")
    customers_df.columns = customers_df.columns.str.strip()

    for _, row in customers_df.iterrows():
        cid = str(row["ID"]).strip()

        existing = db.query(Customer).filter(Customer.id == cid).first()

        if existing:
            existing.name = str(row["Vendor"]).strip()
        else:
            db.add(Customer(
                id=cid,
                name=str(row["Vendor"]).strip()
            ))

    db.commit()

    # ================= STOCK =================
    stock_df = pd.read_excel("SOH.xlsx")
    stock_df["SKU"] = stock_df["SKU"].astype(str).str.strip()

    # 🔥 مهم: امسح stock القديم قبل التحديث
    db.query(StockMovement).delete()
    db.commit()

    for _, row in stock_df.iterrows():
        sku = row["SKU"]

        product = db.query(Product).filter(Product.sku == sku).first()
        if not product:
            continue

        qty = row["Stock"] if not pd.isna(row["Stock"]) else 0

        db.add(StockMovement(
            product_id=product.id,
            qty=qty,
            type="init"
        ))

    db.commit()

    return {"status": "updated successfully"}