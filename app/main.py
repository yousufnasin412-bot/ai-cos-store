import sqlite3
import os
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = FastAPI()

app.mount("/static", StaticFiles(directory="app"), name="static")

# Database Setup
def init_db():
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            final_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            original_price REAL,
            min_price REAL,
            image_url TEXT
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO products (name, original_price, min_price, image_url)
            VALUES (?, ?, ?, ?)
        """, [
            ("Wireless Headphones", 100.0, 70.0, "https://images.pexels.com/photos/577769/pexels-photo-577769.jpeg?auto=compress&cs=tinysrgb&w=400"),
            ("Smart Watch", 250.0, 180.0, "https://images.pexels.com/photos/437037/pexels-photo-437037.jpeg?auto=compress&cs=tinysrgb&w=400"),
            ("Running Sneakers", 150.0, 110.0, "https://images.pexels.com/photos/2529148/pexels-photo-2529148.jpeg?auto=compress&cs=tinysrgb&w=400")
        ])
    conn.commit()
    conn.close()

init_db()

class NegotiateRequest(BaseModel):
    product_name: str
    original_price: float
    min_price: float
    user_offer: float

class OrderRequest(BaseModel):
    product_name: str
    final_price: float

class ProductRequest(BaseModel):
    name: str
    original_price: float
    min_price: float
    image_url: str

@app.get("/")
def read_root():
    return FileResponse("app/index.html")

@app.get("/admin")
def read_admin():
    return FileResponse("app/admin.html")

@app.get("/api/products")
def get_products():
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, original_price, min_price, image_url FROM products")
    rows = cursor.fetchall()
    conn.close()
    return {"status": "success", "products": [{"id": r[0], "name": r[1], "original_price": r[2], "min_price": r[3], "image_url": r[4]} for r in rows]}

@app.post("/api/products")
def add_product(prod: ProductRequest):
    try:
        conn = sqlite3.connect("orders.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, original_price, min_price, image_url) VALUES (?, ?, ?, ?)",
                       (prod.name, prod.original_price, prod.min_price, prod.image_url))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Product added!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Gemini AI Integration Endpoint
@app.post("/api/negotiate")
def negotiate_price(req: NegotiateRequest):
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Fallback Rule Engine if API Key is not configured yet
    if not api_key:
        if req.user_offer < req.min_price:
            counter = round((req.original_price + req.min_price) / 2, 2)
            return {
                "ai_response": f"Sorry, ${req.user_offer} is too low for {req.product_name}. How about we meet at ${counter}?",
                "deal_ok": False,
                "deal_price": counter
            }
        else:
            return {
                "ai_response": f"Great offer! I can give you {req.product_name} for ${req.user_offer}!",
                "deal_ok": True,
                "deal_price": req.user_offer
            }
    
    # Live Gemini AI Response
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are a friendly E-commerce AI Sales Negotiator for product '{req.product_name}'.
    Original Price: ${req.original_price}
    Minimum Allowed Floor Price: ${req.min_price}
    Customer Offer: ${req.user_offer}

    Instructions:
    1. If customer offer is equal or above minimum floor price (${req.min_price}), ACCEPT the deal politely.
    2. If customer offer is below minimum floor price (${req.min_price}), REJECT politely and offer a counter-price above ${req.min_price}.
    3. Keep response concise (under 25 words).
    """
    
    response = model.generate_content(prompt)
    deal_ok = req.user_offer >= req.min_price
    deal_price = req.user_offer if deal_ok else round((req.original_price + req.min_price) / 2, 2)
    
    return {
        "ai_response": response.text,
        "deal_ok": True,
        "deal_price": deal_price
    }

@app.post("/api/buy")
def place_order(order: OrderRequest):
    try:
        conn = sqlite3.connect("orders.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO orders (product_name, final_price) VALUES (?, ?)", (order.product_name, order.final_price))
        conn.commit()
        order_id = cursor.lastrowid
        conn.close()
        return {"status": "success", "order_id": order_id, "message": "Order saved!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# PDF Invoice Generation Endpoint
@app.get("/api/invoice/{order_id}")
def generate_invoice(order_id: int):
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, product_name, final_price, created_at FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "Order not found"}

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(200, 750, "AI-COS E-Commerce Receipt")
    p.setLineWidth(1)
    p.line(50, 735, 550, 735)

    p.setFont("Helvetica", 12)
    p.drawString(50, 690, f"Order ID: #{row[0]}")
    p.drawString(50, 670, f"Date & Time: {row[3]}")
    p.drawString(50, 650, f"Product Name: {row[1]}")
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 610, f"Total Amount Paid: ${row[2]}")

    p.setFont("Helvetica-Oblique", 10)
    p.drawString(200, 500, "Thank you for shopping with AI-COS Store!")
    p.showPage()
    p.save()

    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=Invoice_Order_{order_id}.pdf"})

@app.get("/api/orders")
def get_orders():
    try:
        conn = sqlite3.connect("orders.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_name, final_price, created_at FROM orders ORDER BY id DESC")
        rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(*), SUM(final_price) FROM orders")
        stats = cursor.fetchone()
        conn.close()
        return {
            "status": "success",
            "orders": [{"id": r[0], "product_name": r[1], "final_price": r[2], "created_at": r[3]} for r in rows],
            "total_orders": stats[0] if stats[0] else 0,
            "total_revenue": round(stats[1], 2) if stats[1] else 0.0
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}