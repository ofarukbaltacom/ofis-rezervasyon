from datetime import datetime, timedelta
import csv
import io
import json
import os
import random
import string
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
import sqlite3
app = FastAPI(title="Uydu Ofis Rezervasyon Portalı")
# Veritabanının sunucu yeniden başlatmalarında silinmemesi için kalıcı bir dizin kullanıyoruz
# Sunucu ortamına göre kalıcı bir klasör (/tmp veya ana dizin)
PERSISTENT_DIR = os.path.expanduser("~")
if not os.path.exists(PERSISTENT_DIR):
 PERSISTENT_DIR = "/tmp"
DB_FILE = os.path.join(PERSISTENT_DIR, "uydu_ofis_reservations_v2.db")
ADMIN_PASSWORD = "kogm2071"
DEFAULT_CAPACITIES = {
   "Atatürk Havalimanı": 20,
   "Libadiye Teknoloji Ofisi": 30,
}
# Eylül 2026 Çalışma Haftaları (Pazartesi - Cuma)
SEPTEMBER_2026_WEEKS = {
   "1. Hafta (1 - 4 Eylül)": [
       "2026-09-01",
       "2026-09-02",
       "2026-09-03",
       "2026-09-04",
   ],
   "2. Hafta (7 - 11 Eylül)": [
       "2026-09-07",
       "2026-09-08",
       "2026-09-09",
       "2026-09-10",
       "2026-09-11",
   ],
   "3. Hafta (14 - 18 Eylül)": [
       "2026-09-14",
       "2026-09-15",
       "2026-09-16",
       "2026-09-17",
       "2026-09-18",
   ],
   "4. Hafta (21 - 25 Eylül)": [
       "2026-09-21",
       "2026-09-22",
       "2026-09-23",
       "2026-09-24",
       "2026-09-25",
   ],
   "5. Hafta (28 - 30 Eylül)": ["2026-09-28", "2026-09-29", "2026-09-30"],
}

def generate_pnr(sicil: str):
 chars = string.ascii_uppercase + string.digits
 random_suffix = "".join(random.choices(chars, k=4))
 return f"TK-{sicil.strip().upper()}-{random_suffix}"

def init_db():
 conn = sqlite3.connect(DB_FILE)
 cursor = conn.cursor()
 cursor.execute("PRAGMA journal_mode=WAL;")
 cursor.execute("""
      CREATE TABLE IF NOT EXISTS reservations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          pnr TEXT NOT NULL,
          sicil TEXT NOT NULL,
          name TEXT NOT NULL,
          baskanlik TEXT NOT NULL,
          mudurluk TEXT NOT NULL,
          location TEXT NOT NULL,
          res_date TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  """)
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
@app.get("/api/all-availability")
async def get_all_availability():
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute("SELECT location, res_date, capacity FROM custom_capacities")
 custom_caps = {}
 for loc, d, cap in cursor.fetchall():
   custom_caps[(loc, d)] = cap
 cursor.execute("SELECT location, res_date, COUNT(*) FROM reservations GROUP BY location, res_date")
 booked_counts = {}
 for loc, d, cnt in cursor.fetchall():
   booked_counts[(loc, d)] = cnt
 conn.close()
 result = {}
 locations = ["Atatürk Havalimanı", "Libadiye Teknoloji Ofisi"]
 for loc in locations:
   result[loc] = {}
   default_cap = DEFAULT_CAPACITIES.get(loc, 20)
   for week_name, days in SEPTEMBER_2026_WEEKS.items():
     for d in days:
       cap = custom_caps.get((loc, d), default_cap)
       booked = booked_counts.get((loc, d), 0)
       result[loc][d] = {
           "capacity": cap,
           "booked": booked,
           "remaining": max(0, cap - booked),
       }
 return JSONResponse(content=result)

@app.post("/api/reserve")
async def make_reservation(
   sicil: str = Form(...),
   name: str = Form(...),
   baskanlik: str = Form(...),
   mudurluk: str = Form(...),
   selections_json: str = Form(...),
):
 try:
   selections = json.loads(selections_json)
 except:
   return JSONResponse(
       status_code=400, content={"message": "Geçersiz seçim formatı!"}
   )
 if not selections:
   return JSONResponse(
       status_code=400, content={"message": "Lütfen en az bir ofis ve gün seçiniz!"}
   )
 selected_dates = [s["date"] for s in selections]
 for week_name, days in SEPTEMBER_2026_WEEKS.items():
   count_in_week = sum(1 for d in selected_dates if d in days)
   if count_in_week > 2:
     return JSONResponse(
         status_code=400,
         content={
             "message": (
                 f"{week_name} içerisinde toplamda 2 günden fazla seçim"
                 " yapamazsınız!"
             )
         },
     )
 conn = get_db()
 cursor = conn.cursor()
 errors = []
 valid_items = []
 for item in selections:
   loc = item["location"]
   res_date = item["date"]
   cursor.execute(
       "SELECT id FROM reservations WHERE LOWER(name) = LOWER(?) AND res_date"
       " = ?",
       (name.strip(), res_date),
   )
   if cursor.fetchone():
     errors.append(f"{res_date} tarihinde zaten başka bir kaydınız bulunmaktadır.")
     continue
   cursor.execute(
       "SELECT capacity FROM custom_capacities WHERE location = ? AND"
       " res_date = ?",
       (loc, res_date),
   )
   custom_row = cursor.fetchone()
   max_capacity = custom_row[0] if custom_row else DEFAULT_CAPACITIES[loc]
   cursor.execute(
       "SELECT COUNT(*) FROM reservations WHERE location = ? AND res_date = ?",
       (loc, res_date),
   )
   current_count = cursor.fetchone()[0]
   if current_count >= max_capacity:
     errors.append(f"{loc} - {res_date} tarihi için kontenjan dolmuştur.")
     continue
   valid_items.append(item)
 if errors and not valid_items:
   conn.close()
   return JSONResponse(
       status_code=400, content={"message": " <br>".join(errors)}
   )
 pnr_code = generate_pnr(sicil)
 for item in valid_items:
   cursor.execute(
       "INSERT INTO reservations (pnr, sicil, name, baskanlik, mudurluk,"
       " location, res_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
       (
           pnr_code,
           sicil.strip(),
           name.strip(),
           baskanlik,
           mudurluk,
           item["location"],
           item["date"],
       ),
   )
 conn.commit()
 conn.close()
 msg = f"{len(valid_items)} adet gün için rezervasyonunuz başarıyla oluşturuldu."
 if errors:
   msg += f"<br><small class='text-amber-700'>Uyarı: {', '.join(errors)}</small>"
 return JSONResponse(content={"message": msg, "pnr": pnr_code})

@app.post("/api/lookup-reservation")
async def lookup_reservation(pnr: str = Form(...), sicil: str = Form(...)):
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute(
     "SELECT id, location, res_date FROM reservations WHERE pnr = ? AND sicil"
     " = ?",
     (pnr.strip().upper(), sicil.strip()),
 )
 rows = cursor.fetchall()
 conn.close()
 if not rows:
   return JSONResponse(
       status_code=400,
       content={
           "message": (
               "Girilen PNR kodu ve sicil numarası ile eşleşen aktif bir"
               " rezervasyon bulunamadı."
           )
       },
   )
 reservations = [
     {"id": r[0], "location": r[1], "res_date": r[2]} for r in rows
 ]
 return JSONResponse(content=reservations)

@app.post("/api/cancel-single-reservation")
async def cancel_single_reservation(id: int = Form(...)):
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute("DELETE FROM reservations WHERE id = ?", (id,))
 conn.commit()
 conn.close()
 return JSONResponse(
     content={"message": "Seçilen gün rezervasyonu başarıyla iptal edildi."}
 )

@app.post("/api/change-reservation-day")
async def change_reservation_day(
   old_id: int = Form(...),
   new_location: str = Form(...),
   new_date: str = Form(...),
   pnr: str = Form(...),
   sicil: str = Form(...),
):
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute(
     "SELECT location, res_date FROM reservations WHERE pnr = ? AND sicil = ?"
     " AND id != ?",
     (pnr.strip().upper(), sicil.strip(), old_id),
 )
 existing_res = cursor.fetchall()
 all_dates_for_check = [r[1] for r in existing_res] + [new_date]
 for week_name, days in SEPTEMBER_2026_WEEKS.items():
   count_in_week = sum(1 for d in all_dates_for_check if d in days)
   if count_in_week > 2:
     conn.close()
     return JSONResponse(
         status_code=400,
         content={
             "message": (
                 f"{week_name} içerisinde en fazla 2 gün seçebilirsiniz! Bu"
                 " işlem kuralı ihlal ediyor."
             )
         },
     )
 cursor.execute(
     "SELECT capacity FROM custom_capacities WHERE location = ? AND res_date ="
     " ?",
     (new_location, new_date),
 )
 custom_row = cursor.fetchone()
 max_capacity = custom_row[0] if custom_row else DEFAULT_CAPACITIES[new_location]
 cursor.execute(
     "SELECT COUNT(*) FROM reservations WHERE location = ? AND res_date = ?",
     (new_location, new_date),
 )
 current_count = cursor.fetchone()[0]
 if current_count >= max_capacity:
   conn.close()
   return JSONResponse(
       status_code=400,
       content={
           "message": f"Seçtiğiniz {new_location} - {new_date} tarihi için kontenjan dolmuştur!"
       },
   )
 cursor.execute(
     "SELECT id FROM reservations WHERE sicil = ? AND res_date = ?",
     (sicil.strip(), new_date),
 )
 if cursor.fetchone():
   conn.close()
   return JSONResponse(
       status_code=400,
       content={
           "message": (
               f"Bu tarihe ({new_date}) ait zaten aktif başka bir kaydınız"
               " bulunmaktadır."
           )
       },
   )
 cursor.execute(
     "SELECT name, baskanlik, mudurluk FROM reservations WHERE id = ?",
     (old_id,),
 )
 user_info = cursor.fetchone()
 if not user_info:
   conn.close()
   return JSONResponse(
       status_code=400, content={"message": "Eski rezervasyon kaydı bulunamadı."}
   )
 name, baskanlik, mudurluk = user_info
 cursor.execute("DELETE FROM reservations WHERE id = ?", (old_id,))
 cursor.execute(
     "INSERT INTO reservations (pnr, sicil, name, baskanlik, mudurluk,"
     " location, res_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
     (
         pnr.strip().upper(),
         sicil.strip(),
         name,
         baskanlik,
         mudurluk,
         new_location,
         new_date,
     ),
 )
 conn.commit()
 conn.close()
 return JSONResponse(
     content={"message": "Rezervasyon gününüz ve ofisiniz başarıyla güncellendi."}
 )

# ----------------- ADMIN API ENDPOINTS -----------------
@app.post("/api/admin/login")
async def admin_login(password: str = Form(...)):
 if password == ADMIN_PASSWORD:
   return JSONResponse(content={"success": True})
 return JSONResponse(
     status_code=401, content={"message": "Hatalı yönetici parolası!"}
 )

@app.get("/api/admin/reservations")
async def get_all_reservations(password: str):
 if password != ADMIN_PASSWORD:
   return JSONResponse(
       status_code=401, content={"message": "Yetkisiz erişim!"}
   )
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute(
     "SELECT id, pnr, sicil, name, baskanlik, mudurluk, location, res_date,"
     " created_at FROM reservations ORDER BY res_date DESC, id DESC"
 )
 rows = cursor.fetchall()
 conn.close()
 reservations = [
     {
         "id": r[0],
         "pnr": r[1],
         "sicil": r[2],
         "name": r[3],
         "baskanlik": r[4],
         "mudurluk": r[5],
         "location": r[6],
         "res_date": r[7],
         "created_at": r[8],
     }
     for r in rows
 ]
 return JSONResponse(content=reservations)

@app.post("/api/admin/delete-reservation")
async def delete_reservation(id: int = Form(...), password: str = Form(...)):
 if password != ADMIN_PASSWORD:
   return JSONResponse(
       status_code=401, content={"message": "Yetkisiz erişim!"}
   )
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
   password: str = Form(...),
):
 if password != ADMIN_PASSWORD:
   return JSONResponse(
       status_code=401, content={"message": "Yetkisiz erişim!"}
   )
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute(
     """
      INSERT INTO custom_capacities (location, res_date, capacity)
      VALUES (?, ?, ?)
      ON CONFLICT(location, res_date) DO UPDATE SET capacity = excluded.capacity
  """,
     (location, res_date, capacity),
 )
 conn.commit()
 conn.close()
 return JSONResponse(
     content={
         "message": (
             f"{location} - {res_date} için kontenjan {capacity} olarak"
             " güncellendi."
         )
     }
 )

@app.get("/api/admin/export-excel")
async def export_excel(password: str):
 if password != ADMIN_PASSWORD:
   return JSONResponse(
       status_code=401, content={"message": "Yetkisiz erişim!"}
   )
 conn = get_db()
 cursor = conn.cursor()
 cursor.execute(
     "SELECT id, pnr, sicil, name, baskanlik, mudurluk, location, res_date,"
     " created_at FROM reservations ORDER BY res_date DESC"
 )
 rows = cursor.fetchall()
 conn.close()
 output = io.StringIO()
 writer = csv.writer(output, delimiter=";")
 writer.writerow([
     "ID",
     "PNR Kodu",
     "Sicil",
     "Ad Soyad",
     "Başkanlık",
     "Müdürlük",
     "Lokasyon",
     "Rezervasyon Tarihi",
     "Kayıt Tarihi",
 ])
 for row in rows:
   writer.writerow(row)
 response = Response(
     content=output.getvalue().encode("utf-8-sig"), media_type="text/csv"
 )
 response.headers["Content-Disposition"] = (
     "attachment; filename=Eylul_2026_Uydu_Ofis_Rezervasyonlari.csv"
 )
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
<div class="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
<div class="flex items-center space-x-3">
<i class="fa-solid fa-plane-departure text-red-500 text-2xl"></i>
<div>
<h1 class="text-xl font-bold tracking-wide">Uydu Ofis Rezervasyon Portalı</h1>
<p class="text-xs text-slate-400">Turkish Cargo - Eylül 2026 Çalışma Takvimi</p>
</div>
</div>
<button onclick="toggleAdminModal()" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 px-3 py-1.5 rounded-lg transition flex items-center space-x-1">
<i class="fa-solid fa-user-shield text-red-400"></i>
<span>Admin Paneli</span>
</button>
</div>
</header>
<!-- Main Content -->
<main class="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
<!-- Sol Panel: Kişisel Bilgiler ve Sekmeler -->
<section class="lg:col-span-1 bg-white rounded-xl shadow-md p-6 border border-slate-200 h-fit space-y-4">
<div class="flex border-b mb-4 text-sm font-semibold">
<button onclick="switchTab('create')" id="tabCreateBtn" class="pb-2 px-3 text-red-600 border-b-2 border-red-600 flex items-center space-x-1.5 transition">
<i class="fa-regular fa-calendar-check"></i> <span>Rezervasyon Yap</span>
</button>
<button onclick="switchTab('cancel')" id="tabCancelBtn" class="pb-2 px-3 text-slate-500 hover:text-slate-800 flex items-center space-x-1.5 transition">
<i class="fa-solid fa-right-left"></i> <span>Gün Değiştir / İptal Et</span>
</button>
</div>
<!-- Rezervasyon Formu -->
<div id="tabCreateContent">
<form id="resForm" onsubmit="handleReserve(event)" class="space-y-4">
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Sicil No</label>
<input type="text" id="sicil" required placeholder="Örn: 123456"
                         class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm">
</div>
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
<div class="flex items-start space-x-2 pt-2">
<input type="checkbox" id="rulesCheck" required class="mt-0.5 rounded text-red-600 focus:ring-red-500">
<label for="rulesCheck" class="text-xs text-slate-600 leading-tight">
                        Haftalık toplamda en fazla 2 gün seçim kuralını ve çalışma esaslarını onaylıyorum.
</label>
</div>
<button type="submit" id="submitBtn"
                     class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg transition duration-150 flex items-center justify-center space-x-2 text-sm shadow cursor-pointer">
<i class="fa-solid fa-check"></i>
<span>Seçilen Günleri Rezerve Et</span>
</button>
</form>
<div id="alertBox" class="mt-4 hidden p-3 rounded-lg text-xs font-medium"></div>
</div>
<!-- Gün Değiştirme / İptal Formu -->
<div id="tabCancelContent" class="hidden space-y-4">
<form id="cancelForm" onsubmit="handleLookup(event)" class="space-y-3">
<p class="text-xs text-slate-500">Rezervasyonunuzu değiştirmek veya iptal etmek için PNR kodunuzu ve sicilinizi girip sorgulayınız.</p>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">PNR Kodu</label>
<input type="text" id="cancel_pnr" required placeholder="Örn: TK-123456-ABCD"
                         class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm uppercase">
</div>
<div>
<label class="block text-xs font-bold text-slate-600 uppercase mb-1">Sicil No</label>
<input type="text" id="cancel_sicil" required placeholder="Örn: 123456"
                         class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm">
</div>
<button type="submit"
                     class="w-full bg-slate-800 hover:bg-slate-900 text-white font-medium py-2.5 px-4 rounded-lg transition duration-150 flex items-center justify-center space-x-2 text-sm shadow cursor-pointer">
<i class="fa-solid fa-search"></i>
<span>Rezervasyonları Sorgula</span>
</button>
</form>
<div id="cancelAlertBox" class="mt-2 hidden p-3 rounded-lg text-xs font-medium"></div>
<!-- Sorgulanan Günler Listesi ve Yönetim Butonları -->
<div id="lookupResultContainer" class="hidden space-y-2 pt-2 border-t">
<h4 class="text-xs font-bold text-slate-700 uppercase">Mevcut Rezervasyon Günleriniz:</h4>
<div id="reservationDaysList" class="space-y-2 max-h-48 overflow-y-auto"></div>
</div>
<!-- Yeni Ofis ve Tarih Seçim Alanı (Gün Değiştirme Modu İçin) -->
<div id="changeDateContainer" class="hidden space-y-2 pt-3 border-t bg-amber-50/60 p-3 rounded-lg border border-amber-200">
<p class="text-xs font-bold text-amber-900" id="changeTitle"></p>
<div class="space-y-2">
<div>
<label class="block text-[11px] font-semibold text-slate-700">Yeni Ofis Seçin:</label>
<select id="newLocSelect" onchange="updateChangeDateOptions()" class="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white">
<option value="Atatürk Havalimanı">Atatürk Havalimanı</option>
<option value="Libadiye Teknoloji Ofisi">Libadiye Teknoloji Ofisi</option>
</select>
</div>
<div>
<label class="block text-[11px] font-semibold text-slate-700">Yeni Tarih Seçin:</label>
<select id="newDateSelect" class="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white"></select>
</div>
</div>
<div class="flex space-x-2 pt-1">
<button onclick="confirmDateChange()" class="flex-1 bg-red-600 hover:bg-red-700 text-white text-xs font-medium py-1.5 rounded transition">Değişikliği Onayla</button>
<button onclick="cancelDateChangeMode()" class="bg-slate-300 hover:bg-slate-400 text-slate-800 text-xs py-1.5 px-3 rounded transition">İptal</button>
</div>
</div>
</div>
<div class="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-600 space-y-1">
<p class="font-bold text-slate-700"><i class="fa-solid fa-circle-info text-blue-500"></i> Kurallar:</p>
<p>• Her çalışma haftasından <b>en fazla 2 gün</b> seçebilirsiniz.</p>
<p>• Dilediğiniz günü değiştirebilir veya tamamen iptal edebilirsiniz.</p>
</div>
</section>
<!-- Sağ Panel: Eylül 2026 Her İki Ofis Açık Takvim -->
<section class="lg:col-span-2 space-y-4">
<div class="bg-white rounded-xl shadow-md p-6 border border-slate-200">
<h3 class="text-base font-semibold text-slate-900 border-b pb-3 mb-4 flex justify-between items-center">
<span><i class="fa-regular fa-calendar-days text-red-600 mr-2"></i> Eylül 2026 Ofis ve Gün Seçimi</span>
<span id="selectedCountBadge" class="text-xs bg-red-50 text-red-700 px-2.5 py-1 rounded-full font-bold border border-red-200">0 Gün Seçildi</span>
</h3>
<!-- Haftalık Kartlar -->
<div id="weeksContainer" class="space-y-4">
<!-- JS Dynamic Weeks -->
</div>
</div>
</section>
</main>
<!-- ADMIN MODAL -->
<div id="adminModal" class="fixed inset-0 bg-black/60 hidden backdrop-blur-sm flex items-center justify-center p-4 z-50">
<div class="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-300">
<div class="bg-slate-900 text-white px-6 py-4 flex justify-between items-center border-b border-slate-700">
<div class="flex items-center space-x-2">
<i class="fa-solid fa-user-shield text-red-500"></i>
<h3 class="font-bold text-base">Yönetici Kontrol Paneli</h3>
</div>
<button onclick="toggleAdminModal()" class="text-slate-400 hover:text-white text-lg"><i class="fa-solid fa-xmark"></i></button>
</div>
<div class="p-6 overflow-y-auto space-y-6">
<div id="adminLoginForm" class="max-w-sm mx-auto my-8 space-y-4 text-center">
<i class="fa-solid fa-lock text-slate-400 text-4xl mb-2"></i>
<h4 class="font-bold text-slate-800">Admin Girişi Yapın</h4>
<input type="password" id="adminPass" placeholder="Yönetici Parolası" class="w-full px-3 py-2 border rounded-lg text-sm text-center focus:ring-2 focus:ring-red-500 outline-none">
<button onclick="loginAdmin()" class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 rounded-lg text-sm transition">Giriş Yap</button>
<p id="adminLoginErr" class="text-xs text-rose-600 hidden"></p>
</div>
<div id="adminContent" class="hidden space-y-6">
<div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
<h4 class="text-xs font-bold text-slate-700 uppercase mb-3 flex items-center">
<i class="fa-solid fa-sliders text-red-600 mr-2"></i> Kontenjan Güncelle
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
<div>
<div class="flex justify-between items-center mb-3">
<h4 class="text-xs font-bold text-slate-700 uppercase flex items-center">
<i class="fa-solid fa-list-check text-slate-600 mr-2"></i> Rezervasyon Listesi
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
<th class="p-2.5">PNR Kodu</th>
<th class="p-2.5">Sicil</th>
<th class="p-2.5">Ad Soyad</th>
<th class="p-2.5">Başkanlık</th>
<th class="p-2.5">Müdürlük</th>
<th class="p-2.5">Lokasyon</th>
<th class="p-2.5">Tarih</th>
<th class="p-2.5 text-center">İşlem</th>
</tr>
</thead>
<tbody id="resTableBody" class="divide-y text-slate-600"></tbody>
</table>
</div>
</div>
</div>
</div>
</div>
</div>
<script>
         let currentAdminPass = "";
         let selectedSelections = new Set();
         let globalAvailability = {};
         let activeLookupData = [];
         let selectedOldIdForChange = null;
         const weeksData = {
             "1. Hafta (1 - 4 Eylül)": ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"],
             "2. Hafta (7 - 11 Eylül)": ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"],
             "3. Hafta (14 - 18 Eylül)": ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"],
             "4. Hafta (21 - 25 Eylül)": ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"],
             "5. Hafta (28 - 30 Eylül)": ["2026-09-28", "2026-09-29", "2026-09-30"]
         };
         const mudurlukData = {
             "Kargo Operasyon Başkanlığı": ["Kargo Handling Anlaşmaları Müdürlüğü", "Kargo Operasyonel Performans Müdürlüğü", "Kargo Uçuş Operasyon Kontrol Müdürlüğü", "Kargo Güvenlik Müdürlüğü", "Özel Kargo ve Operasyonel Hizmetler Müdürlüğü"],
             "Kargo Satış Başkanlığı": ["Kargo Kurumsal Müşteriler Müdürlüğü", "Kargo Dijital Satış Müdürlüğü", "Kargo Bölge Müdürlüğü (İstanbul)", "Kargo Bölge Müdürlüğü (Anadolu)"],
             "Kargo Pazarlama Başkanlığı": ["Kargo Ürün Geliştirme Müdürlüğü", "Kargo Pazarlama İletişimi Müdürlüğü"],
             "Kargo Gelir Yönetimi ve Ürün Planlama Başkanlığı": ["Kargo Fiyatlandırma Müdürlüğü", "Kargo Kapasite Planlama Müdürlüğü"],
             "Genel Müdür (Kargo) Yardımcılığı": ["Kargo Organizasyonel Gelişim Müdürlüğü", "Kargo İnsan Kaynakları Müdürlüğü"]
         };
         function switchTab(tab) {
             const createBtn = document.getElementById("tabCreateBtn");
             const cancelBtn = document.getElementById("tabCancelBtn");
             const createContent = document.getElementById("tabCreateContent");
             const cancelContent = document.getElementById("tabCancelContent");
             if (tab === 'create') {
                 createBtn.className = "pb-2 px-3 text-red-600 border-b-2 border-red-600 flex items-center space-x-1.5 transition font-semibold";
                 cancelBtn.className = "pb-2 px-3 text-slate-500 hover:text-slate-800 flex items-center space-x-1.5 transition";
                 createContent.classList.remove("hidden");
                 cancelContent.classList.add("hidden");
             } else {
                 cancelBtn.className = "pb-2 px-3 text-red-600 border-b-2 border-red-600 flex items-center space-x-1.5 transition font-semibold";
                 createBtn.className = "pb-2 px-3 text-slate-500 hover:text-slate-800 flex items-center space-x-1.5 transition";
                 cancelContent.classList.remove("hidden");
                 createContent.classList.add("hidden");
             }
         }
         function updateMudurlukOptions() {
             const b = document.getElementById("baskanlik").value;
             const m = document.getElementById("mudurluk");
             m.innerHTML = '<option value="">Müdürlük Seçiniz</option>';
             if (b && mudurlukData[b]) {
                 mudurlukData[b].forEach(item => {
                     const opt = document.createElement("option");
                     opt.value = item;
                     opt.innerText = item;
                     m.appendChild(opt);
                 });
             }
         }
         async function loadAllAvailability() {
             try {
                 const res = await fetch("/api/all-availability");
                 globalAvailability = await res.json();
                 renderWeeks();
             } catch (e) {
                 console.error("Kontenjanlar yüklenemedi", e);
             }
         }
         function renderWeeks() {
             const container = document.getElementById("weeksContainer");
             container.innerHTML = "";
             const dayNames = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"];
             for (const [weekTitle, dates] of Object.entries(weeksData)) {
                 const weekBox = document.createElement("div");
                 weekBox.className = "border border-slate-200 rounded-xl p-4 bg-slate-50/50 space-y-3";
                 let daysHtml = "";
                 dates.forEach((dStr, idx) => {
                     const dateObj = new Date(dStr);
                     const formattedDate = `${dateObj.getDate()} Eylül (${dayNames[idx] || 'İş Günü'})`;
                     const atkInfo = globalAvailability["Atatürk Havalimanı"]?.[dStr] || { remaining: 20 };
                     const atkKey = `Atatürk Havalimanı|${dStr}`;
                     const atkFull = atkInfo.remaining <= 0;
                     const atkChecked = selectedSelections.has(atkKey);
                     const libInfo = globalAvailability["Libadiye Teknoloji Ofisi"]?.[dStr] || { remaining: 30 };
                     const libKey = `Libadiye Teknoloji Ofisi|${dStr}`;
                     const libFull = libInfo.remaining <= 0;
                     const libChecked = selectedSelections.has(libKey);
                     daysHtml += `
<div class="bg-white p-3 rounded-lg border border-slate-200 space-y-2">
<div class="text-xs font-bold text-slate-800 border-b pb-1.5 flex items-center justify-between">
<span><i class="fa-regular fa-calendar text-red-500 mr-1"></i> ${formattedDate}</span>
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
<label class="flex items-center justify-between p-2 rounded border transition ${
                         atkFull ? 'bg-slate-100 border-slate-200 opacity-60 cursor-not-allowed' :
                         atkChecked ? 'bg-red-50 border-red-400 font-semibold' : 'bg-slate-50/70 border-slate-200 hover:border-slate-300 cursor-pointer'
                     }">
<div class="flex items-center space-x-2">
<input type="checkbox" value="${atkKey}" data-week="${weekTitle}" ${atkChecked ? 'checked' : ''} ${atkFull ? 'disabled' : ''}
                                    onchange="toggleSelection(this)" class="rounded text-red-600 focus:ring-red-500 h-3.5 w-3.5">
<span class="text-[11px] text-slate-800 font-medium">Atatürk Havalimanı</span>
</div>
<span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${atkFull ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-800'}">
                                 ${atkFull ? 'Doldu' : atkInfo.remaining + ' Boş'}
</span>
</label>
<label class="flex items-center justify-between p-2 rounded border transition ${
                         libFull ? 'bg-slate-100 border-slate-200 opacity-60 cursor-not-allowed' :
                         libChecked ? 'bg-red-50 border-red-400 font-semibold' : 'bg-slate-50/70 border-slate-200 hover:border-slate-300 cursor-pointer'
                     }">
<div class="flex items-center space-x-2">
<input type="checkbox" value="${libKey}" data-week="${weekTitle}" ${libChecked ? 'checked' : ''} ${libFull ? 'disabled' : ''}
                                    onchange="toggleSelection(this)" class="rounded text-red-600 focus:ring-red-500 h-3.5 w-3.5">
<span class="text-[11px] text-slate-800 font-medium">Libadiye Ofisi</span>
</div>
<span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${libFull ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-800'}">
                                 ${libFull ? 'Doldu' : libInfo.remaining + ' Boş'}
</span>
</label>
</div>
</div>
                     `;
                 });
                 weekBox.innerHTML = `
<div class="flex justify-between items-center border-b pb-2">
<h4 class="text-xs font-bold text-slate-800 uppercase flex items-center">
<i class="fa-regular fa-calendar-check text-red-600 mr-2"></i> ${weekTitle}
</h4>
<span class="text-[11px] text-slate-500 font-medium">Haftalık Toplam Max 2 Gün</span>
</div>
<div class="space-y-2">
                         ${daysHtml}
</div>
                 `;
                 container.appendChild(weekBox);
             }
         }
         function toggleSelection(checkbox) {
             const val = checkbox.value;
             const weekTitle = checkbox.getAttribute("data-week");
             if (checkbox.checked) {
                 const checkboxesInWeek = document.querySelectorAll(`input[data-week="${weekTitle}"]:checked`);
                 if (checkboxesInWeek.length > 2) {
                     alert(`${weekTitle} içerisinden toplamda en fazla 2 gün seçebilirsiniz!`);
                     checkbox.checked = false;
                     return;
                 }
                 selectedSelections.add(val);
             } else {
                 selectedSelections.delete(val);
             }
             document.getElementById("selectedCountBadge").innerText = `${selectedSelections.size} Gün Seçildi`;
             loadAllAvailability();
         }
         async function handleReserve(event) {
             event.preventDefault();
             const alertBox = document.getElementById("alertBox");
             alertBox.className = "mt-4 hidden p-3 rounded-lg text-xs font-medium";
             if (selectedSelections.size === 0) {
                 alertBox.innerText = "Lütfen takvimden en az bir ofis ve gün seçiniz.";
                 alertBox.classList.remove("hidden");
                 alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
                 return;
             }
             const selectionsArray = Array.from(selectedSelections).map(item => {
                 const parts = item.split("|");
                 return { location: parts[0], date: parts[1] };
             });
             const formData = new FormData();
             formData.append("sicil", document.getElementById("sicil").value);
             formData.append("name", document.getElementById("name").value);
             formData.append("baskanlik", document.getElementById("baskanlik").value);
             formData.append("mudurluk", document.getElementById("mudurluk").value);
             formData.append("selections_json", JSON.stringify(selectionsArray));
             try {
                 const response = await fetch("/api/reserve", {
                     method: "POST",
                     body: formData
                 });
                 const result = await response.json();
                 if (response.ok) {
                     alertBox.innerHTML = `${result.message}<br><br>🔑 <b>Atanan PNR Kodunuz:</b> <span class="bg-white px-2 py-1 rounded border font-mono text-red-600 font-bold select-all">${result.pnr}</span><br><span class='text-[11px] text-emerald-700 mt-1 block'>* Bu kodu ve sicilinizi kullanarak istediğiniz zaman rezervasyonunuzu yönetebilir/değiştirebilirsiniz.</span>`;
                     alertBox.classList.remove("hidden");
                     alertBox.classList.add("bg-emerald-100", "text-emerald-800", "border", "border-emerald-300");
                     selectedSelections.clear();
                     document.getElementById("selectedCountBadge").innerText = "0 Gün Seçildi";
                     document.getElementById("resForm").reset();
                     loadAllAvailability();
                 } else {
                     alertBox.innerHTML = result.message || "Bir hata oluştu.";
                     alertBox.classList.remove("hidden");
                     alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
                 }
             } catch (e) {
                 alertBox.innerText = "Bağlantı hatası oluştu.";
                 alertBox.classList.remove("hidden");
                 alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
             }
         }
         async function handleLookup(event) {
             event.preventDefault();
             const alertBox = document.getElementById("cancelAlertBox");
             const container = document.getElementById("lookupResultContainer");
             const listDiv = document.getElementById("reservationDaysList");
             alertBox.className = "mt-2 hidden p-3 rounded-lg text-xs font-medium";
             container.classList.add("hidden");
             listDiv.innerHTML = "";
             cancelDateChangeMode();
             const formData = new FormData();
             formData.append("pnr", document.getElementById("cancel_pnr").value);
             formData.append("sicil", document.getElementById("cancel_sicil").value);
             try {
                 const response = await fetch("/api/lookup-reservation", {
                     method: "POST",
                     body: formData
                 });
                 const data = await response.json();
                 if (response.ok) {
                     activeLookupData = data;
                     container.classList.remove("hidden");
                     data.forEach(item => {
                         const row = document.createElement("div");
                         row.className = "flex items-center justify-between p-2 bg-slate-50 border rounded text-xs";
                         row.innerHTML = `
<div>
<span class="font-bold text-slate-800">${item.res_date}</span>
<span class="text-slate-500 block text-[10px]">${item.location}</span>
</div>
<div class="flex space-x-1.5">
<button type="button" onclick="initChange(${item.id}, '${item.res_date}', '${item.location}')" class="bg-amber-600 hover:bg-amber-700 text-white px-2 py-1 rounded transition text-[11px]">
                                     Değiştir
</button>
<button type="button" onclick="cancelSingle(${item.id})" class="bg-rose-600 hover:bg-rose-700 text-white px-2 py-1 rounded transition text-[11px]">
                                     İptal Et
</button>
</div>
                         `;
                         listDiv.appendChild(row);
                     });
                 } else {
                     alertBox.innerHTML = data.message || "Kayıt bulunamadı.";
                     alertBox.classList.remove("hidden");
                     alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
                 }
             } catch (e) {
                 alertBox.innerText = "Bağlantı hatası oluştu.";
                 alertBox.classList.remove("hidden");
                 alertBox.classList.add("bg-rose-100", "text-rose-800", "border", "border-rose-300");
             }
         }
         async function cancelSingle(id) {
             if (!confirm("Seçilen günün rezervasyonunu tamamen iptal etmek istediğinize emin misiniz?")) return;
             const formData = new FormData();
             formData.append("id", id);
             try {
                 const res = await fetch("/api/cancel-single-reservation", {
                     method: "POST",
                     body: formData
                 });
                 if (res.ok) {
                     alert("Rezervasyon başarıyla iptal edildi.");
                     cancelDateChangeMode();
                     document.getElementById("cancelForm").requestSubmit();
                     loadAllAvailability();
                 } else {
                     alert("İptal sırasında bir hata oluştu.");
                 }
             } catch (e) {
                 alert("Bağlantı hatası oluştu.");
             }
         }
         function initChange(id, currentDate, currentLoc) {
             selectedOldIdForChange = id;
             document.getElementById("changeTitle").innerText = `${currentLoc} - ${currentDate} için yeni ofis ve tarih seçin:`;
             document.getElementById("newLocSelect").value = currentLoc;
             document.getElementById("changeDateContainer").classList.remove("hidden");
             updateChangeDateOptions();
         }
         function updateChangeDateOptions() {
             const selectedLoc = document.getElementById("newLocSelect").value;
             const selectEl = document.getElementById("newDateSelect");
             selectEl.innerHTML = '<option value="">Tarih Seçiniz</option>';
             const locData = globalAvailability[selectedLoc] || {};
             const otherDates = activeLookupData.filter(item => item.id !== selectedOldIdForChange).map(item => item.res_date);
             for (const [dateStr, info] of Object.entries(locData)) {
                 if (info.remaining <= 0 || otherDates.includes(dateStr)) continue;
                 let weekKey = null;
                 for (const [wTitle, wDays] of Object.entries(weeksData)) {
                     if (wDays.includes(dateStr)) { weekKey = wTitle; break; }
                 }
                 if (weekKey) {
                     const daysInThisWeek = weeksData[weekKey];
                     const countInWeek = otherDates.filter(d => daysInThisWeek.includes(d)).length;
                     if (countInWeek >= 2) continue;
                 }
                 const opt = document.createElement("option");
                 opt.value = dateStr;
                 opt.innerText = `${dateStr} (${selectedLoc} - Boş: ${info.remaining})`;
                 selectEl.appendChild(opt);
             }
         }
         function cancelDateChangeMode() {
             selectedOldIdForChange = null;
             document.getElementById("changeDateContainer").classList.add("hidden");
         }
         async function confirmDateChange() {
             const newLoc = document.getElementById("newLocSelect").value;
             const newDate = document.getElementById("newDateSelect").value;
             if (!newDate) {
                 alert("Lütfen geçerli yeni bir tarih seçiniz.");
                 return;
             }
             const formData = new FormData();
             formData.append("old_id", selectedOldIdForChange);
             formData.append("new_location", newLoc);
             formData.append("new_date", newDate);
             formData.append("pnr", document.getElementById("cancel_pnr").value);
             formData.append("sicil", document.getElementById("cancel_sicil").value);
             try {
                 const res = await fetch("/api/change-reservation-day", {
                     method: "POST",
                     body: formData
                 });
                 const result = await res.json();
                 if (res.ok) {
                     alert(result.message);
                     cancelDateChangeMode();
                     document.getElementById("cancelForm").requestSubmit();
                     loadAllAvailability();
                 } else {
                     alert(result.message || "Güncelleme sırasında bir hata oluştu.");
                 }
             } catch (e) {
                 alert("Bağlantı hatası oluştu.");
             }
         }
         function toggleAdminModal() {
             document.getElementById("adminModal").classList.toggle("hidden");
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
<td class="p-2.5 font-bold text-red-600">${r.pnr}</td>
<td class="p-2.5 font-medium text-slate-800">${r.sicil}</td>
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
             loadAllAvailability();
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
                 loadAllAvailability();
             }
         }
         function downloadExcel() {
             window.location.href = `/api/admin/export-excel?password=${currentAdminPass}`;
         }
         window.onload = loadAllAvailability;
</script>
</body>
</html>
  """
 return HTMLResponse(content=html_content)
