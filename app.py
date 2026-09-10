from datetime import datetime, timedelta
import csv
import io
import json
import os
import random
import string
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
import openpyxl
import sqlite3
import uvicorn

app = FastAPI(title="Uydu Ofis Rezervasyon Portalı")

PERSISTENT_DIR = (
    "/data" if os.path.exists("/data") else os.path.expanduser("~")
)
DB_FILE = os.path.join(PERSISTENT_DIR, "reservations_production.db")

ADMIN_PASSWORD = "kogm2071"
DEFAULT_CAPACITIES = {
    "Atatürk Havalimanı": 20,
    "Libadiye Teknoloji Ofisi": 30,
}

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
  return f"TK-{str(sicil).strip().upper()}-{random_suffix}"


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


@app.get("/api/all-availability")
async def get_all_availability():
  conn = get_db()
  cursor = conn.cursor()

  cursor.execute("SELECT location, res_date, capacity FROM custom_capacities")
  custom_caps = {}
  for loc, d, cap in cursor.fetchall():
    custom_caps[(loc, d)] = cap

  cursor.execute(
      "SELECT location, res_date, COUNT(*) FROM reservations GROUP BY location,"
      " res_date"
  )
  booked_counts = {}
  for loc, d, cnt in cursor.fetchall():
    booked_counts[(loc.strip().lower(), d.strip())] = cnt

  conn.close()

  result = {}
  locations = ["Atatürk Havalimanı", "Libadiye Teknoloji Ofisi"]

  for loc in locations:
    result[loc] = {}
    default_cap = DEFAULT_CAPACITIES.get(loc, 20)
    for week_name, days in SEPTEMBER_2026_WEEKS.items():
      for d in days:
        cap = custom_caps.get((loc, d), default_cap)
        booked = booked_counts.get((loc.lower(), d), 0)
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


@app.post("/api/admin/import-excel")
async def import_excel(password: str = Form(...), file: UploadFile = File(...)):
  if password != ADMIN_PASSWORD:
    return JSONResponse(
        status_code=401, content={"message": "Yetkisiz erişim!"}
    )

  try:
    contents = await file.read()
    wb = openpyxl.load_workbook(filename=io.BytesIO(contents), data_only=True)
    sheet = wb.active

    conn = get_db()
    cursor = conn.cursor()
    imported_count = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
      try:
        if not row or all(cell is None for cell in row):
          continue

        cell_texts = [str(c) for c in row if c is not None]
        full_row_text = " ".join(cell_texts)
        if not full_row_text.strip():
          continue

        sicil = f"99{random.randint(1000,9999)}"
        name = "Personel"
        baskanlik = "Kargo Operasyon Başkanlığı"
        mudurluk = "KARGO OPERASYONEL PERFORMANS MD."

        for c_str in cell_texts:
          val_str = c_str.strip()
          if val_str.isdigit() and 4 <= len(val_str) <= 8:
            sicil = val_str
          elif (
              len(val_str) > 3
              and "@" not in val_str
              and "(" not in val_str
              and "Hafta" not in val_str
              and "|" not in val_str
          ):
            if not any(char.isdigit() for char in val_str):
              name = val_str

        pnr = generate_pnr(sicil)

        segments = full_row_text.split("|")
        for seg in segments:
          seg = seg.strip()
          if not seg or "(" not in seg or ")" not in seg:
            continue

          try:
            loc_raw = seg.split("(")[1].split(")")[0].strip()
            left_part = seg.split("(")[0].strip()
            words = left_part.split()

            date_candidate = ""
            for w in words:
              if "." in w and len(w) >= 8:
                date_candidate = w
                break

            if not date_candidate:
              continue

            dt_obj = datetime.strptime(date_candidate[:10], "%d.%m.%Y")
            res_date = dt_obj.strftime("%Y-%m-%d")

            if not res_date.startswith("2026-09-"):
              continue

            loc_lower = loc_raw.lower()
            if (
                "libadiye" in loc_lower
                or "tekno" in loc_lower
                or "ofis" in loc_lower
                or "liba" in loc_lower
            ):
              location = "Libadiye Teknoloji Ofisi"
            else:
              location = "Atatürk Havalimanı"

            cursor.execute(
                "SELECT id FROM reservations WHERE sicil = ? AND res_date = ?",
                (sicil, res_date),
            )
            if cursor.fetchone():
              continue

            cursor.execute(
                "INSERT INTO reservations (pnr, sicil, name, baskanlik,"
                " mudurluk, location, res_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pnr, sicil, name, baskanlik, mudurluk, location, res_date),
            )
            imported_count += 1
          except Exception:
            continue

      except Exception:
        continue

    conn.commit()
    conn.close()
    return JSONResponse(
        content={
            "message": (
                f"Başarıyla {imported_count} adet rezervasyon günü taranıp"
                " içeri aktarıldı!"
            )
        }
    )
  except Exception as e:
    return JSONResponse(
        status_count=400,
        content={
            "message": f"Excel dosyası işlenirken hata oluştu: {str(e)[:120]}"
        },
    )


@app.get("/", response_class=HTMLResponse)
async def index():
  if os.path.exists("index.html"):
    with open("index.html", "r", encoding="utf-8") as f:
      return f.read()
  return HTMLResponse(
      content="<h3>index.html dosyası bulunamadı! Lütfen ana dizine"
      " index.html dosyasını ekleyin.</h3>",
      status_code=500,
  )


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8000))
  uvicorn.run("main:app", host="0.0.0.0", port=port)
