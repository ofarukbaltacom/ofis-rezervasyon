import io
import os
import sqlite3
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

# ==============================================================================
# SAYFA KONFİGÜRASYONU VE OTURUM CANLI TUTMA (KEEP ALIVE)
# ==============================================================================
st.set_page_config(
    page_title="Uydu Ofis Rezervasyon Portalı",
    page_icon="🏢",
    layout="wide"
)

components.html(
    """
    <script>
    function keepAlive() {
        fetch(window.location.href);
    }
    setInterval(keepAlive, 60000);
    </script>
    """,
    height=0,
    width=0,
)

ADMIN_PASSWORD = "123"
DB_FILE = "rezervasyonlar.db"

# ==============================================================================
# BAŞKANLIK VE MÜDÜRLÜK LİSTELERİ
# ==============================================================================
BASKANLIK_LISTESI = [
    "KARGO OPERASYON BŞK.",
    "KARGO GELİR YÖNETİMİ VE ÜR. PL. BŞK.",
    "KARGO SATIŞ BŞK.",
    "KARGO PAZARLAMA BŞK.",
    "GM (KARGO) YRD."
]

MUDURLUK_LISTESI = [
    "KARGO HANDLING ANLAŞMALAR MD.",
    "KARGO OPERASYONEL PERFORMANS MD.",
    "KARGO UÇUŞ OPERASYON KONTROL MD.",
    "KARGO GÜVENLİK MD.",
    "KARGO OPERASYON PLANLAMA VE PROJELER MD.",
    "KARGO HUB OPERASYONLARI MD.",
    "KARGO TESİS, TEÇHİZAT VE LOJİSTİK MD.",
    "KARGO HUB OPERASYONLARI NÖBETÇİ MD. (A)",
    "KARGO HUB OPERASYONLARI NÖBETÇİ MD. (B)",
    "KARGO HUB OPERASYONLARI NÖBETÇİ MD. (C)",
    "KARGO HUB OPERASYONLARI NÖBETÇİ MD. (D)",
    "GÜMRÜK MD.",
    "KARGO APRON YÖNETİMİ MD.",
    "ÖZEL KARGO VE OPERASYONEL HİZMETLER MD.",
    "KARGO ÜCRET MD.",
    "KARGO GELİR OPTİMİZASYON MD. (1.BÖLGE)",
    "KARGO GELİR OPTİMİZASYON MD. (2.BÖLGE)",
    "KARGO GELİR YÖNETİMİ SİSTEMLERİ MD.",
    "KARGO NETWORK PLANLAMA MD.",
    "KARGO NETWORK İŞ BİRLİKLERİ MD.",
    "KARGO TARİFE MD.",
    "KARGO SATIŞ MD. (İSTANBUL)",
    "KARGO MÜŞTERİ DENEYİMİ MD.",
    "KARGO KİLİT MÜŞTERİLER MD. (AVRUPA)",
    "KARGO KİLİT MÜŞTERİLER MD. (ASYA)",
    "KARGO KİLİT MÜŞTERİLER MD. (AMERİKA)",
    "KARGO UYUMLULUK VE STANDARDİZASYON MD.",
    "KARGO TANITIM VE REKLAM MD.",
    "KARGO GLOBAL SATIŞ KANALLARI MD.",
    "SATIŞ GELİŞTİRME VE CHARTER MD.",
    "ÖZEL KARGOLAR VE SAĞLIK ÜRÜNLERİ MD.",
    "KARGO ÜRÜN VE POSTA MD.",
    "KARGO DİJİTALLEŞME VE SÜREKLİ GELİŞİM MD.",
    "KARGO STRATEJİK PLANLAMA VE İŞ ZEKASI MD.",
    "KARGO ORGANİZASYONEL GELİŞİM MD.",
    "SABİHA GÖKÇEN KARGO MD."
]

EYLUL_HAFTALARI = {
    "1. Hafta (31 Ağustos - 4 Eylül)": [
        "31.08.2026 Pazartesi", "01.09.2026 Salı", "02.09.2026 Çarşamba", "03.09.2026 Perşembe", "04.09.2026 Cuma"
    ],
    "2. Hafta (7 - 11 Eylül)": [
        "07.09.2026 Pazartesi", "08.09.2026 Salı", "09.09.2026 Çarşamba", "10.09.2026 Perşembe", "11.09.2026 Cuma"
    ],
    "3. Hafta (14 - 18 Eylül)": [
        "14.09.2026 Pazartesi", "15.09.2026 Salı", "16.09.2026 Çarşamba", "17.09.2026 Perşembe", "18.09.2026 Cuma"
    ],
    "4. Hafta (21 - 25 Eylül)": [
        "21.09.2026 Pazartesi", "22.09.2026 Salı", "23.09.2026 Çarşamba", "24.09.2026 Perşembe", "25.09.2026 Cuma"
    ],
    "5. Hafta (28 - 30 Eylül)": [
        "28.09.2026 Pazartesi", "29.09.2026 Salı", "30.09.2026 Çarşamba"
    ]
}

# ==============================================================================
# VERİTABANI İŞLEMLERİ (REZERVASYON + KONTENJAN YÖNETİMİ)
# ==============================================================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rezervasyonlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sicil TEXT,
            ad_soyad TEXT,
            baskanlik TEXT,
            mudurluk TEXT,
            unvan TEXT,
            hafta_1 TEXT,
            hafta_2 TEXT,
            hafta_3 TEXT,
            hafta_4 TEXT,
            hafta_5 TEXT,
            kayit_tarihi TEXT,
            secim_detaylari TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kontenjanlar (
            tesis_adi TEXT PRIMARY KEY,
            limit_sayisi INTEGER
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO kontenjanlar VALUES ('Atatürk Havalimanı', 30)")
    cursor.execute("INSERT OR IGNORE INTO kontenjanlar VALUES ('Libadiye Teknoloji Ofisi', 20)")
    conn.commit()
    conn.close()

init_db()

def kontenjanlari_getir():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT tesis_adi, limit_sayisi FROM kontenjanlar")
    data = dict(cursor.fetchall())
    conn.close()
    return data

def kontenjan_guncelle(tesis_adi, yeni_limit):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE kontenjanlar SET limit_sayisi = ? WHERE tesis_adi = ?", (yeni_limit, tesis_adi))
    conn.commit()
    conn.close()

def verileri_getir():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM rezervasyonlar", conn)
    conn.close()
    return df

def veri_ekle(sicil, ad_soyad, baskanlik, mudurluk, unvan, h1, h2, h3, h4, h5, kayit_tarihi, detaylar_str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rezervasyonlar 
        (sicil, ad_soyad, baskanlik, mudurluk, unvan, hafta_1, hafta_2, hafta_3, hafta_4, hafta_5, kayit_tarihi, secim_detaylari)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sicil, ad_soyad, baskanlik, mudurluk, unvan, h1, h2, h3, h4, h5, kayit_tarihi, detaylar_str))
    conn.commit()
    conn.close()

def gun_tesis_dolu_sayisi(tarih, tesis_adi):
    df = verileri_getir()
    toplam = 0
    if not df.empty and "secim_detaylari" in df.columns:
        arama_terimi = f"{tarih}@{tesis_adi}"
        for d in df["secim_detaylari"].dropna():
            if arama_terimi in d:
                toplam += 1
    return toplam

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Eylul_Rezervasyonlari')
    return output.getvalue()

if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

# --- SIDEBAR MENÜ ---
st.sidebar.title("📌 Menü")
sayfa = st.sidebar.radio(
    "Gitmek İstediğiniz Sayfayı Seçin:",
    ["📝 Eylül Ayı Rezervasyon Formu", "⚙️ Yönetim Dashboard'u"]
)

# ==============================================================================
# SAYFA 1: KULLANICI REZERVASYON PORTALI
# ==============================================================================
if sayfa == "📝 Eylül Ayı Rezervasyon Formu":
    current_limits = kontenjanlari_getir()
    st.title("🏢 Eylül 2026 Uydu Ofis Kullanım / Rezervasyon Formu")
    st.markdown("Lütfen kişisel bilgilerinizi giriniz ve Eylül ayı için haftalık **en fazla 2 gün** olacak şekilde ofis günlerinizi seçiniz.")
    st.info(f"💡 **Günlük Kontenjanlar:** Atatürk Havalimanı ({current_limits.get('Atatürk Havalimanı', 30)} Kişi) | Libadiye Teknoloji Ofisi ({current_limits.get('Libadiye Teknoloji Ofisi', 20)} Kişi)")

    with st.form("aylik_rezervasyon_formu"):
        st.subheader("👤 Kullanıcı Bilgileri")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            sicil = st.text_input("Sicil Bilgisi", placeholder="Örn: 12345")
            ad_soyad = st.text_input("İsim Soyisim", placeholder="Adınızı ve soyadınızı giriniz")
            unvan = st.text_input("Ünvan", placeholder="Göreviniz / Ünvanınız")
            
        with col_f2:
            baskanlik = st.selectbox(
                "Başkanlık / GMY",
                options=["Başkanlık Seçiniz..."] + BASKANLIK_LISTESI,
                index=0
            )
            mudurluk = st.selectbox(
                "Müdürlük",
                options=["Müdürlük Seçiniz..."] + MUDURLUK_LISTESI,
                index=0
            )
            
        st.divider()
        st.subheader("📅 Eylül 2026 Gün Seçimleri")
        
        secimler = {}
        
        for hafta_adi, gunler in EYLUL_HAFTALARI.items():
            st.markdown(f"#### 📌 **{hafta_adi}** *(En fazla 2 gün seçilebilir)*")
            
            for gun in gunler:
                c_a, c_l = st.columns(2)
                
                dolu_ataturk = gun_tesis_dolu_sayisi(gun, "Atatürk Havalimanı")
                kalan_ataturk = max(0, current_limits.get("Atatürk Havalimanı", 30) - dolu_ataturk)
                ataturk_label = f"{gun} - Atatürk Havalimanı ({kalan_ataturk} yer kaldı)" if kalan_ataturk > 0 else f"{gun} - Atatürk Havalimanı (⚠️ DOLDU)"
                
                dolu_libadiye = gun_tesis_dolu_sayisi(gun, "Libadiye Teknoloji Ofisi")
                kalan_libadiye = max(0, current_limits.get("Libadiye Teknoloji Ofisi", 20) - dolu_libadiye)
                libadiye_label = f"{gun} - Libadiye Ofisi ({kalan_libadiye} yer kaldı)" if kalan_libadiye > 0 else f"{gun} - Libadiye Ofisi (⚠️ DOLDU)"
                
                with c_a:
                    sec_ataturk = st.checkbox(ataturk_label, disabled=(kalan_ataturk <= 0), key=f"at_{gun}")
                with c_l:
                    sec_libadiye = st.checkbox(libadiye_label, disabled=(kalan_libadiye <= 0), key=f"lib_{gun}")
                
                if sec_ataturk:
                    secimler.setdefault(hafta_adi, []).append((gun, "Atatürk Havalimanı"))
                if sec_libadiye:
                    secimler.setdefault(hafta_adi, []).append((gun, "Libadiye Teknoloji Ofisi"))
                    
            st.markdown("---")

        submit_btn = st.form_submit_button("Eylül Ayı Rezervasyonunu Onayla", use_container_width=True)

    if submit_btn:
        if baskanlik == "Başkanlık Seçiniz..." or mudurluk == "Müdürlük Seçiniz...":
            st.error("⚠️ Lütfen listeden geçerli bir Başkanlık ve Müdürlük seçiniz!")
        elif not (sicil.strip() and ad_soyad.strip() and unvan.strip()):
            st.error("⚠️ Lütfen Sicil, İsim Soyisim ve Ünvan alanlarını eksiksiz doldurunuz!")
        elif not secimler:
            st.error("⚠️ Lütfen en az bir gün için tesis seçimi yapınız!")
        else:
            kural_ihlali = False
            for hafta, secilen_gunler in secimler.items():
                if len(secilen_gunler) > 2:
                    st.error(f"❌ **{hafta}** için {len(secilen_gunler)} seçim yaptınız! Lütfen her hafta için en fazla 2 gün seçiniz.")
                    kural_ihlali = True
            
            if not kural_ihlali:
                hafta_metinleri = {}
                tum_secim_detaylari = []
                
                for hafta_adi in EYLUL_HAFTALARI.keys():
                    hafta_secimleri = secimler.get(hafta_adi, [])
                    if hafta_secimleri:
                        metin_listesi = [f"{tarih} ({tesis})" for tarih, tesis in hafta_secimleri]
                        tum_secim_detaylari.extend([f"{tarih}@{tesis}" for tarih, tesis in hafta_secimleri])
                        hafta_metinleri[hafta_adi] = " | ".join(metin_listesi)
                    else:
                        hafta_metinleri[hafta_adi] = "-"
                
                kayit_tarihi = datetime.now().strftime("%Y-%m-%d %H:%M")
                detaylar_str = ";;".join(tum_secim_detaylari)
                
                h_keys = list(EYLUL_HAFTALARI.keys())
                veri_ekle(
                    sicil.strip(),
                    ad_soyad.strip(),
                    baskanlik,
                    mudurluk,
                    unvan.strip(),
                    hafta_metinleri.get(h_keys[0], "-"),
                    hafta_metinleri.get(h_keys[1], "-"),
                    hafta_metinleri.get(h_keys[2], "-"),
                    hafta_metinleri.get(h_keys[3], "-"),
                    hafta_metinleri.get(h_keys[4], "-"),
                    kayit_tarihi,
                    detaylar_str
                )
                
                st.balloons()
                st.success(f"🎉 Sayın **{ad_soyad}**, Eylül ayı rezervasyon formunuz başarıyla kaydedildi!")

# ==============================================================================
# SAYFA 2: YÖNETİM DASHBOARD'U
# ==============================================================================
elif sayfa == "⚙️ Yönetim Dashboard'u":
    st.title("⚙️ Yönetim & Kontenjan Kontrol Paneli")

    if not st.session_state.admin_logged_in:
        st.subheader("🔒 Yönetici Girişi")
        girilen_sifre = st.text_input("Lütfen Admin Parolasını Giriniz:", type="password")
        if st.button("Giriş Yap"):
            if girilen_sifre == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("Giriş Başarılı!")
                st.rerun()
            else:
                st.error("❌ Hatalı şifre!")
    else:
        if st.sidebar.button("🚪 Yönetici Çıkışı Yap"):
            st.session_state.admin_logged_in = False
            st.rerun()

        # MANUEL KONTENJAN MÜDAHALE BÖLÜMÜ
        st.subheader("🛠️ Manuel Kontenjan Limiti Düzenleme")
        limittler = kontenjanlari_getir()
        
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            yeni_ataturk = st.number_input("Atatürk Havalimanı Kontenjanı", min_value=1, value=limittler.get("Atatürk Havalimanı", 30), step=1)
        with col_k2:
            yeni_libadiye = st.number_input("Libadiye Teknoloji Ofisi Kontenjanı", min_value=1, value=limittler.get("Libadiye Teknoloji Ofisi", 20), step=1)
            
        if st.button("💾 Kontenjan Limitlerini Güncelle"):
            kontenjan_guncelle("Atatürk Havalimanı", yeni_ataturk)
            kontenjan_guncelle("Libadiye Teknoloji Ofisi", yeni_libadiye)
            st.success("✅ Kontenjan limitleri başarıyla güncellendi!")
            st.rerun()

        st.divider()
        st.subheader("📊 Günlük Kontenjan Doluluk Durumları (Eylul 2026)")
        
        limittler = kontenjanlari_getir()
        ozet_list = []
        for hafta, gunler in EYLUL_HAFTALARI.items():
            for g in gunler:
                d_ataturk = gun_tesis_dolu_sayisi(g, "Atatürk Havalimanı")
                d_libadiye = gun_tesis_dolu_sayisi(g, "Libadiye Teknoloji Ofisi")
                ozet_list.append({
                    "Hafta": hafta,
                    "Tarih": g,
                    f"Atatürk (Dolu/{limittler.get('Atatürk Havalimanı', 30)})": f"{d_ataturk} / {limittler.get('Atatürk Havalimanı', 30)}",
                    f"Libadiye (Dolu/{limittler.get('Libadiye Teknoloji Ofisi', 20)})": f"{d_libadiye} / {limittler.get('Libadiye Teknoloji Ofisi', 20)}"
                })
        
        st.dataframe(pd.DataFrame(ozet_list), use_container_width=True)
        
        st.divider()
        st.subheader("📥 Tüm Eylül Rezervasyon Verileri (Kişi Başı Tek Satır)")
        
        df_rez = verileri_getir()
        if not df_rez.empty:
            df_goster = df_rez.drop(columns=['secim_detaylari'], errors='ignore')
            
            arama_metni = st.text_input("Arama Yap (Sicil, İsim, Başkanlık veya Müdürlük)", placeholder="Örn: Ahmet, 12345 veya GELİR")
            if arama_metni:
                df_goster = df_goster[
                    df_goster['sicil'].astype(str).str.contains(arama_metni, case=False) |
                    df_goster['ad_soyad'].str.contains(arama_metni, case=False) |
                    df_goster['baskanlik'].str.contains(arama_metni, case=False) |
                    df_goster['mudurluk'].str.contains(arama_metni, case=False)
                ]
                
            st.dataframe(df_goster, use_container_width=True)
            
            col_ex1, col_ex2, _ = st.columns([1, 1, 2])
            with col_ex1:
                st.download_button(
                    label="🟢 Excel Olarak İndir (.xlsx)",
                    data=to_excel(df_goster),
                    file_name="eylul_2026_rezervasyon_listesi.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_ex2:
                st.download_button(
                    label="📄 CSV Olarak İndir (.csv)",
                    data=df_goster.to_csv(index=False).encode('utf-8-sig'),
                    file_name="eylul_2026_rezervasyon_listesi.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.warning("Henüz sistemde kayıtlı bir rezervasyon verisi bulunmamaktadır.")

