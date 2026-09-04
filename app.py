from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import pandas as pd
import os
app = FastAPI(title="Uydu Ofis Rezervasyon")
# SQLite WAL Modu Konfigürasyonu (Yüksek Eşzamanlılık İçin)
DB_FILE = "reservations.db"
def init_db():
   conn = sqlite3.connect(DB_FILE)
   cursor = conn.cursor()
   cursor.execute("PRAGMA journal_mode=WAL;")
   cursor.execute("""
       CREATE TABLE IF NOT EXISTS reservations (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           name TEXT NOT NULL,
           email TEXT NOT NULL,
           date TEXT NOT NULL,
           desk_id TEXT NOT NULL
       )
   """)
   conn.commit()
   conn.close()
init_db()
def get_db_connection():
   conn = sqlite3.connect(DB_FILE, check_same_thread=False)
   conn.execute("PRAGMA journal_mode=WAL;")
   return conn
# Ana Sayfa / Arayüz
@app.get("/", response_class=HTMLResponse)
async def read_root():
   return """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Uydu Ofis Rezervasyon</title>
<style>
           body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f7f6; }
           .container { max-width: 600px; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
           h2 { color: #333; }
           input, select, button { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
           button { background-color: #007bff; color: white; border: none; cursor: pointer; font-weight: bold; }
           button:hover { background-color: #0056b3; }
</style>
</head>
<body>
<div class="container">
<h2>Uydu Ofis Rezervasyon Formu</h2>
<form action="/api/reserve" method="post">
<label>Ad Soyad:</label>
<input type="text" name="name" required>
<label>E-posta:</label>
<input type="email" name="email" required>
<label>Tarih:</label>
<input type="date" name="date" required>
<label>Masa / Alan Seçimi:</label>
<select name="desk_id">
<option value="Masa-1">Masa 1</option>
<option value="Masa-2">Masa 2</option>
<option value="Masa-3">Masa 3</option>
</select>
<button type="submit">Rezervasyon Yap</button>
</form>
</div>
</body>
</html>
   """
# Rezervasyon Kayıt API
@app.post("/api/reserve")
async def create_reservation(name: str = Form(...), email: str = Form(...), date: str = Form(...), desk_id: str = Form(...)):
   conn = get_db_connection()
   cursor = conn.cursor()
   cursor.execute(
       "INSERT INTO reservations (name, email, date, desk_id) VALUES (?, ?, ?, ?)",
       (name, email, date, desk_id)
   )
   conn.commit()
   conn.close()
   return JSONResponse(content={"status": "success", "message": "Rezervasyon başarıyla oluşturuldu."})
