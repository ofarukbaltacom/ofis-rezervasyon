import streamlit as st

import pandas as pd

import io

import os

from datetime import datetime

# Sayfa Konfigürasyonu

st.set_page_config(

    page_title="Uydu Ofis Rezervasyon Portalı",

    page_icon="🏢",

    layout="wide"

)

ADMIN_PASSWORD = "123"

DATA_FILE = "rezervasyonlar.csv"

# --- KONTENJAN LİMİTLERİ ---

KONTENJAN_LIMITLERI = {

    "Atatürk Havalimanı": 30,

    "Libadiye Teknoloji Ofisi": 20

}

# --- EYLÜL 2026 HAFTALIK MESAİ GÜNLERİ ---

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

# 🚀 TÜM KULLANICILAR İÇİN ORTAK MERKEZİ VERİTABANI HAFIZASI

# ==============================================================================

@st.cache_resource

def get_global_database():

    """Tüm kullanıcılar ve sekmeler arasında anlık paylaşılan merkezi liste"""

    if os.path.exists(DATA_FILE):

        try:

            df = pd.read_csv(DATA_FILE)

            return df.to_dict('records')

        except Exception:

            return []

    return []

# Anlık Ortak Veri Listesi

VERITABANI = get_global_database()

def verileri_kaydet(yeni_kayitlar):

    VERITABANI.extend(yeni_kayitlar)

    try:

        df = pd.DataFrame(VERITABANI)

        df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

    except Exception:

        pass

def to_excel(df):

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        df.to_excel(writer, index=False, sheet_name='Eylul_Rezervasyonlari')

    return output.getvalue()

def gun_tesis_dolu_sayisi(tarih, tesis_adi):

    return sum(1 for r in VERITABANI if r.get("Tarih") == tarih and r.get("Tesis") == tesis_adi)

if 'admin_logged_in' not in st.session_state:

    st.session_state.admin_logged_in = False

# --- SIDEBAR MENÜ ---

st.sidebar.title("📌 Menü")

sayfa = st.sidebar.radio(

    "Gitmek İstediğiniz Sayfayı Seçin:",

    ["📝 Eylül Ayı Rezervasyon Formu", "⚙️ Yönetim Dashboard'u"]

)

# ==============================================================================

# SAYFA 1: KULLANICI REZERVASYON PORTALI (EYLÜL 2026)

# ==============================================================================

if sayfa == "📝 Eylül Ayı Rezervasyon Formu":

    st.title("🏢 Eylül 2026 Uydu Ofis Kullanım / Rezervasyon Formu")

    st.markdown("Lütfen kişisel bilgilerinizi giriniz ve Eylül ayı için haftalık **en fazla 2 gün** olacak şekilde ofis günlerinizi seçiniz.")

    st.info("💡 **Günlük Kontenjanlar:** Atatürk Havalimanı (30 Kişi) | Libadiye Teknoloji Ofisi (20 Kişi)")

    with st.form("aylik_rezervasyon_formu"):

        st.subheader("👤 Kullanıcı Bilgileri")

        col_f1, col_f2 = st.columns(2)

        with col_f1:

            sicil = st.text_input("Sicil Bilgisi", placeholder="Örn: 12345")

            ad_soyad = st.text_input("İsim Soyisim", placeholder="Adınızı ve soyadınızı giriniz")

        with col_f2:

            mudurluk = st.text_input("Müdürlük", placeholder="Bağlı olduğunuz müdürlük")

            unvan = st.text_input("Ünvan", placeholder="Göreviniz / Ünvanınız")

        st.divider()

        st.subheader("📅 Eylül 2026 Gün Seçimleri")

        secimler = {}

        for hafta_adi, gunler in EYLUL_HAFTALARI.items():

            st.markdown(f"#### 📌 **{hafta_adi}** *(En fazla 2 gün seçilebilir)*")

            for gun in gunler:

                c_a, c_l = st.columns(2)

                dolu_ataturk = gun_tesis_dolu_sayisi(gun, "Atatürk Havalimanı")

                kalan_ataturk = max(0, KONTENJAN_LIMITLERI["Atatürk Havalimanı"] - dolu_ataturk)

                ataturk_label = f"{gun} - Atatürk Havalimanı ({kalan_ataturk} yer kaldı)" if kalan_ataturk > 0 else f"{gun} - Atatürk Havalimanı (⚠️ DOLDU)"

                dolu_libadiye = gun_tesis_dolu_sayisi(gun, "Libadiye Teknoloji Ofisi")

                kalan_libadiye = max(0, KONTENJAN_LIMITLERI["Libadiye Teknoloji Ofisi"] - dolu_libadiye)

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

        if not (sicil.strip() and ad_soyad.strip() and mudurluk.strip() and unvan.strip()):

            st.error("⚠️ Lütfen en üstteki Sicil, İsim Soyisim, Müdürlük ve Ünvan alanlarını eksiksiz doldurunuz!")

        elif not secimler:

            st.error("⚠️ Lütfen en az bir gün için tesis seçimi yapınız!")

        else:

            kural_ihlali = False

            for hafta, secilen_gunler in secimler.items():

                if len(secilen_gunler) > 2:

                    st.error(f"❌ **{hafta}** için {len(secilen_gunler)} seçim yaptınız! Lütfen her hafta için en fazla 2 gün seçiniz.")

                    kural_ihlali = True

            if not kural_ihlali:

                yeni_kayitlar = []

                for hafta, gun_listesi in secimler.items():

                    for tarih, tesis in gun_listesi:

                        yeni_kayitlar.append({

                            "Sicil": sicil.strip(),

                            "Ad Soyad": ad_soyad.strip(),

                            "Müdürlük": mudurluk.strip(),

                            "Ünvan": unvan.strip(),

                            "Hafta": hafta,

                            "Tarih": tarih,

                            "Tesis": tesis,

                            "Kayıt Tarihi": datetime.now().strftime("%Y-%m-%d %H:%M")

                        })

                # Ortak Veritabanına Anında Kaydet

                verileri_kaydet(yeni_kayitlar)

                st.balloons()

                st.success(f"✅ Sayın **{ad_soyad}**, Eylül ayı için toplam **{len(yeni_kayitlar)} günlük** rezervasyon kaydınız başarıyla sistem veritabanına eklendi! Yönetim panelinden anında görebilirsiniz.")

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

        st.subheader("📊 Günlük Kontenjan Doluluk Durumları (Eylül 2026)")

        ozet_list = []

        for hafta, gunler in EYLUL_HAFTALARI.items():

            for g in gunler:

                d_ataturk = gun_tesis_dolu_sayisi(g, "Atatürk Havalimanı")

                d_libadiye = gun_tesis_dolu_sayisi(g, "Libadiye Teknoloji Ofisi")

                ozet_list.append({

                    "Hafta": hafta,

                    "Tarih": g,

                    "Atatürk (Dolu/30)": f"{d_ataturk} / 30",

                    "Libadiye (Dolu/20)": f"{d_libadiye} / 20"

                })

        st.dataframe(pd.DataFrame(ozet_list), use_container_width=True)

        st.divider()

        st.subheader("📥 Tüm Eylül Rezervasyon Verileri")

        if len(VERITABANI) > 0:

            df_rez = pd.DataFrame(VERITABANI)

            arama_metni = st.text_input("Arama Yap (Sicil, İsim veya Müdürlük)", placeholder="Örn: Ahmet veya 12345")

            if arama_metni:

                df_rez = df_rez[

                    df_rez['Sicil'].astype(str).str.contains(arama_metni, case=False) |

                    df_rez['Ad Soyad'].str.contains(arama_metni, case=False) |

                    df_rez['Müdürlük'].str.contains(arama_metni, case=False)

                ]

            st.dataframe(df_rez, use_container_width=True)

            col_ex1, col_ex2, _ = st.columns([1, 1, 2])

            with col_ex1:

                st.download_button(

                    label="🟢 Excel Olarak İndir (.xlsx)",

                    data=to_excel(df_rez),

                    file_name="eylul_2026_rezervasyon_listesi.xlsx",

                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

                    use_container_width=True

                )

            with col_ex2:

                st.download_button(

                    label="📄 CSV Olarak İndir (.csv)",

                    data=df_rez.to_csv(index=False).encode('utf-8-sig'),

                    file_name="eylul_2026_rezervasyon_listesi.csv",

                    mime="text/csv",

                    use_container_width=True

                )

        else:

            st.warning("⚠️ Henüz sistemde kayıtlı bir rezervasyon verisi bulunmamaktadır. Form sayfasından bir rezervasyon yapıldığında veriler anında burada görünecektir.")