from fastapi import FastAPI, Depends, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.database import engine, SessionLocal, Base
from app.models import Product, Customer, Invoice, InvoiceItem, StockMovement, User
from app.schemas import InvoiceCreate
from app.services import pos_service
from app.auth import hash_password, verify_password, create_token, decode_token

app = FastAPI()

Base.metadata.create_all(bind=engine)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ================= DB =================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================= AUTH =================
def get_current_user(authorization: str = Header(None)):
    try:
        token = authorization.split(" ")[1]
        return decode_token(token)
    except:
        return None

# ================= SEARCH (FIXED) =================
@app.get("/search-products")
def search_products(q: str, db: Session = Depends(get_db)):
    q = q.strip()

    return [
        {
            "sku": p.sku,
            "name": p.name,
            "price": p.price
        }
        for p in db.query(Product)
        .filter(
            Product.name.ilike(f"%{q}%") |
            Product.sku.ilike(f"%{q}%")
        )
        .limit(20)
        .all()
    ]

# ================= PRODUCTS CACHE =================
@app.get("/products-cache")
def products_cache(db: Session = Depends(get_db)):
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "price": p.price
        }
        for p in db.query(Product).all()
    ]

# ================= CUSTOMERS =================
@app.get("/customers")
def customers(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name} for c in db.query(Customer).all()]

# ================= USERS =================
@app.get("/create-user")
def create_user(username: str, password: str, role: str, db: Session = Depends(get_db)):
    user = User(username=username, password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    return {"msg": "created"}

@app.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data["username"]).first()

    if not user or not verify_password(data["password"], user.password):
        return {"error": "invalid"}

    token = create_token({"user_id": user.id})
    return {"access_token": token}

# ================= LOGIN PAGE =================
@app.get("/", response_class=HTMLResponse)
def login_page():
    return """
    <html>
    <body>

    <h2>Login</h2>

    <input id="u" placeholder="username"><br><br>
    <input id="p" type="password"><br><br>

    <button onclick="login()">Login</button>

    <script>
    async function login(){
        let res = await fetch("/login",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({username:u.value,password:p.value})
        });

        let data = await res.json();

        if(data.error){
            alert("Wrong login");
            return;
        }

        localStorage.setItem("token", data.access_token);
        window.location.href="/pos";
    }
    </script>

    </body>
    </html>
    """

# ================= INVOICE =================
@app.post("/invoice")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user:
        return {"error": "unauthorized"}
    return pos_service.create_invoice(data, db)

# ================= RECEIPT =================
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import Depends

from app.database import SessionLocal
from app.models import Invoice, InvoiceItem, Product, Customer

# DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/invoice/{invoice_id}", response_class=HTMLResponse)
def view_invoice(invoice_id: int, db: Session = Depends(get_db)):

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()

    rows = ""
    for i in items:
        p = db.query(Product).filter(Product.id == i.product_id).first()

        rows += f"""
        <div class="row">
            <span>{p.name}</span>
            <span>{i.qty} x {i.price}</span>
            <span>{(i.qty*i.price):.2f}</span>
        </div>
        """

    return f"""
    <html>
    <head>

    <style>
    body {{
        font-family: monospace;
        margin:0;
        padding:0;
    }}

    .r {{
        width:300px;
        margin:0 auto;
        padding:10px;
    }}

    .center {{
        text-align:center;
    }}

    .center img {{
        display:block;
        margin:0 auto;
        width:70px;
    }}

    .center h3 {{
        margin:5px 0;
    }}

    .row {{
        display:flex;
        justify-content:space-between;
        font-size:14px;
    }}

    .line {{
        border-top:1px dashed;
        margin:8px 0;
    }}

    button {{
        width:100%;
        padding:10px;
        margin-top:10px;
    }}

    </style>

    <script>
    function printAndBack(){{
        window.print();
        setTimeout(()=>{{window.location.href="/pos";}},500);
    }}
    </script>

    </head>

    <body>

    <div class="r">

        <!-- HEADER -->
        <div class="center">
            <img src="/static/logo.png">
            <h3>Habiba Organic Farm</h3>
        </div>

        <div class="line"></div>

        <!-- INFO -->
        <div class="row"><span>INV</span><span>{inv.id}</span></div>
        <div class="row"><span>Date</span><span>{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>
        <div class="row"><span>Customer</span><span>{customer.name if customer else ''}</span></div>

        <div class="line"></div>

        <!-- ITEMS -->
        {rows}

        <div class="line"></div>

        <!-- TOTAL -->
        <div class="row">
            <b>Total</b>
            <b>{inv.total:.2f}</b>
        </div>

        <button onclick="printAndBack()">Print</button>

    </div>

    </body>
    </html>
    """

# ================= POS (FIXED SEARCH + CUSTOMER) =================
@app.get("/pos", response_class=HTMLResponse)
def pos_ui():
    return """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">

<style>
:root {
    --bg:       #060810;
    --surface:  #0a0d18;
    --card:     #0f1424;
    --card2:    #151c30;
    --border:   rgba(255,255,255,0.06);
    --border2:  rgba(255,255,255,0.11);
    --green:    #00ff9d;
    --green-d:  #00c97a;
    --blue:     #4d9fff;
    --purple:   #a855f7;
    --pink:     #f472b6;
    --danger:   #ff4d6d;
    --warn:     #ffb547;
    --text:     #f0f4ff;
    --sub:      #8899bb;
    --muted:    #445066;
    --sans:     'Outfit', sans-serif;
    --mono:     'JetBrains Mono', monospace;
    --r:        13px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── ANIMATED MESH BACKGROUND ── */
body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
    display: grid;
    grid-template-columns: 1fr 430px;
    grid-template-rows: 58px 1fr;
    font-size: 14px;
    position: relative;
}

body::before {
    content: '';
    position: fixed;
    inset: 0;
    background:
        radial-gradient(ellipse 600px 400px at 15% 50%, rgba(0,255,157,.05) 0%, transparent 70%),
        radial-gradient(ellipse 400px 600px at 85% 20%, rgba(77,159,255,.06) 0%, transparent 70%),
        radial-gradient(ellipse 500px 300px at 60% 80%, rgba(168,85,247,.04) 0%, transparent 70%);
    animation: meshShift 12s ease-in-out infinite alternate;
    pointer-events: none;
    z-index: 0;
}

@keyframes meshShift {
    0%   { opacity: 1; transform: scale(1); }
    50%  { opacity: .7; transform: scale(1.05) translateY(-10px); }
    100% { opacity: 1; transform: scale(1) translateX(10px); }
}

body > * { position: relative; z-index: 1; }

/* ── TOPBAR ── */
#topbar {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 18px;
    background: rgba(10,13,24,.85);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    z-index: 10;
}

.logo {
    font-size: 18px;
    font-weight: 900;
    letter-spacing: -1px;
    background: linear-gradient(135deg, var(--green), var(--blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-right: 6px;
    white-space: nowrap;
    position: relative;
}
.logo::after {
    content: '';
    position: absolute;
    bottom: -2px; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, var(--green), var(--blue));
    opacity: .4;
    animation: logoPulse 2.5s ease-in-out infinite;
}
@keyframes logoPulse { 0%,100%{opacity:.4} 50%{opacity:1} }

/* tb fields */
.tb-field {
    display: flex; align-items: center; gap: 9px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 0 13px;
    transition: border-color .2s, box-shadow .2s;
    position: relative;
    overflow: hidden;
}
.tb-field::after {
    content: '';
    position: absolute;
    bottom: 0; left: -100%; right: 100%; height: 1.5px;
    background: linear-gradient(90deg, transparent, var(--green), transparent);
    transition: left .3s, right .3s;
}
.tb-field:focus-within::after { left: 0; right: 0; }
.tb-field:focus-within { border-color: rgba(0,255,157,.3); box-shadow: 0 0 0 3px rgba(0,255,157,.08), 0 0 20px rgba(0,255,157,.05); }
.tb-field svg { color: var(--muted); flex-shrink: 0; transition: color .2s; }
.tb-field:focus-within svg { color: var(--green); }
.tb-field input {
    background: transparent; border: none; outline: none;
    color: var(--text); font-family: var(--sans);
    font-size: 14px; font-weight: 500; padding: 11px 0; width: 100%;
}
.tb-field input::placeholder { color: var(--muted); font-weight: 400; }

#barcode_wrap { flex: 0 0 230px; }
#barcode_wrap input { font-family: var(--mono); font-size: 13px; }
#barcode_wrap:focus-within { border-color: rgba(77,159,255,.4); box-shadow: 0 0 0 3px rgba(77,159,255,.1), 0 0 20px rgba(77,159,255,.06); }
#barcode_wrap:focus-within::after { background: linear-gradient(90deg, transparent, var(--blue), transparent); }
#barcode_wrap:focus-within svg { color: var(--blue); }

#search_wrap { flex: 1; }

.tb-spacer { flex: 1; }

/* CUSTOMER */
#cust_wrap { position: relative; flex: 0 0 220px; }
#cust_wrap .tb-field { width: 100%; }
#cust_results {
    position: absolute; top: calc(100% + 8px); left: 0; right: 0;
    background: rgba(15,20,36,.97);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border2);
    border-radius: var(--r);
    max-height: 220px; overflow-y: auto;
    z-index: 300;
    box-shadow: 0 20px 50px rgba(0,0,0,.6), 0 0 0 1px rgba(0,255,157,.05);
    display: none;
    animation: dropIn .18s ease;
}
@keyframes dropIn {
    from { opacity:0; transform: translateY(-6px); }
    to   { opacity:1; transform: translateY(0); }
}
#cust_results.open { display: block; }
.cust-item {
    display: flex; align-items: center; gap: 9px;
    padding: 11px 14px; font-size: 13.5px; font-weight: 500;
    color: var(--sub); cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background .12s, color .12s, padding-left .12s;
}
.cust-item:last-child { border-bottom: none; }
.cust-item:hover { background: rgba(0,255,157,.07); color: var(--green); padding-left: 18px; }

#selected_badge {
    display: none; align-items: center; gap: 8px;
    background: rgba(0,255,157,.08);
    border: 1px solid rgba(0,255,157,.25);
    color: var(--green); font-size: 13px; font-weight: 700;
    padding: 8px 13px; border-radius: var(--r);
    white-space: nowrap; flex-shrink: 0;
    animation: badgeIn .25s ease;
}
@keyframes badgeIn {
    from { opacity:0; transform: scale(.9); }
    to   { opacity:1; transform: scale(1); }
}
#selected_badge.show { display: flex; }
#xcust { background: none; border: none; color: var(--green); opacity:.5; font-size:17px; line-height:1; cursor:pointer; padding:0; transition: opacity .15s, transform .15s; }
#xcust:hover { opacity:1; transform: rotate(90deg); }

/* LOGOUT */
#logout_btn {
    display: flex; align-items: center; gap: 7px;
    background: transparent; border: 1px solid var(--border);
    color: var(--sub); font-family: var(--sans);
    font-size: 13px; font-weight: 600;
    padding: 8px 14px; border-radius: var(--r); cursor: pointer;
    transition: all .2s; white-space: nowrap;
}
#logout_btn:hover { border-color: var(--danger); color: var(--danger); box-shadow: 0 0 12px rgba(255,77,109,.15); }

/* ── LEFT PANEL ── */
#left {
    overflow-y: auto; padding: 18px 18px;
    display: flex; flex-direction: column; gap: 14px;
    scrollbar-width: thin; scrollbar-color: var(--border2) transparent;
}

.panel-title {
    font-size: 11px; font-weight: 700;
    letter-spacing: 2px; text-transform: uppercase; color: var(--muted);
    display: flex; align-items: center; gap: 8px;
}
.panel-title::after {
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, var(--border2), transparent);
}

/* ── PRODUCT GRID ── */
#grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(145px,1fr)); gap: 10px; }

.product {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 16px 13px 13px;
    cursor: pointer;
    display: flex; flex-direction: column; gap: 5px;
    position: relative; overflow: hidden;
    transition: border-color .2s, box-shadow .2s, transform .15s;
    animation: cardReveal .3s ease both;
}
@keyframes cardReveal {
    from { opacity:0; transform: scale(.96) translateY(6px); }
    to   { opacity:1; transform: scale(1) translateY(0); }
}
.product:nth-child(1)  { animation-delay: .02s }
.product:nth-child(2)  { animation-delay: .04s }
.product:nth-child(3)  { animation-delay: .06s }
.product:nth-child(4)  { animation-delay: .08s }
.product:nth-child(5)  { animation-delay: .10s }
.product:nth-child(6)  { animation-delay: .12s }
.product:nth-child(7)  { animation-delay: .14s }
.product:nth-child(8)  { animation-delay: .16s }

/* moving glint on hover */
.product::before {
    content: '';
    position: absolute;
    top: -40%; left: -60%; width: 40%; height: 180%;
    background: linear-gradient(105deg, transparent, rgba(255,255,255,.06), transparent);
    transform: skewX(-15deg);
    transition: left .4s ease;
}
.product:hover::before { left: 130%; }

/* glow overlay */
.product::after {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(circle at 50% 0%, rgba(0,255,157,.1), transparent 65%);
    opacity: 0; transition: opacity .2s;
}
.product:hover {
    border-color: rgba(0,255,157,.5);
    box-shadow: 0 0 0 1px rgba(0,255,157,.15), 0 8px 30px rgba(0,255,157,.12), inset 0 1px 0 rgba(0,255,157,.1);
    transform: translateY(-3px);
}
.product:hover::after { opacity: 1; }
.product:active { transform: translateY(-1px); }

.p-name { font-size: 13.5px; font-weight: 700; color: var(--text); line-height: 1.35; }
.p-sku  { font-family: var(--mono); font-size: 10.5px; color: var(--muted); letter-spacing: .3px; }
.p-price {
    font-family: var(--mono); font-size: 17px; font-weight: 700;
    color: var(--green); margin-top: 5px;
    text-shadow: 0 0 12px rgba(0,255,157,.4);
}

/* ripple on add */
@keyframes ripple {
    0%   { transform: scale(0); opacity: .5; }
    100% { transform: scale(4); opacity: 0; }
}
.ripple-dot {
    position: absolute; width: 40px; height: 40px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(0,255,157,.5), transparent 70%);
    transform: scale(0); pointer-events: none;
    animation: ripple .5s ease-out forwards;
}

/* flash on scan */
@keyframes cardFlash {
    0%   { background: rgba(0,255,157,.2); border-color: var(--green); box-shadow: 0 0 20px rgba(0,255,157,.4); }
    100% { background: var(--card); border-color: var(--border); box-shadow: none; }
}
.flash { animation: cardFlash .45s ease; }

#no_results {
    display: none; flex-direction: column; align-items: center;
    gap: 12px; padding: 70px 0; color: var(--muted);
    font-size: 14px; font-weight: 500;
}

/* ── RIGHT PANEL ── */
#right {
    background: rgba(10,13,24,.9);
    backdrop-filter: blur(20px);
    border-left: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden;
    position: relative;
}
/* subtle animated left-border glow */
#right::before {
    content: '';
    position: absolute; left: -1px; top: 20%; bottom: 20%; width: 1px;
    background: linear-gradient(180deg, transparent, var(--green), transparent);
    opacity: .4;
    animation: borderGlow 3s ease-in-out infinite;
}
@keyframes borderGlow { 0%,100%{opacity:.2;top:20%;bottom:20%} 50%{opacity:.7;top:10%;bottom:10%} }

/* cart header */
#cart_header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 15px 18px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.cart-title { display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 800; }
#cart_count {
    background: linear-gradient(135deg, var(--green), var(--blue));
    color: #000; font-size: 11px; font-weight: 800;
    padding: 2px 9px; border-radius: 20px; display: none;
    animation: countPop .2s cubic-bezier(.34,1.56,.64,1);
}
@keyframes countPop { from{transform:scale(.6)} to{transform:scale(1)} }

#clear_btn {
    display: flex; align-items: center; gap: 6px;
    background: rgba(255,77,109,.08);
    border: 1px solid rgba(255,77,109,.2);
    color: var(--danger); font-family: var(--sans);
    font-size: 12px; font-weight: 700;
    padding: 7px 13px; border-radius: 9px; cursor: pointer;
    transition: all .2s;
}
#clear_btn:hover { background: rgba(255,77,109,.18); border-color: var(--danger); box-shadow: 0 0 14px rgba(255,77,109,.2); }

/* cart scroll */
#cart_scroll {
    flex: 1; overflow-y: auto; padding: 12px 16px;
    display: flex; flex-direction: column; gap: 8px;
    scrollbar-width: thin; scrollbar-color: var(--border2) transparent;
}

#cart_empty {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 12px; color: var(--muted); font-size: 14px; font-weight: 500; padding: 40px 0;
}
#cart_empty svg { opacity: .25; animation: emptyFloat 3s ease-in-out infinite; }
@keyframes emptyFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }

/* cart items */
.cart-item {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 11px 13px;
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    column-gap: 10px; row-gap: 7px;
    align-items: center;
    animation: itemIn .2s cubic-bezier(.34,1.2,.64,1);
    transition: border-color .2s, box-shadow .2s;
}
@keyframes itemIn {
    from { opacity:0; transform: translateX(12px) scale(.97); }
    to   { opacity:1; transform: translateX(0) scale(1); }
}
.cart-item:hover { border-color: var(--border2); box-shadow: 0 4px 16px rgba(0,0,0,.3); }

.ci-name   { font-size: 13.5px; font-weight: 700; color: var(--text); line-height: 1.3; }
.ci-subtotal {
    font-family: var(--mono); font-size: 15px; font-weight: 700;
    color: var(--green); text-align: right;
    text-shadow: 0 0 10px rgba(0,255,157,.3);
}
.ci-controls { display: flex; align-items: center; gap: 5px; grid-column: 1/-1; }

.qty-btn {
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    background: var(--card2); border: 1px solid var(--border2);
    border-radius: 8px; color: var(--text);
    font-size: 18px; font-weight: 700; line-height: 1; font-family: var(--sans);
    cursor: pointer; transition: all .15s; flex-shrink: 0;
}
.qty-btn:hover { border-color: var(--green); color: var(--green); box-shadow: 0 0 8px rgba(0,255,157,.2); transform: scale(1.1); }
.qty-btn:active { transform: scale(.95); }

.qty-input {
    width: 38px; height: 28px;
    background: var(--card2); border: 1px solid var(--border2);
    border-radius: 8px; color: var(--text);
    font-family: var(--mono); font-size: 13px; font-weight: 500;
    text-align: center; outline: none; transition: border-color .15s;
}
.qty-input:focus { border-color: var(--blue); box-shadow: 0 0 8px rgba(77,159,255,.2); }

.ci-unit { font-family: var(--mono); font-size: 11.5px; color: var(--muted); margin-left: 3px; flex: 1; }

.rm-btn {
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    background: transparent; border: 1px solid transparent;
    border-radius: 8px; color: var(--muted); font-size: 13px;
    cursor: pointer; transition: all .15s; margin-left: auto;
}
.rm-btn:hover { border-color: var(--danger); color: var(--danger); background: rgba(255,77,109,.08); transform: scale(1.1); }

/* ── TOTALS ── */
#totals {
    border-top: 1px solid var(--border);
    padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; flex-shrink: 0;
}

.inputs-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.fld { display: flex; flex-direction: column; gap: 4px; }
.fld-label { font-size: 10.5px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); }
.fld-input {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r); padding: 10px 12px;
    color: var(--text); font-family: var(--mono); font-size: 15px; font-weight: 500;
    text-align: center; outline: none; width: 100%; transition: all .18s;
}
.fld-input:focus { border-color: rgba(77,159,255,.5); box-shadow: 0 0 0 3px rgba(77,159,255,.1), 0 0 16px rgba(77,159,255,.08); }

/* total display */
.total-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    position: relative; overflow: hidden;
}
.total-row::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(0,255,157,.04), transparent 60%);
    pointer-events: none;
}
.total-label { font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: var(--sub); }
#total {
    font-family: var(--mono); font-size: 30px; font-weight: 700;
    color: var(--green); transition: color .3s;
    text-shadow: 0 0 20px rgba(0,255,157,.35);
}

/* change row */
.change-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 9px 14px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--r);
}
.change-label { font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: var(--sub); }
#change { font-family: var(--mono); font-size: 16px; font-weight: 500; color: var(--muted); transition: color .2s; }

/* ── CHECKOUT BUTTON ── */
#checkout_btn {
    display: flex; align-items: center; justify-content: center; gap: 9px;
    width: 100%; padding: 16px;
    background: linear-gradient(135deg, var(--green), #00d4ff);
    border: none; border-radius: var(--r);
    color: #021a10; font-family: var(--sans); font-size: 15px; font-weight: 900;
    letter-spacing: .5px; cursor: pointer;
    position: relative; overflow: hidden;
    transition: transform .15s, box-shadow .2s, filter .2s;
    box-shadow: 0 4px 20px rgba(0,255,157,.25), 0 0 0 1px rgba(0,255,157,.1);
}
#checkout_btn::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(255,255,255,.15), transparent);
    pointer-events: none;
}
/* shimmer sweep */
#checkout_btn::after {
    content: '';
    position: absolute; top:0; left:-100%; bottom:0; width:50%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.25), transparent);
    animation: shimmer 2.5s ease-in-out infinite;
}
@keyframes shimmer { 0%{left:-100%} 100%{left:200%} }

#checkout_btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,255,157,.4), 0 0 0 1px rgba(0,255,157,.2);
    filter: brightness(1.08);
}
#checkout_btn:active:not(:disabled) { transform: translateY(0); }
#checkout_btn:disabled { opacity: .35; cursor: not-allowed; filter: grayscale(.5); }

/* ── BARCODE SCAN ANIMATION ── */
@keyframes scanBeam {
    0%   { box-shadow: 0 0 0 2px rgba(77,159,255,.6), inset 0 0 0 1000px rgba(77,159,255,.04); border-color: var(--blue); }
    100% { box-shadow: none; border-color: var(--border); }
}
.scan-flash { animation: scanBeam .5s ease; }

/* ── TOAST ── */
.toast {
    position: fixed; bottom: 22px; left: 50%;
    transform: translateX(-50%) translateY(16px);
    background: rgba(15,20,36,.95);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border2);
    border-radius: var(--r); padding: 12px 18px;
    display: flex; align-items: center; gap: 12px;
    font-size: 13.5px; font-weight: 600; color: var(--text);
    box-shadow: 0 20px 50px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.04);
    opacity: 0; pointer-events: none;
    transition: opacity .25s, transform .25s; z-index: 999;
}
.toast.show { opacity:1; transform: translateX(-50%) translateY(0); pointer-events: auto; }
.toast-undo {
    background: linear-gradient(135deg, var(--green), var(--blue)); color: #021a10;
    border: none; border-radius: 7px; padding: 5px 11px;
    font-family: var(--sans); font-size: 12px; font-weight: 800; cursor: pointer;
}

/* scrollbar styling */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 4px; }
</style>
</head>
<body>

<!-- TOPBAR -->
<div id="topbar">
    <span class="logo">⬡ POS</span>

    <div class="tb-field" id="barcode_wrap" title="Scan barcode or type SKU + Enter">
        <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path d="M3 5v14M7 5v14M11 5v14M15 5v9M19 5v9M15 17v2M19 17v2"/>
        </svg>
        <input id="barcode" placeholder="Scan / SKU…" autocomplete="off">
    </div>

    <div class="tb-field" id="search_wrap">
        <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input id="search" placeholder="Search products…" autocomplete="off">
    </div>

    <span class="tb-spacer"></span>

    <div id="cust_wrap">
        <div class="tb-field">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
            <input id="cust_search" placeholder="Search customer…" autocomplete="off">
        </div>
        <div id="cust_results"></div>
    </div>

    <div id="selected_badge">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <polyline points="20 6 9 17 4 12"/>
        </svg>
        <span id="sel_name"></span>
        <button id="xcust" onclick="clearCustomer()" title="Clear">×</button>
    </div>

    <button id="logout_btn" onclick="logout()">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
        Logout
    </button>
</div>

<!-- LEFT -->
<div id="left">
    <span class="panel-title">Products</span>
    <div id="grid"></div>
    <div id="no_results">
        <svg width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        No products found
    </div>
</div>

<!-- RIGHT -->
<div id="right">
    <div id="cart_header">
        <div class="cart-title">
            Cart
            <span id="cart_count"></span>
        </div>
        <button id="clear_btn" onclick="clearCart()">
            <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
            </svg>
            Clear
        </button>
    </div>

    <div id="cart_scroll">
        <div id="cart_empty">
            <svg width="44" height="44" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                <line x1="3" y1="6" x2="21" y2="6"/>
                <path d="M16 10a4 4 0 0 1-8 0"/>
            </svg>
            Cart is empty
        </div>
        <div id="cart"></div>
    </div>

    <div id="totals">
        <div class="inputs-row">
            <div class="fld">
                <span class="fld-label">Discount %</span>
                <input id="discount" class="fld-input" type="number" placeholder="0" min="0" max="100">
            </div>
            <div class="fld">
                <span class="fld-label">Cash</span>
                <input id="cash" class="fld-input" type="number" placeholder="0.00" min="0">
            </div>
        </div>

        <div class="total-row">
            <span class="total-label">Total</span>
            <span id="total">0.00</span>
        </div>

        <div class="change-row">
            <span class="change-label">Change</span>
            <span id="change">—</span>
        </div>

        <button id="checkout_btn" onclick="checkout()">
            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            Confirm Order
        </button>
    </div>
</div>

<!-- TOAST -->
<div class="toast" id="toast">
    <span id="toast_msg"></span>
    <button class="toast-undo" id="toast_undo" style="display:none" onclick="undoCart()">UNDO</button>
</div>

<script>
let beep = new Audio("https://www.soundjay.com/buttons/beep-07.wav");
let customers=[], products=[], cart=[], lastCart=[];
let selectedCustomer=null, token=localStorage.getItem("token"), toastTimer=null;

/* LOAD */
async function load(){
    customers = await (await fetch("/customers")).json();
    products  = await (await fetch("/products-cache")).json();
    draw(products.slice(0,40));
}

/* CUSTOMER */
cust_search.oninput = function(){
    let v=this.value.toLowerCase().trim();
    let r=document.getElementById("cust_results");
    if(!v){ r.classList.remove("open"); r.innerHTML=""; return; }
    let f=customers.filter(c=>c.name.toLowerCase().includes(v)).slice(0,8);
    r.innerHTML=f.map(c=>`
        <div class="cust-item" onclick="selectCustomer('${c.id}','${c.name}')">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>${c.name}
        </div>`).join("");
    r.classList.add("open");
};

function selectCustomer(id,name){
    selectedCustomer=id;
    document.getElementById("sel_name").innerText=name;
    document.getElementById("selected_badge").classList.add("show");
    document.getElementById("cust_wrap").style.display="none";
    document.getElementById("cust_results").classList.remove("open");
}
function clearCustomer(){
    selectedCustomer=null;
    document.getElementById("selected_badge").classList.remove("show");
    document.getElementById("cust_wrap").style.display="";
    cust_search.value="";
}
document.addEventListener("click",e=>{
    if(!e.target.closest("#cust_wrap"))
        document.getElementById("cust_results").classList.remove("open");
});

/* BARCODE */
barcode.addEventListener("keydown",function(e){
    if(e.key!=="Enter") return;
    let v=this.value.trim(); if(!v) return;
    let p=products.find(p=>String(p.sku).toLowerCase()===v.toLowerCase());
    if(p){
        add(p.sku,p.name,p.price);
        let card=document.querySelector(`[data-sku="${p.sku}"]`);
        if(card){ card.classList.add("flash"); setTimeout(()=>card.classList.remove("flash"),450); }
        barcode_wrap.classList.add("scan-flash");
        setTimeout(()=>barcode_wrap.classList.remove("scan-flash"),500);
    } else {
        showToast("⚠ SKU not found: "+v);
    }
    this.value="";
});

/* GRID */
function draw(list){
    let nr=document.getElementById("no_results");
    if(!list.length){ document.getElementById("grid").innerHTML=""; nr.style.display="flex"; return; }
    nr.style.display="none";
    document.getElementById("grid").innerHTML=list.map(p=>`
        <div class="product" data-sku="${p.sku}" onclick="addWithRipple(event,'${p.sku}','${p.name}',${p.price})">
            <div class="p-name">${p.name}</div>
            <div class="p-sku">${p.sku}</div>
            <div class="p-price">${parseFloat(p.price).toFixed(2)}</div>
        </div>`).join("");
}

search.oninput=async function(){
    let v=this.value.trim();
    if(!v){ draw(products.slice(0,40)); return; }
    let data=await(await fetch("/search-products?q="+encodeURIComponent(v))).json();
    draw(data);
};

/* RIPPLE ADD */
function addWithRipple(e,sku,name,price){
    let card=e.currentTarget;
    let rect=card.getBoundingClientRect();
    let dot=document.createElement("div");
    dot.className="ripple-dot";
    dot.style.left=(e.clientX-rect.left-20)+"px";
    dot.style.top=(e.clientY-rect.top-20)+"px";
    card.appendChild(dot);
    setTimeout(()=>dot.remove(),500);
    add(sku,name,price);
}

/* CART ACTIONS */
function add(sku,name,price){
    let ex=cart.find(c=>c.sku===sku);
    ex ? ex.qty++ : cart.push({sku,name,price:parseFloat(price),qty:1});
    beep.currentTime=0; beep.play().catch(()=>{});
    drawCart();
}
function inc(sku){ cart.find(c=>c.sku===sku).qty++; drawCart(); }
function dec(sku){
    let i=cart.find(c=>c.sku===sku);
    if(--i.qty<=0) cart=cart.filter(c=>c.sku!==sku);
    drawCart();
}
function updateQty(sku,val){
    cart.find(c=>c.sku===sku).qty=Math.max(1,parseFloat(val)||1);
    drawCart();
}
function removeItem(sku){ cart=cart.filter(c=>c.sku!==sku); drawCart(); }
function clearCart(){
    if(!cart.length) return;
    if(!confirm("Clear all items?")) return;
    lastCart=[...cart]; cart=[];
    drawCart(); showToast("Cart cleared",true,true);
}
function undoCart(){ cart=[...lastCart]; drawCart(); hideToast(); }
function logout(){ localStorage.removeItem("token"); window.location.href="/"; }

/* ANIMATED COUNTER */
function animateNumber(el, to){
    let from=parseFloat(el.innerText)||0;
    let diff=to-from; let steps=18; let i=0;
    clearInterval(el._t);
    el._t=setInterval(()=>{
        i++;
        el.innerText=(from+diff*(i/steps)).toFixed(2);
        if(i>=steps){ el.innerText=to.toFixed(2); clearInterval(el._t); }
    },14);
}

/* DRAW CART */
function drawCart(){
    let empty=document.getElementById("cart_empty");
    let cartEl=document.getElementById("cart");
    let countEl=document.getElementById("cart_count");
    let total=0;

    if(!cart.length){
        cartEl.innerHTML=""; empty.style.display="flex";
        countEl.style.display="none";
    } else {
        empty.style.display="none";
        countEl.style.display="";
        countEl.innerText=cart.reduce((s,c)=>s+c.qty,0);
        // re-pop badge
        countEl.style.animation="none";
        void countEl.offsetWidth;
        countEl.style.animation="countPop .2s cubic-bezier(.34,1.56,.64,1)";
    }

    cartEl.innerHTML=cart.map(c=>{
        let t=c.qty*c.price; total+=t;
        return `
        <div class="cart-item">
            <div class="ci-name">${c.name}</div>
            <div class="ci-subtotal">${t.toFixed(2)}</div>
            <div class="ci-controls">
                <button class="qty-btn" onclick="dec('${c.sku}')">−</button>
                <input class="qty-input" value="${c.qty}" onchange="updateQty('${c.sku}',this.value)">
                <button class="qty-btn" onclick="inc('${c.sku}')">+</button>
                <span class="ci-unit">× ${c.price.toFixed(2)}</span>
                <button class="rm-btn" onclick="removeItem('${c.sku}')" title="Remove">✕</button>
            </div>
        </div>`;
    }).join("");

    let disc=parseFloat(document.getElementById("discount").value)||0;
    let final=total-(total*disc/100);
    let cash=parseFloat(document.getElementById("cash").value)||0;

    let totalEl=document.getElementById("total");
    animateNumber(totalEl, final);
    totalEl.style.color=(cash>0&&cash>=final)?"var(--green)":(cash>0)?"var(--warn)":"var(--green)";
    totalEl.style.textShadow=(cash>0&&cash<final)?"0 0 20px rgba(255,181,71,.4)":"0 0 20px rgba(0,255,157,.35)";

    let changeEl=document.getElementById("change");
    if(cash>0){
        let ch=cash-final;
        changeEl.innerText=ch.toFixed(2);
        changeEl.style.color=ch>=0?"var(--green)":"var(--danger)";
    } else {
        changeEl.innerText="—"; changeEl.style.color="var(--muted)";
    }
}

document.getElementById("cash").oninput=drawCart;
document.getElementById("discount").oninput=drawCart;

/* TOAST */
function showToast(msg,autoHide=true,undo=false){
    document.getElementById("toast_msg").innerText=msg;
    let u=document.getElementById("toast_undo"); u.style.display=undo?"":"none";
    document.getElementById("toast").classList.add("show");
    if(toastTimer) clearTimeout(toastTimer);
    if(autoHide) toastTimer=setTimeout(hideToast,4000);
}
function hideToast(){ document.getElementById("toast").classList.remove("show"); }

/* CHECKOUT */
async function checkout(){
    if(!selectedCustomer){ showToast("⚠ Select a customer first"); return; }
    if(!cart.length){ showToast("⚠ Cart is empty"); return; }
    if(!token){ window.location.href="/"; return; }
    let btn=document.getElementById("checkout_btn");
    btn.disabled=true; btn.innerText="Processing…";
    try {
        let res=await fetch("/invoice",{
            method:"POST",
            headers:{"Content-Type":"application/json","Authorization":"Bearer "+token},
            body:JSON.stringify({customer_id:selectedCustomer,payment_method:"cash",items:cart})
        });
        let data=await res.json();
        if(data.error){ showToast(data.error); btn.disabled=false; btn.innerText="Confirm Order"; return; }
        window.location.href="/invoice/"+data.invoice_id;
    } catch(e){
        showToast("Network error"); btn.disabled=false; btn.innerText="Confirm Order";
    }
}

load();
</script>
</body>
</html>
"""