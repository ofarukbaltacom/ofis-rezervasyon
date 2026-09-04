from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
from datetime import datetime
import json
app = FastAPI(title="Uydu Ofis Rezervasyon Sistemi")
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
           location TEXT NOT NULL,
           desk_id TEXT NOT NULL,
           res_date TEXT NOT NULL,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
       )
   """)
   conn.commit()
   conn.close()
init_db()
def get_db():
   conn = sqlite3.connect(DB_FILE, check_same_thread=False)
   conn.execute("PRAGMA journal_mode=WAL;")
   return conn
# Lokasyon ve Masa Tanımlamaları
LOCATIONS = {
   "Atatürk Havalimanı": {
       "capacity": 12,
       "desks": [f"AHL-Masa-{i}" for i in range(1, 13)]
   },
   "Libadiye Teknoloji Ofisi": {
       "capacity": 8,
       "desks": [f"LBD-Masa-{i}" for i in range(1, 9)]
   }
}
@app.get("/api/reservations")
async def get_reservations(date: str, location: str):
   conn = get_db()
   cursor = conn.cursor()
   cursor.execute(
       "SELECT desk_id, name, email FROM reservations WHERE res_date = ? AND location = ?",
       (date, location)
   )
   rows = cursor.fetchall()
   conn.close()
   reserved_desks = {row[0]: {"name": row[1], "email": row[2]} for row in rows}
   return JSONResponse(content={"reserved": reserved_desks})
@app.post("/api/reserve")
async def make_reservation(
   name: str = Form(...),
   email: str = Form(...),
   location: str = Form(...),
   desk_id: str = Form(...),
   res_date: str = Form(...)
):
   conn = get_db()
   cursor = conn.cursor()
   # Çift rezervasyon kontrolü
   cursor.execute(
       "SELECT id FROM reservations WHERE location = ? AND desk_id = ? AND res_date = ?",
       (location, desk_id, res_date)
   )
   if cursor.fetchone():
       conn.close()
       return JSONResponse(status_code=400, content={"message": "Seçilen masa bu tarihte zaten rezerve edilmiş!"})
   cursor.execute(
       "INSERT INTO reservations (name, email, location, desk_id, res_date) VALUES (?, ?, ?, ?, ?)",
       (name, email, location, desk_id, res_date)
   )
   conn.commit()
   conn.close()
   return JSONResponse(content={"message": "Rezervasyonunuz başarıyla kaydedildi!"})
@app.get("/", response_class=HTMLResponse)
async def index():
   today = datetime.now().strftime("%Y-%m-%d")
   locations_json = json.dumps(LOCATIONS)
   html_content = f"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Uydu Ofis Rezervasyon Portalı</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
<style>
           .desk-card {{
               transition: all 0.2s ease-in-out;
           }}
           .desk-card:hover {{
               transform: translateY(-2px);
           }}
</style>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800">
<!-- Header -->
<header class="bg-slate-900 text-white shadow-lg border-b border-red-600">
<div class="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
<div class="flex items-center space-x-3">
<i class="fa-solid fa-building-user text-red-500 text-2xl"></i>
<div>
<h1 class="text-xl font-bold tracking-wide">Uydu Ofis Rezervasyon Portalı</h1>
<p class="text-xs text-slate-400">Atatürk Havalimanı & Libadiye Teknoloji Ofisleri</p>
</div>
</div>
<div class="text-right hidden sm:block">
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
<span class="w-2 h-2 mr-1.5 bg-emerald-500 rounded-full animate-pulse"></span> Canlı Sistem
</span>
</div>
</div>
</header>
<!-- Main Layout -->
<main class="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
<!-- Sol Panel: Rezervasyon Formu -->
<section class="bg-white rounded-xl shadow-md p-6 border border-slate-200">
<h2 class="text-lg font-semibold text-slate-900 border-b pb-3 mb-5 flex items-center">
<i class="fa-regular fa-calendar-check text-red-600 mr-2"></i> Rezervasyon Oluştur
</h2>
<form id="resForm" onsubmit="handleReserve(event)" class="space-y-4">
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Ad Soyad</label>
<input type="text" id="name" required placeholder="Örn: Ömer Faruk Balta"
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm">
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">E-Posta Adresi</label>
<input type="email" id="email" required placeholder="ornek@thy.com"
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm">
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Lokasyon Seçimi</label>
<select id="location" onchange="updateView()"
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm bg-white">
<option value="Atatürk Havalimanı">Atatürk Havalimanı</option>
<option value="Libadiye Teknoloji Ofisi">Libadiye Teknoloji Ofisi</option>
</select>
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Rezervasyon Tarihi</label>
<input type="date" id="res_date" value="{today}" onchange="updateView()" min="{today}"
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm">
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Seçilen Masa</label>
<input type="text" id="desk_id" readonly placeholder="Haritadan/Listeden Masa Seçin" required
                           class="w-full px-3 py-2 border border-slate-200 bg-slate-100 rounded-lg text-sm font-semibold text-red-600">
</div>
<button type="submit"
                       class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg transition duration-150 flex items-center justify-center space-x-2 text-sm shadow">
<i class="fa-solid fa-check"></i>
<span>Rezervasyonu Onayla</span>
</button>
</form>
<div id="alertBox" class="mt-4 hidden p-3 rounded-lg text-xs font-medium"></div>
</section>
<!-- Sağ Panel: İnteraktif Kat Planı ve Masalar -->
<section class="lg:col-span-2 space-y-6">
<!-- Kapasite Özet Kartı -->
<div class="bg-white rounded-xl shadow-md p-6 border border-slate-200 flex flex-wrap items-center justify-between gap-4">
<div>
<h3 id="locTitle" class="text-xl font-bold text-slate-800">Atatürk Havalimanı</h3>
<p class="text-xs text-slate-500 mt-0.5">Masa durumunu görmek için tarih seçiniz.</p>
</div>
<div class="flex items-center space-x-6 text-sm">
<div class="flex items-center space-x-2">
<span class="w-3.5 h-3.5 bg-emerald-500 rounded-md inline-block"></span>
<span class="text-xs text-slate-600 font-medium">Boş: <b id="statFree" class="text-slate-800">0</b></span>
</div>
<div class="flex items-center space-x-2">
<span class="w-3.5 h-3.5 bg-rose-500 rounded-md inline-block"></span>
<span class="text-xs text-slate-600 font-medium">Dolu: <b id="statBusy" class="text-slate-800">0</b></span>
</div>
</div>
</div>
<!-- Masa Izgarası (Kat Planı Görünümü) -->
<div class="bg-white rounded-xl shadow-md p-6 border border-slate-200">
<div class="flex items-center justify-between mb-4 border-b pb-2">
<h4 class="text-sm font-bold text-slate-700 uppercase tracking-wider">Ofis Kat Planı & Masa Seçimi</h4>
<span class="text-xs text-slate-400"><i class="fa-solid fa-mouse-pointer mr-1"></i> Masa seçmek için tıklayın</span>
</div>
<div id="deskGrid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
<!-- Javascript ile dinamik dolacak -->
</div>
</div>
</section>
</main>
<script>
           const locations = {locations_json};
           let reservedDesks = {{}};
           let selectedDesk = "";
           async function updateView() {{
               const location = document.getElementById("location").value;
               const date = document.getElementById("res_date").value;
               document.getElementById("locTitle").innerText = location;
               // Formdaki seçili masayı sıfırla
               selectedDesk = "";
               document.getElementById("desk_id").value = "";
               if (!date) return;
               try {{
                   const res = await fetch(`/api/reservations?date=${{date}}&location=${{encodeURIComponent(location)}}`);
                   const data = await res.json();
                   reservedDesks = data.reserved || {{}};
                   renderDesks(location);
               }} catch (e) {{
                   console.error("Veriler alınamadı:", e);
               }}
           }}
           function renderDesks(location) {{
               const grid = document.getElementById("deskGrid");
               grid.innerHTML = "";
               const desks = locations[location].desks;
               let busyCount = 0;
               desks.forEach(deskId => {{
                   const isReserved = reservedDesks.hasOwnProperty(deskId);
                   if (isReserved) busyCount++;
                   const isSelected = selectedDesk === deskId;
                   const card = document.createElement("div");
                   card.className = `desk-card border-2 rounded-xl p-4 cursor-pointer text-center relative transition ${
                       isReserved
                           ? 'bg-rose-50 border-rose-200 text-rose-700 cursor-not-allowed'
                           : isSelected
                               ? 'bg-red-50 border-red-600 text-red-700 ring-2 ring-red-400'
                               : 'bg-slate-50 border-slate-200 hover:border-slate-400 text-slate-700'
                   }`;
                   let statusBadge = isReserved
                       ? `<span class="text-[10px] font-semibold bg-rose-200 text-rose-800 px-2 py-0.5 rounded-full block mt-2 truncate">${{reservedDesks[deskId].name}}</span>`
                       : `<span class="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full block mt-2">Uygun</span>`;
                   card.innerHTML = `
<div class="text-2xl mb-1"><i class="fa-solid fa-desktop"></i></div>
<div class="text-xs font-bold">${{deskId}}</div>
                       ${{statusBadge}}
                   `;
                   if (!isReserved) {{
                       card.onclick = () => selectDesk(deskId);
                   }}
                   grid.appendChild(card);
               }});
               document.getElementById("statBusy").innerText = busyCount;
               document.getElementById("statFree").innerText = desks.length - busyCount;
           }}
           function selectDesk(deskId) {{
               selectedDesk = deskId;
               document.getElementById("desk_id").value = deskId;
               renderDesks(document.getElementById("location").value);
           }}
           async function handleReserve(event) {{
               event.preventDefault();
               const alertBox = document.getElementById("alertBox");
               alertBox.className = "mt-4 hidden p-3 rounded-lg text-xs font-medium";
               const formData = new FormData();
               formData.append("name", document.getElementById("name").value);
               formData.append("email", document.getElementById("email").value);
               formData.append("location", document.getElementById("location").value);
               formData.append("desk_id", document.getElementById("desk_id").value);
               formData.append("res_date", document.getElementById("res_date").value);
               try {{
                   const response = await fetch("/api/reserve", {{
                       method: "POST",
                       body: formData
                   }});
                   const result = await response.json();
                   if (response.ok) {{
                       alertBox.innerText = result.message;
                       alertBox.classList.remove("hidden");
                       alertBox.classList.add("bg-emerald-100", "text-emerald-800", "border", "border-emerald-300");
                       updateView();
                   }} else {{
                       alertBox.innerText = result.message || "Bir hata oluştu.";
                       alertBox.classList.remove("hidden");
                       alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
                   }}
               }} catch (e) {{
                   alertBox.innerText = "Bağlantı hatası oluştu.";
                   alertBox.classList.remove("hidden");
                   alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
               }}
           }}
           // Sayfa yüklendiğinde masaları çek
           window.onload = updateView;
</script>
</body>
</html>
   """
   return html_content
