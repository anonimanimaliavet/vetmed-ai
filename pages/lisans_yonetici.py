import datetime
import streamlit as st
from supabase import create_client, Client
import uuid

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