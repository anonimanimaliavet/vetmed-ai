import datetime
import uuid
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="VetMed Admin Paneli", page_icon="⚙️", layout="centered")

# --- SUPABASE BAĞLANTISI ---
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

# --- 2. YÖNETİCİ PANELİ ---
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

# --- SEKME 3: SİSTEM ŞALTERLERİ VE KULLANICILAR (SUPABASE ENTEGRELİ) ---
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
    st.header("👥 Bulut Kullanıcı Yönetimi (Supabase)")
    
    # 1. KULLANICI EKLEME
    modul_listesi = ["AI Teşhis Asistanı", "Pre-Op (Cerrahi Hazırlık)", "Çoklu Röntgen & Hibrit Konsültasyon", "Detaylı Vaka Girişi & Güvenlik"]
    
    with st.expander("➕ Yeni Kullanıcı Ekle (Kredili Sistem)"):
        with st.form("yeni_kullanici_formu", clear_on_submit=True):
            yeni_kullanici = st.text_input("Kullanıcı Adı")
            yeni_sifre = st.text_input("Şifre", type="password")
            secilen_moduller = st.multiselect("Erişilebilecek Modülleri Seçin", modul_listesi, default=modul_listesi)
            
            # Kredi Belirleme Alanları
            col_k1, col_k2, col_k3 = st.columns(3)
            kredi_ai = col_k1.number_input("AI Teşhis Kredisi", min_value=0, value=2)
            kredi_preop = col_k2.number_input("Pre-Op Kredisi", min_value=0, value=5)
            kredi_rontgen = col_k3.number_input("Röntgen Kredisi", min_value=0, value=3)
            
            if st.form_submit_button("Buluta Kaydet"):
                if yeni_kullanici and yeni_sifre:
                    modul_metni = ", ".join(secilen_moduller)
                    try:
                        kontrol = supabase.table("kullanicilar").select("*").eq("kullanici_adi", yeni_kullanici).execute()
                        if len(kontrol.data) > 0:
                            st.error("❌ Bu kullanıcı adı zaten mevcut!")
                        else:
                            supabase.table("kullanicilar").insert({
                                "kullanici_adi": yeni_kullanici,
                                "sifre": yeni_sifre,
                                "aktif_mi": True,
                                "yetkili_moduller": modul_metni,
                                "ai_kredi": kredi_ai,
                                "preop_kredi": kredi_preop,
                                "rontgen_kredi": kredi_rontgen
                            }).execute()
                            st.success(f"'{yeni_kullanici}' başarıyla eklendi! AI: {kredi_ai}, Pre-Op: {kredi_preop}, Röntgen: {kredi_rontgen}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Kayıt Hatası: {e}")
                else:
                    st.warning("Kullanıcı adı ve şifre zorunludur.")

    # 2. KULLANICI LİSTELEME VE DÜZENLEME
    st.subheader("Mevcut Kullanıcılar")
    try:
        kullanicilar = supabase.table("kullanicilar").select("*").order("id").execute().data
    except Exception:
        kullanicilar = []

    if kullanicilar:
        col1, col2, col3, col4, col5 = st.columns([2, 1, 3, 2, 1])
        col1.markdown("**Kullanıcı Adı**")
        col2.markdown("**Durum**")
        col3.markdown("**Krediler (AI / Pre / Rönt)**")
        col4.markdown("**İşlem**")
        col5.markdown("**Sil**")
        
        for user in kullanicilar:
            user_id = user["id"]
            k_adi = user["kullanici_adi"]
            aktif_mi = user.get("aktif_mi", True)
            c_ai = user.get("ai_kredi", 0)
            c_pre = user.get("preop_kredi", 0)
            c_ron = user.get("rontgen_kredi", 0)
            
            c1, c2, c3, c4, c5 = st.columns([2, 1, 3, 2, 1])
            c1.write(k_adi)
            c2.write("🟢" if aktif_mi else "🔴")
            c3.write(f"{c_ai} / {c_pre} / {c_ron}")
            
            if c4.button("Pasif Yap" if aktif_mi else "Aktif Yap", key=f"durum_{user_id}"):
                yeni_durum = not aktif_mi
                supabase.table("kullanicilar").update({"aktif_mi": yeni_durum}).eq("id", user_id).execute()
                st.rerun()
                
            if c5.button("❌", key=f"sil_{user_id}"):
                supabase.table("kullanicilar").delete().eq("id", user_id).execute()
                st.rerun()
    else:
        st.info("Bulut sisteminde henüz kayıtlı kullanıcı bulunmuyor.")