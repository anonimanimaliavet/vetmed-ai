import datetime
import uuid
import os
import sqlite3
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="VetMed Admin Paneli", page_icon="⚙️", layout="centered")

# --- VERİTABANI YOLU VE GÜVENLİK ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "vetmed_klinik.db")

def tablolari_garantiye_al():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Kendi kendini onaran ve modül yetkilerini içeren tam tablo yapısı
    c.execute('''CREATE TABLE IF NOT EXISTS kullanicilar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  kullanici_adi TEXT UNIQUE,
                  sifre TEXT,
                  aktif_mi INTEGER DEFAULT 1,
                  yetkili_moduller TEXT DEFAULT 'AI Teşhis Asistanı, Pre-Op (Cerrahi Hazırlık), Çoklu Röntgen & Hibrit Konsültasyon, Detaylı Vaka Girişi & Güvenlik')''')
    conn.commit()
    conn.close()

tablolari_garantiye_al()

# --- SUPABASE BAĞLANTISI (Sadece Lisanslar ve Ayarlar İçin) ---
SUPABASE_URL = "https://ukwskngnerynnuygrzrl.supabase.co"
SUPABASE_KEY = "sb_publishable_lRMxOBQ5V-lG_OCMFThG_g_iqCgin_i"
YONETICI_SIFRESI = "vetmed2026"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# --- 1. GÜVENLİ GİRİŞ EKRANI ---
if "admin_giris_yapildi" not in st.session_state:
    st.session_state.admin_giris_yapildi = False

if not st.session_state.admin_giris_yapildi:
    st.title("🔒 VetMed Lisans Yönetim Paneli")
    st.info("Panele erişmek için yönetici şifrenizi girin.")
    
    girilen_sifre = st.text_input("Yönetici Şifresi:", type="password")
    if st.button("Giriş Yap", type="primary"):
        if girilen_sifre == YONETICI_SIFRESI:
            st.session_state.admin_giris_yapildi = True
            st.rerun()
        else:
            st.error("❌ Hatalı şifre girdiniz!")
    st.stop()

# --- 2. YÖNETİCİ PANELİ (GİRİŞ BAŞARILIYSA GÖRÜNÜR) ---
st.title("⚙️ VetMed AI - Yönetici Paneli")

if st.sidebar.button("🚪 Çıkış Yap"):
    st.session_state.admin_giris_yapildi = False
    st.rerun()

tab1, tab2, tab3 = st.tabs(["🆕 Yeni Lisans Üret", "📋 Lisansları Yönet", "⚙️ Sistem ve Kullanıcılar"])

# --- SEKME 1: LİSANS ÜRETME ---
with tab1:
    st.header("Yeni Lisans Üret")
    lisans_tipi_secimi = st.radio("Lisans Türünü Seçin:", ["Tek/Çok Kullanımlık", "Süreli (Tarih Bazlı)"])
    
    if lisans_tipi_secimi == "Tek/Çok Kullanımlık":
        max_kullanim = st.number_input("Kullanım Hakkı:", min_value=1, value=1, step=1)
        tip_kodu, son_tarih = "kullanim", None
    else:
        gecerlilik_gunu = st.number_input("Kaç Gün Geçerli Olsun?", min_value=1, value=30, step=1)
        max_kullanim, tip_kodu = 999999, "sureli"
        son_tarih = (datetime.datetime.now() + datetime.timedelta(days=gecerlilik_gunu)).isoformat()

    if st.button("Lisans Kodu Oluştur", type="primary"):
        yeni_kod = "VET-" + str(uuid.uuid4()).split('-')[0].upper()
        try:
            supabase.table("lisanslar").insert({
                "lisans_kodu": yeni_kod, "max_kullanim": max_kullanim, 
                "lisans_tipi": tip_kodu, "son_kullanma_tarihi": son_tarih
            }).execute()
            st.success(f"✅ Lisans oluşturuldu!\n\n**Müşteriye Verilecek Kod:** `{yeni_kod}`")
        except Exception as e:
            st.error(f"Hata oluştu: {e}")

# --- SEKME 2: LİSANS YÖNETİMİ ---
with tab2:
    st.header("Mevcut Lisanslar")
    try:
        response = supabase.table("lisanslar").select("*").order("id", desc=True).execute()
        lisanslar = response.data
        if not lisanslar:
            st.info("Sistemde henüz oluşturulmuş bir lisans yok.")
        else:
            st.dataframe(lisanslar, use_container_width=True)
            st.divider()
            lisans_kodlari = [l["lisans_kodu"] for l in lisanslar]
            secilen_kod = st.selectbox("İşlem yapmak istediğiniz lisans kodunu seçin:", lisans_kodlari)
            secilen_lisans = next((l for l in lisanslar if l["lisans_kodu"] == secilen_kod), None)
            
            if secilen_lisans:
                durum_metni = "Aktif 🟢" if secilen_lisans["aktif"] else "Pasif 🔴"
                st.write(f"**Seçilen Kod:** `{secilen_kod}` | **Şu Anki Durum:** {durum_metni}")
                col1, col2 = st.columns(2)
                with col1:
                    if secilen_lisans["aktif"]:
                        if st.button("🔴 Lisansı Pasife Al"):
                            supabase.table("lisanslar").update({"aktif": False}).eq("lisans_kodu", secilen_kod).execute()
                            st.rerun()
                    else:
                        if st.button("🟢 Lisansı Aktif Et"):
                            supabase.table("lisanslar").update({"aktif": True}).eq("lisans_kodu", secilen_kod).execute()
                            st.rerun()
                with col2:
                    if st.button("🗑️ Lisansı Tamamen Sil", type="primary"):
                        supabase.table("lisanslar").delete().eq("lisans_kodu", secilen_kod).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Veriler çekilirken hata oluştu: {e}")

# --- SEKME 3: SİSTEM ŞALTERLERİ VE KULLANICILAR ---
with tab3:
    st.header("Sistem Giriş Şalterleri")
    ayarlar = supabase.table("sistem_ayarlari").select("*").eq("id", 1).execute().data[0]
    
    acik_erisim_drm = st.toggle("🔓 Açık Erişim Modu", value=ayarlar.get("acik_erisim", False))
    yeni_lisans_drm = st.toggle("🔑 Lisans ile Giriş", value=ayarlar["lisans_aktif"])
    yeni_kul_drm = st.toggle("👤 Kullanıcı Girişi", value=ayarlar["kullanici_aktif"])
    
    if st.button("Ayarları Kaydet", type="primary"):
        supabase.table("sistem_ayarlari").update({
            "acik_erisim": acik_erisim_drm, "lisans_aktif": yeni_lisans_drm, "kullanici_aktif": yeni_kul_drm
        }).eq("id", 1).execute()
        st.success("Giriş ayarları güncellendi!")
        
    st.divider()
    st.header("👥 Kullanıcı (Personel) Yönetimi")
    
    # KULLANICI EKLEME ALANI
    modul_listesi = ["AI Teşhis Asistanı", "Pre-Op (Cerrahi Hazırlık)", "Çoklu Röntgen & Hibrit Konsültasyon", "Detaylı Vaka Girişi & Güvenlik"]
    
    with st.expander("➕ Yeni Kullanıcı Ekle"):
        with st.form("yeni_kullanici_formu", clear_on_submit=True):
            yeni_kullanici = st.text_input("Kullanıcı Adı")
            yeni_sifre = st.text_input("Şifre", type="password")
            secilen_moduller = st.multiselect("Erişilebilecek Modülleri Seçin", modul_listesi, default=modul_listesi)
            
            if st.form_submit_button("Kullanıcıyı Kaydet"):
                if yeni_kullanici and yeni_sifre:
                    try:
                        modul_metni = ", ".join(secilen_moduller) 
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, aktif_mi, yetkili_moduller) VALUES (?, ?, ?, ?)", 
                                  (yeni_kullanici, yeni_sifre, 1, modul_metni))
                        conn.commit()
                        conn.close()
                        st.success(f"'{yeni_kullanici}' başarıyla kaydedildi!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("❌ Bu kullanıcı adı zaten mevcut!")
                else:
                    st.warning("Kullanıcı adı ve şifre zorunludur.")

    # KULLANICI LİSTELEME ALANI
    st.subheader("Mevcut Kullanıcılar")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT id, kullanici_adi, aktif_mi FROM kullanicilar")
        kullanicilar = c.fetchall()
    except sqlite3.OperationalError:
        c.execute("DROP TABLE IF EXISTS kullanicilar")
        tablolari_garantiye_al()
        kullanicilar = []
    conn.close()

    if kullanicilar:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        col1.markdown("**Kullanıcı Adı**")
        col2.markdown("**Durum**")
        col3.markdown("**İşlem**")
        col4.markdown("**Sil**")
        
        for user in kullanicilar:
            user_id, k_adi, aktif_mi = user[0], user[1], user[2]
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.write(k_adi)
            c2.write("🟢 Aktif" if aktif_mi == 1 else "🔴 Pasif")
            
            if c3.button("Pasif Yap" if aktif_mi == 1 else "Aktif Yap", key=f"durum_{user_id}"):
                yeni_durum = 0 if aktif_mi == 1 else 1
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE kullanicilar SET aktif_mi = ? WHERE id = ?", (yeni_durum, user_id))
                conn.commit()
                conn.close()
                st.rerun()
                
            if c4.button("❌", key=f"sil_{user_id}"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM kullanicilar WHERE id = ?", (user_id,))
                conn.commit()
                conn.close()
                st.rerun()
    else:
        st.info("Sistemde kayıtlı kullanıcı bulunmuyor.")