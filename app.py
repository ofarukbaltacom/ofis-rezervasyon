import streamlit as st
import pandas as pd
import io
import os
# Sayfa Konfigürasyonu
st.set_page_config(
   page_title="Tesis Rezervasyon & Yönetim Portalı",
   page_icon="🏢",
   layout="wide"
)
ADMIN_PASSWORD = "123"
DATA_FILE = "rezervasyonlar.csv"
# --- KALICI VERİ DOKUMA / YAZMA FONKSİYONLARI ---
def verileri_yukle():
   if os.path.exists(DATA_FILE):
       try:
           df = pd.read_csv(DATA_FILE)
           return df.to_dict('records')
       except Exception:
           return []
   return []
def veriyi_kaydet(yeni_kayit):
   df_yeni = pd.DataFrame([yeni_kayit])
   if not os.path.exists(DATA_FILE):
       df_yeni.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
   else:
       df_yeni.to_csv(DATA_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
# Session State Başlatma
if 'rezervasyonlar' not in st.session_state:
   st.session_state.rezervasyonlar = verileri_yukle()
if 'kontenjan_data' not in st.session_state:
   st.session_state.kontenjan_data = {
       "Atatürk Havalimanı": 150,
       "Libadiye Teknoloji Ofisi": 100
   }
if 'admin_logged_in' not in st.session_state:
   st.session_state.admin_logged_in = False
# Excel İhraç Fonksiyonu
def to_excel(df):
   output = io.BytesIO()
   with pd.ExcelWriter(output, engine='openpyxl') as writer:
       df.to_excel(writer, index=False, sheet_name='Rezervasyonlar')
   return output.getvalue()
# Dolu Sayısını Kayıtlardan Hesapla
def dolu_sayisi(tesis_adi):
   return sum(1 for r in st.session_state.rezervasyonlar if r.get("Tesis") == tesis_adi)
# --- SIDEBAR MENÜ ---
st.sidebar.title("📌 Menü")
sayfa = st.sidebar.radio(
   "Gitmek İstediğiniz Sayfayı Seçin:",
   ["📝 Rezervasyon Oluştur", "⚙️ Yönetim Dashboard'u"]
)
# ==============================================================================
# SAYFA 1: KULLANICI REZERVASYON PORTALI
# ==============================================================================
if sayfa == "📝 Rezervasyon Oluştur":
   st.title("🏢 Tesis Kullanım ve Kontenjan Portalı")
   st.markdown("Lütfen bilgilerinizi girerek kullanmak istediğiniz tesisi seçiniz.")
   # Anlık Tesis Doluluk Durumu
   st.subheader("📊 Anlık Tesis Doluluk Durumu")
   tesisler = list(st.session_state.kontenjan_data.keys())
   cols = st.columns(len(tesisler) if len(tesisler) > 0 else 1)
   for idx, (tesis_adi, toplam_kontenjan) in enumerate(st.session_state.kontenjan_data.items()):
       dolu = dolu_sayisi(tesis_adi)
       kalan = max(0, toplam_kontenjan - dolu)
       oran = (dolu / toplam_kontenjan * 100) if toplam_kontenjan > 0 else 0
       target_col = cols[idx % len(cols)]
       with target_col:
           st.metric(
               label=f"**{tesis_adi}**",
               value=f"%{oran:.1f} Dolu",
               delta=f"{kalan} Kalan Yer",
               delta_color="normal" if kalan > 10 else "inverse"
           )
           st.progress(min(oran / 100, 1.0))
   st.divider()
   # Form
   st.subheader("📝 Rezervasyon Formu")
   with st.form("rezervasyon_formu", clear_on_submit=True):
       col_f1, col_f2 = st.columns(2)
       with col_f1:
           sicil = st.text_input("Sicil Bilgisi", placeholder="Örn: 12345")
           ad_soyad = st.text_input("İsim Soyisim", placeholder="Adınızı ve soyadınızı giriniz")
       with col_f2:
           mudurluk = st.text_input("Müdürlük", placeholder="Bağlı olduğunuz müdürlük")
           unvan = st.text_input("Ünvan", placeholder="Göreviniz / Ünvanınız")
       tesis_secimi = st.selectbox(
           "Gidilecek Tesis",
           options=list(st.session_state.kontenjan_data.keys())
       )
       if tesis_secimi:
           toplam_k = st.session_state.kontenjan_data[tesis_secimi]
           secilen_kalan = toplam_k - dolu_sayisi(tesis_secimi)
           st.info(f"💡 **{tesis_secimi}** için güncel kalan kontenjan: **{secilen_kalan}**")
       submit_btn = st.form_submit_button("Rezervasyonu Onayla", use_container_width=True)
   if submit_btn:
       if not (sicil and ad_soyad and mudurluk and unvan):
           st.error("⚠️ Lütfen formdaki tüm alanları eksiksiz doldurunuz!")
       elif secilen_kalan <= 0:
           st.error(f"❌ Üzgünüz, {tesis_secimi} tesisinin kontenjanı tamamen dolmuştur.")
       else:
           yeni_kayit = {
               "Sicil": sicil,
               "Ad Soyad": ad_soyad,
               "Müdürlük": mudurluk,
               "Ünvan": unvan,
               "Tesis": tesis_secimi
           }
           # Hafızaya ve kalıcı dosyaya kaydet
           st.session_state.rezervasyonlar.append(yeni_kayit)
           veriyi_kaydet(yeni_kayit)
           st.success(f"✅ Sayın {ad_soyad}, {tesis_secimi} için rezervasyonunuz başarıyla oluşturuldu!")
           st.rerun()
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
       # Kontenjan Ayarları
       col_adm1, col_adm2 = st.columns([2, 1])
       with col_adm1:
           st.subheader("🔧 Tesis Kontenjan Limitlerini Güncelle")
           for tesis_adi, toplam_k in st.session_state.kontenjan_data.items():
               with st.expander(f"📌 **{tesis_adi}** Ayarları", expanded=True):
                   c1, c2 = st.columns(2)
                   yeni_toplam = c1.number_input(
                       f"Toplam Kontenjan ({tesis_adi})",
                       min_value=0,
                       value=toplam_k,
                       key=f"toplam_{tesis_adi}"
                   )
                   c2.metric("Mevcut Kayıtlı Sayısı", dolu_sayisi(tesis_adi))
                   if st.button(f"Kaydet: {tesis_adi}", key=f"btn_{tesis_adi}"):
                       st.session_state.kontenjan_data[tesis_adi] = yeni_toplam
                       st.success(f"{tesis_adi} kontenjan bilgisi güncellendi.")
                       st.rerun()
       with col_adm2:
           st.subheader("➕ Yeni Tesis Ekle")
           with st.form("yeni_tesis_formu"):
               yeni_tesis_adi = st.text_input("Tesis Adı")
               yeni_tesis_toplam = st.number_input("Toplam Kontenjan", min_value=1, value=50)
               yeni_tesis_btn = st.form_submit_button("Tesisi Ekle")
               if yeni_tesis_btn:
                   if yeni_tesis_adi.strip() == "":
                       st.error("Lütfen geçerli bir tesis adı giriniz.")
                   elif yeni_tesis_adi in st.session_state.kontenjan_data:
                       st.warning("Bu tesis zaten mevcut!")
                   else:
                       st.session_state.kontenjan_data[yeni_tesis_adi] = yeni_tesis_toplam
                       st.success(f"'{yeni_tesis_adi}' eklendi.")
                       st.rerun()
       st.divider()
       # Veri İhraç
       st.subheader("📥 Rezervasyon Verilerini İncele ve İhraç Et")
       # Güncel verileri dosyadan tekrar oku
       st.session_state.rezervasyonlar = verileri_yukle()
       if st.session_state.rezervasyonlar:
           df_rez = pd.DataFrame(st.session_state.rezervasyonlar)
           col_f1, col_f2 = st.columns([1, 2])
           with col_f1:
               secilen_tesis_filtre = st.multiselect(
                   "Tesis Filtresi",
                   options=list(st.session_state.kontenjan_data.keys()),
                   default=list(st.session_state.kontenjan_data.keys())
               )
           with col_f2:
               arama_metni = st.text_input("Arama Yap", placeholder="Sicil, İsim veya Müdürlük...")
           filtered_df = df_rez[df_rez['Tesis'].isin(secilen_tesis_filtre)]
           if arama_metni:
               filtered_df = filtered_df[
                   filtered_df['Sicil'].astype(str).str.contains(arama_metni, case=False) |
                   filtered_df['Ad Soyad'].str.contains(arama_metni, case=False) |
                   filtered_df['Müdürlük'].str.contains(arama_metni, case=False)
               ]
           st.dataframe(filtered_df, use_container_width=True)
           col_ex1, col_ex2, _ = st.columns([1, 1, 2])
           with col_ex1:
               st.download_button(
                   label="🟢 Excel Olarak İndir (.xlsx)",
                   data=to_excel(filtered_df),
                   file_name="tesis_rezervasyon_listesi.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   use_container_width=True
               )
           with col_ex2:
               st.download_button(
                   label="📄 CSV Olarak İndir (.csv)",
                   data=filtered_df.to_csv(index=False).encode('utf-8-sig'),
                   file_name="tesis_rezervasyon_listesi.csv",
                   mime="text/csv",
                   use_container_width=True
               )
       else:
           st.info("Henüz oluşturulmuş bir rezervasyon kaydı bulunmamaktadır.")