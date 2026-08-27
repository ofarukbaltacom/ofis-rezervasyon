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

ADMIN_PASSWORD = "kogm2071"
DB_FILE = "/tmp/rezervasyonlar.db"

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

TUM_GUNLER = [gun for gunler in EYLUL_HAFTALARI.values() for gun in gunler]

# ==============================================================================
# VERİTABANI İŞLEMLERİ
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gunluk_kontenjanlar (
            tarih TEXT,
            tesis_adi TEXT,
            limit_sayisi INTEGER,
            PRIMARY KEY (tarih, tesis_adi)
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

def gunluk_kontenjan_guncelle(tarih, tesis_adi, yeni_limit):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gunluk_kontenjanlar (tarih, tesis_adi, limit_sayisi) 
        VALUES (?, ?, ?) 
        ON CONFLICT(tarih, tesis_adi) DO UPDATE SET limit_sayisi = excluded.limit_sayisi
    """, (tarih, tesis_adi, yeni_limit))
    conn.commit()
    conn.close()

def gunluk_kontenjanlari_getir():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT tarih, tesis_adi, limit_sayisi FROM gunluk_kontenjanlar")
    rows = cursor.fetchall()
    conn.close()
    res = {}
    for r in rows:
        res[(r[0], r[1])] = r[2]
    return res

def gun_tesis_limiti_getir(tarih, tesis_adi):
    gunluk_dict = gunluk_kontenjanlari_getir()
    if (tarih, tesis_adi) in gunluk_dict:
        return gunluk_dict[(tarih, tesis_adi)]
    genel_dict = kontenjanlari_getir()
    return genel_dict.get(tesis_adi, 30 if tesis_adi == "Atatürk Havalimanı" else 20)

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

def kayit_sil(rezervasyon_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rezervasyonlar WHERE id = ?", (rezervasyon_id,))
    conn.commit()
    conn.close()

def tum_rezervasyonlari_temizle():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rezervasyonlar")
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
    genel_limits = kontenjanlari_getir()
    st.title("🏢 Eylül 2026 Uydu Ofis Kullanım / Rezervasyon Formu")
    st.markdown("Lütfen kişisel bilgilerinizi giriniz ve Eylül ayı için haftalık **en fazla 2 gün** olacak şekilde ofis günlerinizi seçiniz.")
    st.info(f"💡 **Günlük Kontenjanlar:** Atatürk Havalimanı ({genel_limits.get('Atatürk Havalimanı', 30)} Kişi) | Libadiye Teknoloji Ofisi ({genel_limits.get('Libadiye Teknoloji Ofisi', 20)} Kişi)")

    with st.form("aylik_rezervasyon_formu"):
        st.subheader("👤 Kullanıcı Bilgileri")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            sicil = st.text_input("Sicil Bilgisi", placeholder="Örn: 12345")
            ad_soyad = st.text_input("İsim Soyisim", placeholder="Adınızı ve soyadınızı giriniz")
            
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
                
                limit_ataturk = gun_tesis_limiti_getir(gun, "Atatürk Havalimanı")
                dolu_ataturk = gun_tesis_dolu_sayisi(gun, "Atatürk Havalimanı")
                kalan_ataturk = max(0, limit_ataturk - dolu_ataturk)
                ataturk_label = f"{gun} - Atatürk Havalimanı ({kalan_ataturk} yer kaldı)" if kalan_ataturk > 0 else f"{gun} - Atatürk Havalimanı (⚠️ DOLDU)"
                
                limit_libadiye = gun_tesis_limiti_getir(gun, "Libadiye Teknoloji Ofisi")
                dolu_libadiye = gun_tesis_dolu_sayisi(gun, "Libadiye Teknoloji Ofisi")
                kalan_libadiye = max(0, limit_libadiye - dolu_libadiye)
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

        st.warning("""
        Aşağıdaki kurallara ay içinde 3 defa uymayan çalışanlarımızın ilgili ofislere giriş yetkileri kısıtlanacaktır.

        • Rezervasyon yapıp gitmemek ve gitmediği bilgisini KOPS ile paylaşmamak,
        • Rezervasyon yaptığı günden farklı günde veya farklı lokasyonu kullanmak.
        """)
        
        onay = st.checkbox("Okudum, onaylıyorum.")

        submit_btn = st.form_submit_button("Eylül Ayı Rezervasyonunu Onayla", use_container_width=True)

    if submit_btn:
        if not onay:
            st.error("⚠️ Lütfen formu göndermeden önce kural ve bilgilendirme metnini okuyup onaylayınız!")
        elif baskanlik == "Başkanlık Seçiniz..." or mudurluk == "Müdürlük Seçiniz...":
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

        st.subheader("🛠️ Genel Kontenjan Limiti Düzenleme")
        limittler = kontenjanlari_getir()
        
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            yeni_ataturk = st.number_input("Atatürk Havalimanı (Genel Limit)", min_value=1, value=limittler.get("Atatürk Havalimanı", 30), step=1)
        with col_k2:
            yeni_libadiye = st.number_input("Libadiye Teknoloji Ofisi (Genel Limit)", min_value=1, value=limittler.get("Libadiye Teknoloji Ofisi", 20), step=1)
            
        if st.button("💾 Genel Kontenjan Limitlerini Güncelle"):
            kontenjan_guncelle("Atatürk Havalimanı", yeni_ataturk)
            kontenjan_guncelle("Libadiye Teknoloji Ofisi", yeni_libadiye)
            st.success("✅ Genel kontenjan limitleri başarıyla güncellendi!")
            st.rerun()

        st.divider()
        
        st.subheader("📅 Tarih Bazlı Özel Kontenjan Tanımlama")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            secilen_tarih = st.selectbox("Tarih Seçin", options=TUM_GUNLER)
        with col_t2:
            secilen_tesis = st.selectbox("Tesis Seçin", options=["Atatürk Havalimanı", "Libadiye Teknoloji Ofisi"])
        with col_t3:
            mevcut_limit = gun_tesis_limiti_getir(secilen_tarih, secilen_tesis)
            ozel_limit = st.number_input(f"Özel Kontenjan Limiti ({secilen_tarih})", min_value=1, value=mevcut_limit, step=1)

        if st.button("📌 Seçili Tarih İçin Kontenjanı Güncelle"):
            gunluk_kontenjan_guncelle(secilen_tarih, secilen_tesis, ozel_limit)
            st.success(f"✅ {secilen_tarih} günü için {secilen_tesis} kontenjanı **{ozel_limit}** olarak güncellendi!")
            st.rerun()

        st.divider()
        st.subheader("📊 Günlük Kontenjan Doluluk Durumları (Eylül 2026)")
        
        ozet_list = []
        for hafta, gunler in EYLUL_HAFTALARI.items():
            for g in gunler:
                limit_ataturk = gun_tesis_limiti_getir(g, "Atatürk Havalimanı")
                d_ataturk = gun_tesis_dolu_sayisi(g, "Atatürk Havalimanı")
                
                limit_libadiye = gun_tesis_limiti_getir(g, "Libadiye Teknoloji Ofisi")
                d_libadiye = gun_tesis_dolu_sayisi(g, "Libadiye Teknoloji Ofisi")
                
                ozet_list.append({
                    "Hafta": hafta,
                    "Tarih": g,
                    "Atatürk (Dolu / Limit)": f"{d_ataturk} / {limit_ataturk}",
                    "Libadiye (Dolu / Limit)": f"{d_libadiye} / {limit_libadiye}"
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
            
            # --- EXCEL (.XLSX) OLARAK İNDİRME BUTONU ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_goster.to_excel(writer, index=False, sheet_name='Eylül Rezervasyonları')

            st.download_button(
                label="📊 Excel Olarak İndir (.xlsx)",
                data=buffer.getvalue(),
                file_name="eylul_2026_rezervasyon_listesi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            st.divider()
            st.subheader("🗑️ Rezervasyon Verisi / Test Kaydı Silme")
            
            col_del1, col_del2 = st.columns([2, 1])
            with col_del1:
                silinecek_id = st.selectbox(
                    "Silmek İstediğiniz Kaydın ID Numarasını Seçin:",
                    options=df_rez['id'].tolist(),
                    format_func=lambda x: f"ID: {x} | {df_rez[df_rez['id'] == x]['ad_soyad'].values[0]} ({df_rez[df_rez['id'] == x]['sicil'].values[0]})"
                )
            with col_del2:
                st.write("")
                st.write("") 
                if st.button("❌ Seçili Kaydı Sil", use_container_width=True):
                    kayit_sil(silinecek_id)
                    st.success(f"ID {silinecek_id} numaralı kayıt başarıyla silindi ve kontenjan açıldı!")
                    st.rerun()

            with st.expander("⚠️ Tesis / Test Verilerini Sıfırla (Tüm Kayıtları Sil)"):
                st.warning("Bu işlem veritabanındaki TÜM kullanıcı rezervasyonlarını kalıcı olarak siler ve kontenjanları sıfırlar!")
                if st.button("🔥 Tüm Rezervasyon Verilerini Sil"):
                    tum_rezervasyonlari_temizle()
                    st.success("Tüm veriler başarıyla temizlendi!")
                    st.rerun()
        else:
            st.warning("Henüz sistemde kayıtlı bir rezervasyon verisi bulunmamaktadır.")
