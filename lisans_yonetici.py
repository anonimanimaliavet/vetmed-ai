import datetime
import streamlit as st
from supabase import create_client, Client
import uuid
import streamlit as st
import sqlite3  # BU SATIRI EKLEYİN
import os

import sqlite3
import os
import streamlit as st

# Veritabanı Yolunu Sabitle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "vetmed_klinik.db")

# HER SAYFA YENİLENDİĞİNDE TABLOYU KONTROL ET VE YOKSA YARAT
def tablolari_garantiye_al():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS kullanicilar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  kullanici_adi TEXT UNIQUE,
                  sifre TEXT,
                  aktif_mi INTEGER DEFAULT 1,
                  yetkili_moduller TEXT DEFAULT 'AI Teşhis Asistanı, Pre-Op (Cerrahi Hazırlık), Çoklu Röntgen & Hibrit Konsültasyon, Detaylı Vaka Girişi & Güvenlik')''')
    conn.commit()
    conn.close()

tablolari_garantiye_al()

# --- Geri kalan kodlarınız (Kullanıcı ekleme, listeleme vb.) buradan aşağıya devam etsin ---

# --- AYARLAR ---
SUPABASE_URL = "https://ukwskngnerynnuygrzrl.supabase.co"
SUPABASE_KEY = "sb_publishable_lRMxOBQ5V-lG_OCMFThG_g_iqCgin_i"
YONETICI_SIFRESI = "vetmed2026" # Panele girmek için kullanacağın şifre

# --- SUPABASE BAĞLANTISI ---
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

st.set_page_config(page_title="VetMed Admin Paneli", page_icon="⚙️", layout="centered")

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
    
    # Şifre girilmeden alt kısımdaki kodların çalışmasını engelliyoruz:
    st.stop()

# --- 2. YÖNETİCİ PANELİ (GİRİŞ BAŞARILIYSA GÖRÜNÜR) ---
st.title("⚙️ VetMed AI - Yönetici Paneli")

# Çıkış Yap Butonu
if st.sidebar.button("🚪 Çıkış Yap"):
    st.session_state.admin_giris_yapildi = False
    st.rerun()

# Menüleri Sekmelere (Tab) Ayırma
tab1, tab2, tab3 = st.tabs(["🆕 Yeni Lisans Üret", "📋 Lisansları Yönet", "⚙️ Sistem ve Kullanıcılar"])

# --- SEKME 1: LİSANS ÜRETME ---
with tab1:
    st.header("Yeni Lisans Üret")
    
    lisans_tipi_secimi = st.radio("Lisans Türünü Seçin:", ["Tek/Çok Kullanımlık", "Süreli (Tarih Bazlı)"])
    
    if lisans_tipi_secimi == "Tek/Çok Kullanımlık":
        st.info("Bu lisans sadece belirlenen limit kadar kullanılabilir (Örn: 1 kez).")
        max_kullanim = st.number_input("Kullanım Hakkı:", min_value=1, value=1, step=1)
        tip_kodu = "kullanim"
        son_tarih = None
        
    else:
        st.info("Bu lisans belirlenen gün boyunca SINIRSIZ kullanılabilir.")
        gecerlilik_gunu = st.number_input("Kaç Gün Geçerli Olsun?", min_value=1, value=30, step=1)
        max_kullanim = 999999 
        tip_kodu = "sureli"
        son_tarih = (datetime.datetime.now() + datetime.timedelta(days=gecerlilik_gunu)).isoformat()

    if st.button("Lisans Kodu Oluştur", type="primary"):
        yeni_kod = "VET-" + str(uuid.uuid4()).split('-')[0].upper()
        try:
            supabase.table("lisanslar").insert({
                "lisans_kodu": yeni_kod,
                "max_kullanim": max_kullanim,
                "lisans_tipi": tip_kodu,
                "son_kullanma_tarihi": son_tarih
            }).execute()
            st.success(f"✅ Lisans oluşturuldu!\n\n**Müşteriye Verilecek Kod:** `{yeni_kod}`")
        except Exception as e:
            st.error(f"Hata oluştu: {e}")

# --- SEKME 2: LİSANS YÖNETİMİ (AKTİF/PASİF/SİL) ---
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
            st.subheader("Lisans Üzerinde İşlem Yap")
            
            lisans_kodlari = [l["lisans_kodu"] for l in lisanslar]
            secilen_kod = st.selectbox("İşlem yapmak istediğiniz lisans kodunu seçin:", lisans_kodlari)
            
            secilen_lisans = next((l for l in lisanslar if l["lisans_kodu"] == secilen_kod), None)
            
            if secilen_lisans:
                durum_metni = "Aktif 🟢" if secilen_lisans["aktif"] else "Pasif 🔴"
                st.write(f"**Seçilen Kod:** `{secilen_kod}` | **Şu Anki Durum:** {durum_metni}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if secilen_lisans["aktif"]:
                        if st.button("🔴 Lisansı Pasife Al (Kilitle)"):
                            supabase.table("lisanslar").update({"aktif": False}).eq("lisans_kodu", secilen_kod).execute()
                            st.success("Lisans başarıyla pasif edildi! Kullanıcı artık bu kodla giremez.")
                            st.rerun()
                    else:
                        if st.button("🟢 Lisansı Aktif Et (Kilidi Aç)"):
                            supabase.table("lisanslar").update({"aktif": True}).eq("lisans_kodu", secilen_kod).execute()
                            st.success("Lisans başarıyla tekrar aktif edildi!")
                            st.rerun()
                
                with col2:
                    if st.button("🗑️ Lisansı Tamamen Sil", type="primary"):
                        supabase.table("lisanslar").delete().eq("lisans_kodu", secilen_kod).execute()
                        st.error("Lisans sistemden kalıcı olarak silindi!")
                        st.rerun()
                        
    except Exception as e:
        st.error(f"Veriler çekilirken bir bağlantı hatası oluştu: {e}")

# --- SEKME 3: SİSTEM ŞALTERLERİ VE KULLANICILAR ---
with tab3:
    st.header("Sistem Giriş Şalterleri")
    
    # Mevcut ayarları veritabanından çek
    ayarlar = supabase.table("sistem_ayarlari").select("*").eq("id", 1).execute().data[0]
    
    # Şalterler (Toggle) - AÇIK ERİŞİM EKLENDİ
    acik_erisim_drm = st.toggle("🔓 Açık Erişim Modu (Giriş ve Lisans Kontrollerini Tamamen Kapat)", value=ayarlar.get("acik_erisim", False))
    yeni_lisans_drm = st.toggle("🔑 Lisans Kodu ile Girişe İzin Ver", value=ayarlar["lisans_aktif"])
    yeni_kul_drm = st.toggle("👤 Kullanıcı Adı / Şifre ile Girişe İzin Ver", value=ayarlar["kullanici_aktif"])
    
    if st.button("Ayarları Kaydet", type="primary"):
        supabase.table("sistem_ayarlari").update({
            "acik_erisim": acik_erisim_drm,
            "lisans_aktif": yeni_lisans_drm, 
            "kullanici_aktif": yeni_kul_drm
        }).eq("id", 1).execute()
        st.success("Sistem giriş ayarları başarıyla güncellendi!")
        
    st.divider()
    
    st.header("Yeni Kullanıcı Hesabı Ekle")
    k_adi = st.text_input("Kullanıcı Adı (Örn: dr_ahmet):")
    k_sifre = st.text_input("Şifre Belirleyin:", type="password")
    
    if st.button("Kullanıcı Oluştur"):
        if k_adi and k_sifre:
            try:
                supabase.table("kullanicilar").insert({
                    "kullanici_adi": k_adi,
                    "sifre": k_sifre
                }).execute()
                st.success(f"✅ '{k_adi}' kullanıcısı başarıyla oluşturuldu!")
            except Exception as e:
                st.error("Bu kullanıcı adı zaten mevcut olabilir veya bağlantı hatası oluştu.")
        else:
            st.warning("Lütfen kullanıcı adı ve şifre girin.")

            import sqlite3
import os
import streamlit as st

# Veritabanı yolunu ayarla (pages klasöründe olduğumuz için bir üst klasöre bakıyoruz)
import sqlite3
import os
import streamlit as st

# Veritabanı yolunu ayarla (Artık ana dizinde olduğumuz için doğrudan BASE_DIR kullanıyoruz)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "vetmed_klinik.db")

# 1. TABLO OLUŞTURMA (Eğer yoksa otomatik oluşturur)
def kullanici_tablosu_olustur():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS kullanicilar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  kullanici_adi TEXT UNIQUE,
                  sifre TEXT,
                  aktif_mi INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

kullanici_tablosu_olustur()

st.divider()
st.header("👥 Kullanıcı Yönetimi")

# --- HATA ÇÖZÜMÜ İÇİN GEÇİCİ BUTON (GÜNCELLENDİ) ---
if st.button("🚨 Bulut Veritabanını Onar / Sıfırla"):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 1. Eski sorunlu tabloyu tamamen sil
        c.execute("DROP TABLE IF EXISTS kullanicilar")
        
        # 2. Tabloyu en güncel haliyle (yetkili_moduller sütunuyla birlikte) SIFIRDAN YARAT
        c.execute('''CREATE TABLE kullanicilar
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      kullanici_adi TEXT UNIQUE,
                      sifre TEXT,
                      aktif_mi INTEGER DEFAULT 1,
                      yetkili_moduller TEXT DEFAULT 'AI Teşhis Asistanı, Pre-Op (Cerrahi Hazırlık), Çoklu Röntgen & Hibrit Konsültasyon')''')
        
        conn.commit()
        conn.close()
        
        st.success("✅ Veritabanı başarıyla onarıldı! Sistem güncel.")
        st.rerun()
    except Exception as e:
        st.error(f"Onarım sırasında hata: {e}")
# ---------------------------------------------------

def tabloya_modul_yetkisi_ekle():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Kullanıcılar tablosuna yetki sütunu ekliyoruz (Varsayılan olarak hepsine açık)
        c.execute("ALTER TABLE kullanicilar ADD COLUMN yetkili_moduller TEXT DEFAULT 'AI Teşhis Asistanı, Pre-Op (Cerrahi Hazırlık), Çoklu Röntgen & Hibrit Konsültasyon'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Sütun zaten daha önce eklendiyse hata vermeden devam et
    conn.close()

tabloya_modul_yetkisi_ekle()

# --- 2. KULLANICI EKLEME BÖLÜMÜ ---
modul_listesi = [
    "AI Teşhis Asistanı", 
    "Pre-Op (Cerrahi Hazırlık)", 
    "Çoklu Röntgen & Hibrit Konsültasyon", 
    "Detaylı Vaka Girişi & Güvenlik"
]

with st.expander("➕ Yeni Kullanıcı Ekle"):
    with st.form("yeni_kullanici_formu", clear_on_submit=True):
        yeni_kullanici = st.text_input("Kullanıcı Adı")
        yeni_sifre = st.text_input("Şifre", type="password")
        
        # Yeni çoklu seçim alanı
        secilen_moduller = st.multiselect("Erişilebilecek Modülleri Seçin", modul_listesi, default=modul_listesi)
        
        ekle_buton = st.form_submit_button("Kullanıcıyı Kaydet")
        
        if ekle_buton and yeni_kullanici and yeni_sifre:
            # Seçimleri veritabanına yazabilmek için virgüllü metne çeviriyoruz
            modul_metni = ", ".join(secilen_moduller) 
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, aktif_mi, yetkili_moduller) VALUES (?, ?, ?, ?)", 
                      (yeni_kullanici, yeni_sifre, 1, modul_metni))
            conn.commit()
            conn.close()
            st.success("Kullanıcı ve modül yetkileri başarıyla kaydedildi!")
            st.rerun()
# --- 3. KULLANICILARI LİSTELEME VE YÖNETME BÖLÜMÜ ---
st.subheader("Mevcut Kullanıcılar")

# --- 3. KULLANICILARI LİSTELEME VE YÖNETME BÖLÜMÜ ---
st.subheader("Mevcut Kullanıcılar")

# Veritabanından mevcut kullanıcıları çek (Kendi Kendini Onaran Yapı)
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

try:
    c.execute("SELECT id, kullanici_adi, aktif_mi FROM kullanicilar")
    kullanicilar = c.fetchall()
except sqlite3.OperationalError:
    # Eğer GitHub'dan eski/bozuk tablo geldiyse, çökme! Tabloyu sil ve yenisini yap.
    c.execute("DROP TABLE IF EXISTS kullanicilar")
    c.execute('''CREATE TABLE kullanicilar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  kullanici_adi TEXT UNIQUE,
                  sifre TEXT,
                  aktif_mi INTEGER DEFAULT 1,
                  yetkili_moduller TEXT DEFAULT 'AI Teşhis Asistanı, Pre-Op (Cerrahi Hazırlık), Çoklu Röntgen & Hibrit Konsültasyon')''')
    conn.commit()
    kullanicilar = [] # Tablo yeni sıfırlandığı için liste boş
    st.warning("⚠️ Buluttaki eski veritabanı tespit edildi ve otomatik olarak onarıldı. Lütfen kullanıcıları yeniden ekleyin.")

conn.close()

# Eğer kullanıcı varsa listele (Eski kodunuz buradan itibaren aynı kalabilir)
if kullanicilar:
    # ...
        # Durum Göstergesi
        durum_metin = "🟢 Aktif" if aktif_mi == 1 else "🔴 Pasif"
        c2.write(durum_metin)
        
        # Durum Değiştirme Butonu (Aktif <-> Pasif)
        buton_metni = "Pasif Yap" if aktif_mi == 1 else "Aktif Yap"
        if c3.button(buton_metni, key=f"durum_{user_id}"):
            yeni_durum = 0 if aktif_mi == 1 else 1
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE kullanicilar SET aktif_mi = ? WHERE id = ?", (yeni_durum, user_id))
            conn.commit()
            conn.close()
            st.rerun()
            
        # Silme Butonu
        if c4.button("❌", key=f"sil_{user_id}"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM kullanicilar WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            st.rerun()
else:
    st.info("Sistemde henüz kayıtlı kullanıcı bulunmuyor.")