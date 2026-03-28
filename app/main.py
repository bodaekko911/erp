from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.database import engine, SessionLocal, Base
from app.models import Product, Customer, Invoice, InvoiceItem, StockMovement
from app.schemas import InvoiceCreate

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

Base.metadata.create_all(bind=engine)

# ===== DB =====
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===== STOCK =====
def get_stock(db, product_id):
    result = db.query(func.sum(StockMovement.qty)).filter(
        StockMovement.product_id == product_id
    ).scalar()
    return result if result else 0

# ===== PRODUCTS =====
@app.get("/products-full")
def products_full(db: Session = Depends(get_db)):
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "price": p.price,
            "stock": get_stock(db, p.id)
        }
        for p in db.query(Product).all()
    ]

# ===== CUSTOMERS =====
@app.get("/customers")
def customers(db: Session = Depends(get_db)):
    return [{"id": str(c.id), "name": c.name} for c in db.query(Customer).all()]

# ===== CREATE INVOICE =====
@app.post("/invoice")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db)):

    try:
        if not data.customer_id:
            return {"error": "Select customer"}

        if not data.items:
            return {"error": "Empty cart"}

        total = 0
        items_data = []

        for item in data.items:
            p = db.query(Product).filter(Product.sku == item.sku).first()

            if not p:
                return {"error": f"{item.sku} not found"}

            stock = get_stock(db, p.id)
            if stock < item.qty:
                return {"error": f"Not enough stock for {p.name}"}

            total += p.price * item.qty
            items_data.append((p, item.qty))

        inv = Invoice(
            customer_id=str(data.customer_id),
            total=total,
            status="paid",
            payment_method="cash"
        )

        db.add(inv)
        db.commit()
        db.refresh(inv)

        for p, qty in items_data:
            db.add(InvoiceItem(
                invoice_id=inv.id,
                product_id=p.id,
                qty=qty,
                price=p.price
            ))

            db.add(StockMovement(
                product_id=p.id,
                qty=-qty,
                type="sale"
            ))

        db.commit()

        return {"invoice_id": inv.id}

    except Exception as e:
        return {"error": str(e)}

# ===== RECEIPT =====
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
    body {{font-family: monospace;}}
    .r {{width:300px;margin:auto}}
    .c {{text-align:center}}
    .line {{border-top:1px dashed;margin:8px 0}}
    .row {{display:flex;justify-content:space-between}}
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
        <div class="c">
            <img src="/static/logo.png" width="60">
            <h3>Habiba Organic Farm</h3>
        </div>

        <div class="line"></div>

        <div class="row"><span>INV</span><span>{inv.id}</span></div>
        <div class="row"><span>Date</span><span>{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>
        <div class="row"><span>Customer</span><span>{customer.name}</span></div>

        <div class="line"></div>

        {rows}

        <div class="line"></div>

        <div class="row"><b>Total</b><b>{inv.total:.2f}</b></div>

        <button onclick="printAndBack()">Print</button>
    </div>

    </body>
    </html>
    """

# ===== POS =====
@app.get("/pos", response_class=HTMLResponse)
def pos_ui():
    return """
<html>
<head>
<style>

body {margin:0;font-family:system-ui;background:#eef2f7}

.container {
    display:grid;
    grid-template-columns:2fr 1fr;
    height:100vh;
}

.left {padding:24px;}
.card {
    background:white;
    padding:18px;
    border-radius:16px;
    margin-bottom:18px;
    box-shadow:0 6px 18px rgba(0,0,0,0.06);
}

.title {font-weight:600;margin-bottom:10px;}

input {
    width:100%;
    padding:14px;
    border-radius:12px;
    border:1px solid #ddd;
}

.results div {
    padding:10px;
    border-radius:10px;
    cursor:pointer;
}

.results div:hover {
    background:#6366f1;
    color:white;
}

.right {
    background:white;
    padding:24px;
    display:flex;
    flex-direction:column;
}

table {width:100%;}
.qty {width:55px;}

.total {
    font-size:28px;
    font-weight:bold;
    margin-top:auto;
}

button {
    padding:16px;
    background:#6366f1;
    color:white;
    border:none;
    border-radius:14px;
    margin-top:12px;
}

</style>
</head>

<body>

<div class="container">

<div class="left">

<div class="card">
<div class="title">Customer</div>
<input id="cust_search">
<div id="cust_results" class="results"></div>
<div id="selected_customer"></div>
</div>

<div class="card">
<div class="title">Search Product</div>
<input id="search">
<div id="results" class="results"></div>
</div>

</div>

<div class="right">

<h3>Cart</h3>
<table id="cart"></table>

<div id="total" class="total">0.00</div>

<input id="cash" placeholder="Cash (optional)">
<div id="change"></div>

<button onclick="checkout()">Checkout</button>

</div>

</div>

<script>

let products=[],customers=[],cart=[],selectedCustomer=null;

const cartEl=document.getElementById("cart");
const totalEl=document.getElementById("total");
const cashEl=document.getElementById("cash");
const changeEl=document.getElementById("change");

async function load(){
    products=await (await fetch("/products-full")).json();
    customers=await (await fetch("/customers")).json();
}

/* CUSTOMER */
cust_search.oninput=function(){
    let v=this.value.toLowerCase();
    if(!v){cust_results.innerHTML="";return;}
    let f=customers.filter(c=>c.name.toLowerCase().includes(v));
    cust_results.innerHTML=f.map(c=>`<div onclick="selectCustomer('${c.id}','${c.name}')">${c.name}</div>`).join("");
}

function selectCustomer(id,name){
    selectedCustomer=id;
    selected_customer.innerText="✔ "+name;
    cust_search.value="";
    cust_results.innerHTML="";
}

/* SEARCH */
search.oninput=function(){
    let v=this.value.toLowerCase();
    if(!v){results.innerHTML="";return;}
    let f=products.filter(p=>p.name.toLowerCase().includes(v)||p.sku.toLowerCase().includes(v));
    results.innerHTML=f.map(p=>`<div onclick="add('${p.sku}')">${p.name} - ${p.price} (Stock: ${p.stock})</div>`).join("");
}

/* ADD */
function add(sku){
    let p=products.find(x=>x.sku===sku);
    if(!p)return;

    let ex=cart.find(c=>c.sku===sku);
    if(ex){ex.qty++}else{cart.push({...p,qty:1})}

    search.value="";
    results.innerHTML="";
    draw();
}

/* CART */
function draw(){
    let total=0;

    cartEl.innerHTML=cart.map((c,i)=>{
        let t=c.qty*c.price;
        total+=t;

        return `
        <tr>
            <td>${c.name}</td>
            <td><input class="qty" value="${c.qty}" onchange="updateQty(${i},this.value)"></td>
            <td>${t.toFixed(2)}</td>
            <td><button onclick="removeItem(${i})">✕</button></td>
        </tr>`;
    }).join("");

    totalEl.innerText=total.toFixed(2);

    let cashValue = cashEl.value.trim();

    if(cashValue !== ""){
        let cash=parseFloat(cashValue)||0;
        changeEl.innerText="Change: "+(cash-total).toFixed(2);
    }else{
        changeEl.innerText="";
    }
}

function updateQty(i,val){
    cart[i].qty=+val;
    draw();
}

function removeItem(i){
    cart.splice(i,1);
    draw();
}

cashEl.addEventListener("input",draw);

/* CHECKOUT */
async function checkout(){

    if(!selectedCustomer){alert("Select customer");return;}
    if(cart.length===0){alert("Empty cart");return;}

    let total=parseFloat(totalEl.innerText)||0;
    let cash=parseFloat(cashEl.value)||0;

    if(cash && cash < total){
        alert("Not enough cash");
        return;
    }

    let res=await fetch("/invoice",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
            customer_id:selectedCustomer,
            payment_method:"cash",
            items:cart.map(c=>({sku:c.sku,qty:c.qty}))
        })
    });

    let data=await res.json();

    if(data.error){alert(data.error);return;}

    window.location.href="/invoice/"+data.invoice_id;
}

load();

</script>

</body>
</html>
"""