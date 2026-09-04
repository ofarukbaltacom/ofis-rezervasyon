from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
import sqlite3
from datetime import datetime
import csv
import io
app = FastAPI(title="Uydu Ofis Rezervasyon Portalı")
DB_FILE = "reservations.db"
ADMIN_PASSWORD = "kogm2071"
# Varsayılan Lokasyon Kapasiteleri
DEFAULT_CAPACITIES = {
   "Atatürk Havalimanı": 20,
   "Libadiye Teknoloji Ofisi": 30
}
def init_db():
   conn = sqlite3.connect(DB_FILE)
   cursor = conn.cursor()
   cursor.execute("PRAGMA journal_mode=WAL;")
   # Rezervasyonlar Tablosu (Başkanlık ve Müdürlük Eklendi, E-posta Kaldırıldı)
   cursor.execute("""
       CREATE TABLE IF NOT EXISTS reservations (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           name TEXT NOT NULL,
           baskanlik TEXT NOT NULL,
           mudurluk TEXT NOT NULL,
           location TEXT NOT NULL,
           res_date TEXT NOT NULL,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
       )
   """)
   # Özel Tarih Kontenjan Tablosu
   cursor.execute("""
       CREATE TABLE IF NOT EXISTS custom_capacities (
           location TEXT NOT NULL,
           res_date TEXT NOT NULL,
           capacity INTEGER NOT NULL,
           PRIMARY KEY (location, res_date)
       )
   """)
   conn.commit()
   conn.close()
init_db()
def get_db():
   conn = sqlite3.connect(DB_FILE, check_same_thread=False)
   conn.execute("PRAGMA journal_mode=WAL;")
   return conn
# ----------------- API ENDPOINTS -----------------
@app.get("/api/availability")
async def get_availability(date: str):
   conn = get_db()
   cursor = conn.cursor()
   cursor.execute("SELECT location, capacity FROM custom_capacities WHERE res_date = ?", (date,))
   custom_caps = dict(cursor.fetchall())
   cursor.execute("SELECT location, COUNT(*) FROM reservations WHERE res_date = ? GROUP BY location", (date,))
   booked_counts = dict(cursor.fetchall())
   conn.close()
   result = {}
   for loc, default_cap in DEFAULT_CAPACITIES.items():
       capacity = custom_caps.get(loc, default_cap)
       booked = booked_counts.get(loc, 0)
       result[loc] = {
           "capacity": capacity,
           "booked": booked,
           "remaining": max(0, capacity - booked)
       }
   return JSONResponse(content=result)
@app.post("/api/reserve")
async def make_reservation(
   name: str = Form(...),
   baskanlik: str = Form(...),
   mudurluk: str = Form(...),
   location: str = Form(...),
   res_date: str = Form(...)
):
   if location not in DEFAULT_CAPACITIES:
       return JSONResponse(status_code=400, content={"message": "Geçersiz lokasyon seçimi!"})
   # Hafta sonu kontrolü
   dt = datetime.strptime(res_date, "%Y-%m-%d")
   if dt.weekday() >= 5:
       return JSONResponse(status_code=400, content={"message": "Hafta sonları rezervasyon yapılamaz!"})
   conn = get_db()
   cursor = conn.cursor()
   # Mükerrer kayıt kontrolü (Aynı İsim ve Aynı Tarih)
   cursor.execute(
       "SELECT id FROM reservations WHERE LOWER(name) = LOWER(?) AND res_date = ?",
       (name.strip(), res_date)
   )
   if cursor.fetchone():
       conn.close()
       return JSONResponse(status_code=400, content={"message": "Bu isim ile seçilen tarihe zaten bir rezervasyon yapılmış!"})
   # Kontenjan kontrolü
   cursor.execute("SELECT capacity FROM custom_capacities WHERE location = ? AND res_date = ?", (location, res_date))
   custom_row = cursor.fetchone()
   max_capacity = custom_row[0] if custom_row else DEFAULT_CAPACITIES[location]
   cursor.execute("SELECT COUNT(*) FROM reservations WHERE location = ? AND res_date = ?", (location, res_date))
   current_count = cursor.fetchone()[0]
   if current_count >= max_capacity:
       conn.close()
       return JSONResponse(status_code=400, content={"message": f"{location} için {res_date} tarihindeki kontenjan dolmuştur!"})
   # Kaydı Ekle
   cursor.execute(
       "INSERT INTO reservations (name, baskanlik, mudurluk, location, res_date) VALUES (?, ?, ?, ?, ?)",
       (name.strip(), baskanlik, mudurluk, location, res_date)
   )
   conn.commit()
   conn.close()
   return JSONResponse(content={"message": "Rezervasyonunuz başarıyla oluşturuldu!"})
# ----------------- ADMIN API ENDPOINTS -----------------
@app.post("/api/admin/login")
async def admin_login(password: str = Form(...)):
   if password == ADMIN_PASSWORD:
       return JSONResponse(content={"success": True})
   return JSONResponse(status_code=401, content={"message": "Hatalı yönetici parolası!"})
@app.get("/api/admin/reservations")
async def get_all_reservations(password: str):
   if password != ADMIN_PASSWORD:
       return JSONResponse(status_code=401, content={"message": "Yetkisiz erişim!"})
   conn = get_db()
   cursor = conn.cursor()
   cursor.execute("SELECT id, name, baskanlik, mudurluk, location, res_date, created_at FROM reservations ORDER BY res_date DESC, id DESC")
   rows = cursor.fetchall()
   conn.close()
   reservations = [
       {
           "id": r[0],
           "name": r[1],
           "baskanlik": r[2],
           "mudurluk": r[3],
           "location": r[4],
           "res_date": r[5],
           "created_at": r[6]
       }
       for r in rows
   ]
   return JSONResponse(content=reservations)
@app.post("/api/admin/delete-reservation")
async def delete_reservation(id: int = Form(...), password: str = Form(...)):
   if password != ADMIN_PASSWORD:
       return JSONResponse(status_code=401, content={"message": "Yetkisiz erişim!"})
   conn = get_db()
   cursor = conn.cursor()
   cursor.execute("DELETE FROM reservations WHERE id = ?", (id,))
   conn.commit()
   conn.close()
   return JSONResponse(content={"message": "Rezervasyon silindi."})
@app.post("/api/admin/set-capacity")
async def set_capacity(
   location: str = Form(...),
   res_date: str = Form(...),
   capacity: int = Form(...),
   password: str = Form(...)
):
   if password != ADMIN_PASSWORD:
       return JSONResponse(status_code=401, content={"message": "Yetkisiz erişim!"})
   conn = get_db()
   cursor = conn.cursor()
   cursor.execute("""
       INSERT INTO custom_capacities (location, res_date, capacity)
       VALUES (?, ?, ?)
       ON CONFLICT(location, res_date) DO UPDATE SET capacity = excluded.capacity
   """, (location, res_date, capacity))
   conn.commit()
   conn.close()
   return JSONResponse(content={"message": f"{location} - {res_date} için kontenjan {capacity} olarak güncellendi."})
@app.get("/api/admin/export-excel")
async def export_excel(password: str):
   if password != ADMIN_PASSWORD:
       return JSONResponse(status_code=401, content={"message": "Yetkisiz erişim!"})
   conn = get_db()
   cursor = conn.cursor()
   cursor.execute("SELECT id, name, baskanlik, mudurluk, location, res_date, created_at FROM reservations ORDER BY res_date DESC")
   rows = cursor.fetchall()
   conn.close()
   output = io.StringIO()
   writer = csv.writer(output, delimiter=';')
   writer.writerow(["ID", "Ad Soyad", "Başkanlık", "Müdürlük", "Lokasyon", "Rezervasyon Tarihi", "Kayıt Tarihi"])
   for row in rows:
       writer.writerow(row)
   response = Response(content=output.getvalue().encode('utf-8-sig'), media_type="text/csv")
   response.headers["Content-Disposition"] = "attachment; filename=Eylul_2026_Uydu_Ofis_Rezervasyonlari.csv"
   return response
# ----------------- MAIN UI HTML -----------------
@app.get("/", response_class=HTMLResponse)
async def index():
   html_content = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Uydu Ofis Rezervasyon Portalı</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-100 min-h-screen text-slate-800 font-sans">
<!-- Header -->
<header class="bg-slate-900 text-white shadow-lg border-b-4 border-red-600">
<div class="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
<div class="flex items-center space-x-3">
<i class="fa-solid fa-plane-departure text-red-500 text-2xl"></i>
<div>
<h1 class="text-xl font-bold tracking-wide">Uydu Ofis Rezervasyon Portalı</h1>
<p class="text-xs text-slate-400">Turkish Cargo - Eylül 2026 Çalışma Takvimi</p>
</div>
</div>
<div class="flex items-center space-x-3">
<button onclick="toggleAdminModal()" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 px-3 py-1.5 rounded-lg transition flex items-center space-x-1">
<i class="fa-solid fa-user-shield text-red-400"></i>
<span>Admin Paneli</span>
</button>
</div>
</div>
</header>
<!-- Main Content -->
<main class="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 md:grid-cols-2 gap-8">
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
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Başkanlık</label>
<select id="baskanlik" onchange="updateMudurlukOptions()" required
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm bg-white">
<option value="">Başkanlık Seçiniz</option>
<option value="Kargo Operasyon Başkanlığı">Kargo Operasyon Başkanlığı</option>
<option value="Kargo Satış Başkanlığı">Kargo Satış Başkanlığı</option>
<option value="Kargo Pazarlama Başkanlığı">Kargo Pazarlama Başkanlığı</option>
<option value="Kargo Gelir Yönetimi ve Ürün Planlama Başkanlığı">Kargo Gelir Yönetimi ve Ürün Planlama Başkanlığı</option>
<option value="Genel Müdür (Kargo) Yardımcılığı">Genel Müdür (Kargo) Yardımcılığı</option>
</select>
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Müdürlük</label>
<select id="mudurluk" required
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm bg-white">
<option value="">Önce Başkanlık Seçiniz</option>
</select>
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Lokasyon Seçimi</label>
<select id="location" onchange="updateAvailability()"
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm bg-white">
<option value="Atatürk Havalimanı">Atatürk Havalimanı (Maks 20 Kişi)</option>
<option value="Libadiye Teknoloji Ofisi">Libadiye Teknoloji Ofisi (Maks 30 Kişi)</option>
</select>
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Eylül 2026 Çalışma Günü</label>
<input type="date" id="res_date" value="2026-09-01" min="2026-09-01" max="2026-09-30" onchange="validateDateAndFetch()"
                           class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm">
<p id="dateWarning" class="text-xs text-rose-600 mt-1 hidden"><i class="fa-solid fa-circle-exclamation"></i> Hafta sonları seçim yapılamaz. Lütfen bir iş günü seçin.</p>
</div>
<div class="flex items-start space-x-2 pt-2">
<input type="checkbox" id="rulesCheck" required class="mt-0.5 rounded text-red-600 focus:ring-red-500">
<label for="rulesCheck" class="text-xs text-slate-600 leading-tight">
                           Uydu ofis çalışma esaslarını ve talimatnamelerini kabul ediyorum.
</label>
</div>
<button type="submit" id="submitBtn"
                       class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg transition duration-150 flex items-center justify-center space-x-2 text-sm shadow cursor-pointer">
<i class="fa-solid fa-check"></i>
<span>Rezervasyonu Tamamla</span>
</button>
</form>
<div id="alertBox" class="mt-4 hidden p-3 rounded-lg text-xs font-medium"></div>
</section>
<!-- Sağ Panel: Anlık Kontenjan Durumu -->
<section class="space-y-6">
<div class="bg-white rounded-xl shadow-md p-6 border border-slate-200">
<h3 class="text-sm font-bold text-slate-700 uppercase tracking-wider border-b pb-3 mb-4 flex justify-between items-center">
<span><i class="fa-solid fa-chart-pie text-slate-500 mr-2"></i> Anlık Kontenjan Durumu</span>
<span id="selectedDateBadge" class="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded border"></span>
</h3>
<div id="statusCards" class="space-y-4">
<!-- JS Dynamic Cards -->
</div>
</div>
<div class="bg-slate-50 rounded-xl p-5 border border-slate-200 text-xs text-slate-600 space-y-2">
<p class="font-bold text-slate-700"><i class="fa-solid fa-circle-info text-blue-500 mr-1"></i> Eylül 2026 Rezervasyon Esasları:</p>
<p>• Rezervasyonlar Eylül 2026 ayındaki <b>Pazartesi - Cuma</b> günleri için geçerlidir.</p>
<p>• Atatürk Havalimanı kontenjanı <b>20</b>, Libadiye Teknoloji Ofisi kontenjanı <b>30</b> kişidir.</p>
<p>• Sistem e-posta adresi gerektirmez, Ad Soyad ve Birim eşleşmesiyle çalışır.</p>
</div>
</section>
</main>
<!-- ADMIN MODAL -->
<div id="adminModal" class="fixed inset-0 bg-black/60 hidden backdrop-blur-sm flex items-center justify-center p-4 z-50">
<div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-300">
<!-- Modal Header -->
<div class="bg-slate-900 text-white px-6 py-4 flex justify-between items-center border-b border-slate-700">
<div class="flex items-center space-x-2">
<i class="fa-solid fa-user-shield text-red-500"></i>
<h3 class="font-bold text-base">Yönetici Kontrol Paneli</h3>
</div>
<button onclick="toggleAdminModal()" class="text-slate-400 hover:text-white text-lg"><i class="fa-solid fa-xmark"></i></button>
</div>
<!-- Modal Body -->
<div class="p-6 overflow-y-auto space-y-6">
<!-- Login Form -->
<div id="adminLoginForm" class="max-w-sm mx-auto my-8 space-y-4 text-center">
<i class="fa-solid fa-lock text-slate-400 text-4xl mb-2"></i>
<h4 class="font-bold text-slate-800">Admin Girişi Yapın</h4>
<input type="password" id="adminPass" placeholder="Yönetici Parolası" class="w-full px-3 py-2 border rounded-lg text-sm text-center focus:ring-2 focus:ring-red-500 outline-none">
<button onclick="loginAdmin()" class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 rounded-lg text-sm transition">Giriş Yap</button>
<p id="adminLoginErr" class="text-xs text-rose-600 hidden"></p>
</div>
<!-- Admin Content (Giriş Sonrası) -->
<div id="adminContent" class="hidden space-y-6">
<!-- Kontenjan Güncelleme Paneli -->
<div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
<h4 class="text-xs font-bold text-slate-700 uppercase mb-3 flex items-center">
<i class="fa-solid fa-sliders text-red-600 mr-2"></i> Eylül 2026 Tarih Bazlı Kontenjan Güncelle
</h4>
<div class="grid grid-cols-1 sm:grid-cols-4 gap-3">
<select id="adminLoc" class="px-2 py-1.5 border rounded text-xs">
<option value="Atatürk Havalimanı">Atatürk Havalimanı</option>
<option value="Libadiye Teknoloji Ofisi">Libadiye Teknoloji Ofisi</option>
</select>
<input type="date" id="adminDate" value="2026-09-01" min="2026-09-01" max="2026-09-30" class="px-2 py-1.5 border rounded text-xs">
<input type="number" id="adminCap" placeholder="Yeni Kapasite" min="0" class="px-2 py-1.5 border rounded text-xs">
<button onclick="setCustomCapacity()" class="bg-slate-800 hover:bg-slate-900 text-white text-xs py-1.5 px-3 rounded font-medium transition">Güncelle</button>
</div>
</div>
<!-- Rezervasyon Listesi ve Excel İndir -->
<div>
<div class="flex justify-between items-center mb-3">
<h4 class="text-xs font-bold text-slate-700 uppercase flex items-center">
<i class="fa-solid fa-list-check text-slate-600 mr-2"></i> Tüm Eylül Rezervasyonları
</h4>
<button onclick="downloadExcel()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition flex items-center space-x-1">
<i class="fa-solid fa-file-excel"></i>
<span>Excel / CSV İndir</span>
</button>
</div>
<div class="border rounded-xl overflow-x-auto">
<table class="w-full text-left text-xs">
<thead class="bg-slate-100 text-slate-700 uppercase border-b">
<tr>
<th class="p-2.5">Ad Soyad</th>
<th class="p-2.5">Başkanlık</th>
<th class="p-2.5">Müdürlük</th>
<th class="p-2.5">Lokasyon</th>
<th class="p-2.5">Tarih</th>
<th class="p-2.5 text-center">İşlem</th>
</tr>
</thead>
<tbody id="resTableBody" class="divide-y text-slate-600">
<!-- Dynamic Table Rows -->
</tbody>
</table>
</div>
</div>
</div>
</div>
</div>
</div>
<script>
           let currentAdminPass = "";
           const mudurlukData = {
               "Kargo Operasyon Başkanlığı": ["Kargo Handling Anlaşmaları Müdürlüğü", "Kargo Operasyonel Performans Müdürlüğü", "Kargo Uçuş Operasyon Kontrol Müdürlüğü", "Kargo Güvenlik Müdürlüğü", "Özel Kargo ve Operasyonel Hizmetler Müdürlüğü"],
               "Kargo Satış Başkanlığı": ["Kargo Kurumsal Müşteriler Müdürlüğü", "Kargo Dijital Satış Müdürlüğü", "Kargo Bölge Müdürlüğü (İstanbul)", "Kargo Bölge Müdürlüğü (Anadolu)"],
               "Kargo Pazarlama Başkanlığı": ["Kargo Ürün Geliştirme Müdürlüğü", "Kargo Pazarlama İletişimi Müdürlüğü"],
               "Kargo Gelir Yönetimi ve Ürün Planlama Başkanlığı": ["Kargo Fiyatlandırma Müdürlüğü", "Kargo Kapasite Planlama Müdürlüğü"],
               "Genel Müdür (Kargo) Yardımcılığı": ["Kargo Organizasyonel Gelişim Müdürlüğü", "Kargo İnsan Kaynakları Müdürlüğü"]
           };
           function updateMudurlukOptions() {
               const baskanlikSelect = document.getElementById("baskanlik");
               const mudurlukSelect = document.getElementById("mudurluk");
               const selectedBaskanlik = baskanlikSelect.value;
               mudurlukSelect.innerHTML = '<option value="">Müdürlük Seçiniz</option>';
               if (selectedBaskanlik && mudurlukData[selectedBaskanlik]) {
                   mudurlukData[selectedBaskanlik].forEach(m => {
                       const opt = document.createElement("option");
                       opt.value = m;
                       opt.innerText = m;
                       mudurlukSelect.appendChild(opt);
                   });
               }
           }
           function validateDateAndFetch() {
               const dateInput = document.getElementById("res_date");
               const warning = document.getElementById("dateWarning");
               const submitBtn = document.getElementById("submitBtn");
               const date = new Date(dateInput.value);
               const day = date.getUTCDay();
               if (day === 0 || day === 6) { // Pazar veya Cumartesi
                   warning.classList.remove("hidden");
                   submitBtn.disabled = true;
                   submitBtn.classList.add("opacity-50", "cursor-not-allowed");
               } else {
                   warning.classList.add("hidden");
                   submitBtn.disabled = false;
                   submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
                   updateAvailability();
               }
           }
           async function updateAvailability() {
               const date = document.getElementById("res_date").value;
               if (!date) return;
               document.getElementById("selectedDateBadge").innerText = date;
               try {
                   const res = await fetch(`/api/availability?date=${date}`);
                   const data = await res.json();
                   renderStatusCards(data);
               } catch (e) {
                   console.error("Kontenjan çekilemedi:", e);
               }
           }
           function renderStatusCards(data) {
               const container = document.getElementById("statusCards");
               container.innerHTML = "";
               const selectedLoc = document.getElementById("location").value;
               for (const [locName, info] of Object.entries(data)) {
                   const isSelected = locName === selectedLoc;
                   const isFull = info.remaining <= 0;
                   const percent = Math.round((info.booked / info.capacity) * 100);
                   const card = document.createElement("div");
                   card.className = `p-4 rounded-xl border transition ${
                       isSelected ? 'border-red-500 bg-red-50/30' : 'border-slate-200 bg-white'
                   }`;
                   card.innerHTML = `
<div class="flex justify-between items-center mb-2">
<span class="font-bold text-sm text-slate-800">${locName}</span>
<span class="text-xs font-semibold px-2 py-0.5 rounded-full ${
                               isFull ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'
                           }">
                               ${isFull ? 'Doldu' : info.remaining + ' Boş Kontenjan'}
</span>
</div>
<div class="w-full bg-slate-200 rounded-full h-2 mb-2 overflow-hidden">
<div class="bg-red-600 h-2 rounded-full transition-all duration-300" style="width: ${percent}%"></div>
</div>
<div class="flex justify-between text-xs text-slate-500">
<span>Rezerve: <b>${info.booked}</b> / ${info.capacity}</span>
<span>Doluluk: %${percent}</span>
</div>
                   `;
                   container.appendChild(card);
               }
           }
           async function handleReserve(event) {
               event.preventDefault();
               const alertBox = document.getElementById("alertBox");
               alertBox.className = "mt-4 hidden p-3 rounded-lg text-xs font-medium";
               const formData = new FormData();
               formData.append("name", document.getElementById("name").value);
               formData.append("baskanlik", document.getElementById("baskanlik").value);
               formData.append("mudurluk", document.getElementById("mudurluk").value);
               formData.append("location", document.getElementById("location").value);
               formData.append("res_date", document.getElementById("res_date").value);
               try {
                   const response = await fetch("/api/reserve", {
                       method: "POST",
                       body: formData
                   });
                   const result = await response.json();
                   if (response.ok) {
                       alertBox.innerText = result.message;
                       alertBox.classList.remove("hidden");
                       alertBox.classList.add("bg-emerald-100", "text-emerald-800", "border", "border-emerald-300");
                       document.getElementById("resForm").reset();
                       document.getElementById("res_date").value = "2026-09-01";
                       updateAvailability();
                   } else {
                       alertBox.innerText = result.message || "Bir hata oluştu.";
                       alertBox.classList.remove("hidden");
                       alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
                   }
               } catch (e) {
                   alertBox.innerText = "Bağlantı hatası oluştu.";
                   alertBox.classList.remove("hidden");
                   alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
               }
           }
           function toggleAdminModal() {
               const modal = document.getElementById("adminModal");
               modal.classList.toggle("hidden");
           }
           async function loginAdmin() {
               const pass = document.getElementById("adminPass").value;
               const err = document.getElementById("adminLoginErr");
               const formData = new FormData();
               formData.append("password", pass);
               const res = await fetch("/api/admin/login", { method: "POST", body: formData });
               if (res.ok) {
                   currentAdminPass = pass;
                   document.getElementById("adminLoginForm").classList.add("hidden");
                   document.getElementById("adminContent").classList.remove("hidden");
                   loadAdminReservations();
               } else {
                   err.innerText = "Hatalı parola!";
                   err.classList.remove("hidden");
               }
           }
           async function loadAdminReservations() {
               const res = await fetch(`/api/admin/reservations?password=${currentAdminPass}`);
               if (!res.ok) return;
               const data = await res.json();
               const tbody = document.getElementById("resTableBody");
               tbody.innerHTML = "";
               data.forEach(r => {
                   const tr = document.createElement("tr");
                   tr.innerHTML = `
<td class="p-2.5 font-medium text-slate-800">${r.name}</td>
<td class="p-2.5 text-slate-500">${r.baskanlik}</td>
<td class="p-2.5 text-slate-500">${r.mudurluk}</td>
<td class="p-2.5 font-medium">${r.location}</td>
<td class="p-2.5 font-semibold text-red-600">${r.res_date}</td>
<td class="p-2.5 text-center">
<button onclick="deleteRes(${r.id})" class="text-rose-600 hover:text-rose-800"><i class="fa-solid fa-trash"></i></button>
</td>
                   `;
                   tbody.appendChild(tr);
               });
           }
           async function deleteRes(id) {
               if (!confirm("Bu kaydı silmek istediğinize emin misiniz?")) return;
               const formData = new FormData();
               formData.append("id", id);
               formData.append("password", currentAdminPass);
               await fetch("/api/admin/delete-reservation", { method: "POST", body: formData });
               loadAdminReservations();
               updateAvailability();
           }
           async function setCustomCapacity() {
               const loc = document.getElementById("adminLoc").value;
               const date = document.getElementById("adminDate").value;
               const cap = document.getElementById("adminCap").value;
               if (!cap) return alert("Lütfen geçerli bir kapasite girin.");
               const formData = new FormData();
               formData.append("location", loc);
               formData.append("res_date", date);
               formData.append("capacity", cap);
               formData.append("password", currentAdminPass);
               const res = await fetch("/api/admin/set-capacity", { method: "POST", body: formData });
               if (res.ok) {
                   alert("Kontenjan başarıyla güncellendi.");
                   updateAvailability();
               }
           }
           function downloadExcel() {
               window.location.href = `/api/admin/export-excel?password=${currentAdminPass}`;
           }
           window.onload = validateDateAndFetch;
</script>
</body>
</html>
   """
   return HTMLResponse(content=html_content)
