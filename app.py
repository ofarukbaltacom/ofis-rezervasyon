import streamlit as st
import pandas as pd
import io
# Sayfa Konfigürasyonu
st.set_page_config(
   page_title="Tesis Rezervasyon & Yönetim Portalı",
   page_icon="🏢",
   layout="wide"
)
# Admin Şifresi (Buradan değiştirebilirsiniz)
ADMIN_PASSWORD = "123"
# Session State Tanımlamaları
if 'kontenjan_data' not in st.session_state:
   st.session_state.kontenjan_data = {
       "Atatürk Havalimanı": {"toplam": 150, "dolu": 105},
       "Libadiye Teknoloji Ofisi": {"toplam": 100, "dolu": 92}
   }
if 'rezervasyonlar' not in st.session_state:
   st.session_state.rezervasyonlar = []
if 'admin_logged_in' not in st.session_state:
   st.session_state.admin_logged_in = False
# Excel İhraç Yardımcı Fonksiyonu
def to_excel(df):
   output = io.BytesIO()
   with pd.ExcelWriter(output, engine='openpyxl') as writer:
       df.to_excel(writer, index=False, sheet_name='Rezervasyonlar')
   return output.getvalue()
# --- YAN MENÜ (SIDEBAR) İLE SAYFA SEÇİMİ ---
st.sidebar.title("📌 Menü")
sayfa = st.sidebar.radio(
   "Gitmek İstediğiniz Sayfayı Seçin:",
   ["📝 Rezervasyon Oluştur", "⚙️ Yönetim Dashboard'u"]
)
# ==============================================================================
# SAYFA 1: KULLANICI REZERVASYON PORTALI
# ==============================================================================
if sayfa == "📝 Rezervasyon Oluştur":
   st.title("🏢 Turkish Cargo Uydu Ofis Kullanım ve Kontenjan Portalı")
   st.markdown("Lütfen bilgilerinizi girerek kullanmak istediğiniz tesisi seçiniz.")
   # Anlık Tesis Doluluk Durumu
   st.subheader("📊 Anlık Tesis Doluluk Durumu")
   tesisler = list(st.session_state.kontenjan_data.keys())
   cols = st.columns(len(tesisler) if len(tesisler) > 0 else 1)
   for idx, (tesis_adi, data) in enumerate(st.session_state.kontenjan_data.items()):
       toplam = data["toplam"]
       dolu = data["dolu"]
       kalan = max(0, toplam - dolu)
       oran = (dolu / toplam * 100) if toplam > 0 else 0
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
           secilen_tesis_data = st.session_state.kontenjan_data[tesis_secimi]
           secilen_kalan = secilen_tesis_data["toplam"] - secilen_tesis_data["dolu"]
           st.info(f"💡 **{tesis_secimi}** için güncel kalan kontenjan: **{secilen_kalan}**")
       submit_btn = st.form_submit_button("Rezervasyonu Onayla", use_container_width=True)
   if submit_btn:
       if not (sicil and ad_soyad and mudurluk and unvan):
           st.error("⚠️ Lütfen formdaki tüm alanları eksiksiz doldurunuz!")
       elif secilen_kalan <= 0:
           st.error(f"❌ Üzgünüz, {tesis_secimi} tesisinin kontenjanı tamamen dolmuştur.")
       else:
           st.session_state.kontenjan_data[tesis_secimi]["dolu"] += 1
           yeni_kayit = {
               "Sicil": sicil,
               "Ad Soyad": ad_soyad,
               "Müdürlük": mudurluk,
               "Ünvan": unvan,
               "Tesis": tesis_secimi
           }
           st.session_state.rezervasyonlar.append(yeni_kayit)
           st.success(f"✅ Sayın {ad_soyad}, {tesis_secimi} için rezervasyonunuz başarıyla oluşturuldu!")
           st.rerun()
# ==============================================================================
# SAYFA 2: YÖNETİM DASHBOARD'U (ŞİFRE KORUMALI)
# ==============================================================================
elif sayfa == "⚙️ Yönetim Dashboard'u":
   st.title("⚙️ Yönetim & Kontenjan Kontrol Paneli")
   # Şifre Doğrulama Arayüzü
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
       # Oturumu Kapat Butonu
       if st.sidebar.button("🚪 Yönetici Çıkışı Yap"):
           st.session_state.admin_logged_in = False
           st.rerun()
       # 1. Kontenjan Ayarları ve Yeni Tesis Ekleme
       col_adm1, col_adm2 = st.columns([2, 1])
       with col_adm1:
           st.subheader("🔧 Tesis Kontenjanlarını Güncelle")
           for tesis_adi, data in st.session_state.kontenjan_data.items():
               with st.expander(f"📌 **{tesis_adi}** Ayarları", expanded=True):
                   c1, c2 = st.columns(2)
                   yeni_toplam = c1.number_input(
                       f"Toplam Kontenjan ({tesis_adi})",
                       min_value=0,
                       value=data["toplam"],
                       key=f"toplam_{tesis_adi}"
                   )
                   yeni_dolu = c2.number_input(
                       f"Mevcut Dolu Sayısı ({tesis_adi})",
                       min_value=0,
                       value=data["dolu"],
                       key=f"dolu_{tesis_adi}"
                   )
                   if st.button(f"Kaydet: {tesis_adi}", key=f"btn_{tesis_adi}"):
                       st.session_state.kontenjan_data[tesis_adi]["toplam"] = yeni_toplam
                       st.session_state.kontenjan_data[tesis_adi]["dolu"] = yeni_dolu
                       st.success(f"{tesis_adi} kontenjan bilgileri güncellendi.")
                       st.rerun()
       with col_adm2:
           st.subheader("➕ Yeni Tesis Ekle")
           with st.form("yeni_tesis_formu"):
               yeni_tesis_adi = st.text_input("Tesis Adı")
               yeni_tesis_toplam = st.number_input("Toplam Kontenjan", min_value=1, value=50)
               yeni_tesis_dolu = st.number_input("Başlangıç Dolu Sayısı", min_value=0, value=0)
               yeni_tesis_btn = st.form_submit_button("Tesisi Ekle")
               if yeni_tesis_btn:
                   if yeni_tesis_adi.strip() == "":
                       st.error("Lütfen geçerli bir tesis adı giriniz.")
                   elif yeni_tesis_adi in st.session_state.kontenjan_data:
                       st.warning("Bu tesis zaten mevcut!")
                   else:
                       st.session_state.kontenjan_data[yeni_tesis_adi] = {
                           "toplam": yeni_tesis_toplam,
                           "dolu": yeni_tesis_dolu
                       }
                       st.success(f"'{yeni_tesis_adi}' eklendi.")
                       st.rerun()
       st.divider()
       # 2. Veri İhraç Alanı
       st.subheader("📥 Rezervasyon Verilerini İncele ve İhraç Et")
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