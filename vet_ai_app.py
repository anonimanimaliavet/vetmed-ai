import streamlit as st
import datetime
import time
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController

import json
import os

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"open_access_mode": False}

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)

# --- 1. SUPABASE VE BAĞLANTI AYARLARI ---
SUPABASE_URL = "https://ukwskngnerynnuygrzrl.supabase.co"
SUPABASE_KEY = "sb_publishable_lRMxOBQ5V-lG_OCMFThG_g_iqCgin_i"

def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
controller = CookieController()

# --- 2. OTURUM DURUMU VE GÜNCEL ŞALTER KONTROLÜ ---
if "lisans_onaylandi" not in st.session_state:
    st.session_state.lisans_onaylandi = False

try:
    # Veritabanından güncel şalter durumlarını anlık çek
    sistem_ayar = supabase.table("sistem_ayarlari").select("*").eq("id", 1).execute().data[0]
    
    acik_erisim = sistem_ayar.get("acik_erisim", False)
    lisans_aktif = sistem_ayar.get("lisans_aktif", False)
    kullanici_aktif = sistem_ayar.get("kullanici_aktif", False)
    
    # KONTROL 1: Eğer hepsi kapalıysa, içerideki kim varsa oturumunu düşür!
    if not acik_erisim and not lisans_aktif and not kullanici_aktif:
        st.session_state.lisans_onaylandi = False
        try:
            controller.remove('sureli_lisans')
        except:
            pass
            
    # KONTROL 2: Açık Erişim aktifse direkt içeri al
    elif acik_erisim:
        st.session_state.lisans_onaylandi = True

except:
    pass

# Eğer açık erişim kapalıysa ve tüm giriş yöntemleri kapandıysa direkt durdur
try:
    sistem_ayar = supabase.table("sistem_ayarlari").select("*").eq("id", 1).execute().data[0]
    if not sistem_ayar.get("acik_erisim", False) and not sistem_ayar.get("lisans_aktif", False) and not sistem_ayar.get("kullanici_aktif", False):
        if not st.session_state.lisans_onaylandi:
            st.title("🔐 VetMed AI - Kurumsal Giriş")
            st.warning("⛔ Sistem girişleri ve açık erişim geçici olarak tamamen kapatılmıştır.")
            st.stop()
except:
    pass

# Yönetici panelinden Açık Erişim şalteri açıldıysa girişleri direkt atla
try:
    sistem_ayar = supabase.table("sistem_ayarlari").select("*").eq("id", 1).execute().data[0]
    if sistem_ayar.get("acik_erisim", False):
        st.session_state.lisans_onaylandi = True
except:
    pass

# Eğer daha önceden çıkış yapılmadıysa ve çerez varsa hatırla
kayitli_sureli_lisans = controller.get('sureli_lisans')
if kayitli_sureli_lisans and not st.session_state.lisans_onaylandi:
    try:
        res = supabase.table("lisanslar").select("*").eq("lisans_kodu", kayitli_sureli_lisans).execute()
        if len(res.data) > 0:
            l_data = res.data[0]
            if l_data["aktif"] and l_data["lisans_tipi"] == "sureli":
                bitis_tarihi = datetime.datetime.fromisoformat(l_data["son_kullanma_tarihi"])
                su_an = datetime.datetime.now(bitis_tarihi.tzinfo) if bitis_tarihi.tzinfo else datetime.datetime.now()
                if su_an <= bitis_tarihi:
                    st.session_state.lisans_onaylandi = True
    except:
        pass


# =========================================================
# --- 3. GİRİŞ EKRANI ---
# =========================================================
if not st.session_state.lisans_onaylandi:
    st.title("🔐 VetMed AI - Kurumsal Giriş")
    
    try:
        ayarlar = supabase.table("sistem_ayarlari").select("*").eq("id", 1).execute().data[0]
        
        if not ayarlar["lisans_aktif"] and not ayarlar["kullanici_aktif"]:
            st.warning("⛔ Sistem girişleri geçici olarak kapatılmıştır.")
            st.stop()
            
        sekme_listesi = []
        if ayarlar["lisans_aktif"]: sekme_listesi.append("🔑 Lisans ile Giriş")
        if ayarlar["kullanici_aktif"]: sekme_listesi.append("👤 Kullanıcı Girişi")
        
        sekmeler = st.tabs(sekme_listesi)
        idx = 0
        
        # Lisans Sekmesi
        if ayarlar["lisans_aktif"]:
            with sekmeler[idx]:
                st.info("Geçerli bir lisans kodu giriniz.")
                girilen_kod = st.text_input("Lisans Kodu:", type="password", key="l_input")
                
                if st.button("Lisans ile Giriş Yap", key="btn_lisans_giris"):
                    res = supabase.table("lisanslar").select("*").eq("lisans_kodu", girilen_kod).execute()
                    if len(res.data) > 0:
                        l_data = res.data[0]
                        if not l_data["aktif"]:
                            st.error("❌ Lisans iptal edilmiş.")
                        elif l_data["lisans_tipi"] == "sureli":
                            bitis_tarihi = datetime.datetime.fromisoformat(l_data["son_kullanma_tarihi"])
                            su_an = datetime.datetime.now(bitis_tarihi.tzinfo) if bitis_tarihi.tzinfo else datetime.datetime.now()
                            if su_an > bitis_tarihi:
                                st.error("❌ Lisans süresi dolmuş!")
                            else:
                                st.success("✅ Süreli Lisans Doğrulandı!")
                                controller.set('sureli_lisans', girilen_kod, max_age=30*24*60*60)
                                time.sleep(0.5)
                                st.session_state.lisans_onaylandi = True
                                st.rerun()
                        elif l_data["lisans_tipi"] == "kullanim":
                            if l_data["kullanilan"] < l_data["max_kullanim"]:
                                supabase.table("lisanslar").update({
                                    "kullanilan": l_data["kullanilan"] + 1,
                                    "aktif": (l_data["kullanilan"] + 1) < l_data["max_kullanim"]
                                }).eq("lisans_kodu", girilen_kod).execute()
                                st.success("✅ Kullanımlık Lisans Doğrulandı!")
                                st.session_state.lisans_onaylandi = True
                                st.rerun()
                            else:
                                st.error("❌ Kullanım hakkı dolmuş!")
                    else:
                        st.error("❌ Geçersiz kod!")
            idx += 1
            
        # Kullanıcı Sekmesi
        if ayarlar["kullanici_aktif"]:
            with sekmeler[idx]:
                st.info("Kullanıcı adı ve şifrenizle giriş yapın.")
                k_adi = st.text_input("Kullanıcı Adı:", key="k_input")
                k_sifre = st.text_input("Şifre:", type="password", key="s_input")
                
                if st.button("Kullanıcı ile Giriş Yap", key="btn_kul_giris"):
                    res = supabase.table("kullanicilar").select("*").eq("kullanici_adi", k_adi).execute()
                    if len(res.data) > 0:
                        if res.data[0]["sifre"] == k_sifre:
                            st.success(f"✅ Hoş geldin, {k_adi}!")
                            st.session_state.lisans_onaylandi = True
                            st.rerun()
                        else:
                            st.error("❌ Hatalı şifre!")
                    else:
                        st.error("❌ Kullanıcı bulunamadı!")
                        
    except Exception as e:
        st.error(f"Bağlantı veya Yükleme Hatası: {e}")

    st.stop()


# =========================================================
# --- 4. ASIL ANA UYGULAMA (Giriş yapıldıktan sonra çalışır) ---
# =========================================================

import streamlit as st
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
import numpy as np
import requests
import base64
import os
import sqlite3
import hashlib

st.set_page_config(page_title="VetMed AI - Kurumsal Klinik Portal", layout="wide", page_icon="🏥")

# --- KESİN VE DOĞRULANMIŞ SQLITE VERİTABANI YOLU ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "vetmed_klinik.db")
def veritabani_baglanti_ve_kontrol():
    """Veritabanı dosyasını ve tablolarını garanti eder, kayıt sayısını döner."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vakalar';")
        tablo_varmi = cursor.fetchone()
        
        if not tablo_varmi:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vakalar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT, species TEXT, breed TEXT, age_years REAL, weight_kg REAL,
                    sex TEXT, neutered INTEGER, body_temperature_c REAL, heart_rate_bpm INTEGER, 
                    resp_rate_bpm INTEGER, crt_sec REAL, mucosa TEXT, hydration TEXT,
                    appetite_loss INTEGER, vomiting INTEGER, diarrhea INTEGER, lethargy INTEGER, 
                    cough INTEGER, dyspnea INTEGER, weight_loss INTEGER, polydipsia INTEGER, 
                    polyuria INTEGER, seizures INTEGER, bleeding_tendency INTEGER,
                    wbc_10e9_l REAL, rbc_10e12_l REAL, hgb_g_dl REAL, hct_pct REAL, plt_10e9_l REAL, 
                    lym_pct REAL, mon_pct REAL, eos_pct REAL, mcv_fl REAL, mchc_g_dl REAL,
                    reticulocyte_pct REAL, glucose_mg_dl REAL, urea_mg_dl REAL, creatinine_mg_dl REAL, 
                    alt_u_l REAL, ast_u_l REAL, alp_u_l REAL, gha_u_l REAL, total_bilirubin_mg_dl REAL, 
                    total_protein_g_dl REAL, albumin_g_dl REAL, globulin_g_dl REAL, amylase_u_l REAL, 
                    lipase_u_l REAL, potassium_mmol_l REAL, sodium_mmol_l REAL, chloride_mmol_l REAL, 
                    calcium_mg_dl REAL, phosphorus_mg_dl REAL, total_co2_mmol_l REAL, final_diagnosis TEXT
                )
            ''')
            
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kullanicilar (
                kullanici_adi TEXT PRIMARY KEY,
                sifre_hash TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hastaliklar (
                hastalik_adi TEXT PRIMARY KEY
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM kullanicilar")
        if cursor.fetchone()[0] == 0:
            admin_hash = hashlib.sha256("vetmed2026".encode()).hexdigest()
            hekim_hash = hashlib.sha256("klinik2026".encode()).hexdigest()
            cursor.execute("INSERT OR IGNORE INTO kullanicilar VALUES (?, ?)", ("admin", admin_hash))
            cursor.execute("INSERT OR IGNORE INTO kullanicilar VALUES (?, ?)", ("hekim", hekim_hash))
            
        varsayilan_tanilar = [
            'Sağlıklı/klinik olarak anlamlı patoloji yok', 'Böbrek hastalığı',
            'Hepatobiliyer hastalık', 'Gastrointestinal hastalık',
            'Solunum sistemi hastalığı', 'Endokrin/metabolik hastalık',
            'Enfeksiyöz hastalık', 'Ortopedik Hastalık'
        ]
        for t in varsayilan_tanilar:
            cursor.execute("INSERT OR IGNORE INTO hastaliklar VALUES (?)", (t,))
            
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM vakalar")
        sayi = cursor.fetchone()[0]
        conn.close()
        return sayi
    except Exception as e:
        return 0

aktif_vaka_sayisi = veritabani_baglanti_ve_kontrol()

# API anahtarını Streamlit Secrets üzerinden güvenle çekiyoruz
SECURE_GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

def guvenlik_dogrula(kullanici_input, sifre_input):
    if not kullanici_input or not sifre_input:
        return False
    kadi = kullanici_input.strip().lower()
    sifre_hash = hashlib.sha256(sifre_input.strip().encode()).hexdigest()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sifre_hash FROM kullanicilar WHERE kullanici_adi = ?", (kadi,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == sifre_hash:
            return True
    except:
        pass
    return False

def otomatik_hasta_id_uret():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT patient_id FROM vakalar ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            sayi_id = int(''.join(filter(str.isdigit, str(row[0]))))
            return f"P{sayi_id + 1}"
    except:
        pass
    return f"P{np.random.randint(5001, 9999)}"

# Kedi görseli ve çıkış butonu kaldırıldı, sadece menü kaldı
st.sidebar.title("🏥 VetMed Klinik Portal")
secilen_sayfa = st.sidebar.radio("Modül Seçimi:", [
    "🩺 AI Teşhis Asistanı", 
    "✂️ Pre-Op (Cerrahi Hazırlık)", 
    "📸 Çoklu Röntgen & Hibrit Konsültasyon",
    "📂 Detaylı Vaka Girişi & Güvenlik"
])
st.sidebar.divider()

if aktif_vaka_sayisi > 0:
    st.sidebar.success(f"🟢 DB Bağlantısı Sağlıklı\n📊 Aktif Vaka: {aktif_vaka_sayisi} adet")
else:
    st.sidebar.error(f"🔴 Veritabanı Boş!\nLütfen terminalde `python veri_uret.py` çalıştırın.")

# =====================================================================
# SAYFA 1: MAKSİMUM KLİNİK BULGULU AI TEŞHİS ASİSTANI
# =====================================================================
if secilen_sayfa == "🩺 AI Teşhis Asistanı":
    st.title("🧬 VetMed AI - Kapsamlı Klinik Teşhis Modülü")
    st.markdown("Fiziki muayene ve esnek 'Veri Yok' kontrollü genişletilmiş laboratuvar parametreleriyle karar destek sistemi.")

    @st.cache_resource
    def load_and_train_model_sql():
        if not os.path.exists(DB_PATH):
            return None, None, None, None, None, None, None, None
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT * FROM vakalar", conn)
            conn.close()
        except:
            return None, None, None, None, None, None, None, None
        
        if len(df) < 5:
            return None, None, None, None, None, None, None, None
            
        features = [
            'species_code', 'sex_code', 'age_years', 'weight_kg', 'neutered', 
            'body_temperature_c', 'heart_rate_bpm', 'resp_rate_bpm', 'crt_sec',
            'mucosa_code', 'hydration_code', 'appetite_loss', 'vomiting', 'diarrhea', 
            'lethargy', 'cough', 'dyspnea', 'weight_loss', 'polydipsia', 'polyuria', 
            'seizures', 'bleeding_tendency', 'wbc_10e9_l', 'rbc_10e12_l', 'hgb_g_dl', 
            'hct_pct', 'plt_10e9_l', 'lym_pct', 'mon_pct', 'eos_pct', 'mcv_fl', 'mchc_g_dl',
            'reticulocyte_pct', 'glucose_mg_dl', 'urea_mg_dl', 'creatinine_mg_dl', 'alt_u_l', 
            'ast_u_l', 'alp_u_l', 'gha_u_l', 'total_bilirubin_mg_dl', 'total_protein_g_dl', 
            'albumin_g_dl', 'globulin_g_dl', 'amylase_u_l', 'lipase_u_l', 'potassium_mmol_l', 
            'sodium_mmol_l', 'chloride_mmol_l', 'calcium_mg_dl', 'phosphorus_mg_dl', 'total_co2_mmol_l'
        ]
        
        le_species, le_sex, le_mucosa, le_hydration, le_tani = LabelEncoder(), LabelEncoder(), LabelEncoder(), LabelEncoder(), LabelEncoder()
        
        df['species_code'] = le_species.fit_transform(df['species'])
        df['sex_code'] = le_sex.fit_transform(df['sex'])
        df['mucosa_code'] = le_mucosa.fit_transform(df['mucosa'])
        df['hydration_code'] = le_hydration.fit_transform(df['hydration'])
        df['Tanı_Kodu'] = le_tani.fit_transform(df['final_diagnosis'])
        
        for col in features:
            if col not in df.columns:
                df[col] = 0.0
        
        X, y = df[features], df['Tanı_Kodu']
        model = xgb.XGBClassifier(eval_metric='mlogloss', random_state=42)
        model.fit(X, y)
        return model, le_species, le_sex, le_mucosa, le_hydration, le_tani, features, df

    model, le_species, le_sex, le_mucosa, le_hydration, le_tani, features_list, raw_df = load_and_train_model_sql()

    if model is not None:
        st.sidebar.header("📋 Hasta Klinik Parametreleri")
        
        with st.sidebar.expander("📌 Anamnez & Fizik Muayene", expanded=True):
            col_a, col_b = st.columns(2)
            tur_input = col_a.selectbox("Tür", le_species.classes_)
            cinsiyet_input = col_b.selectbox("Cinsiyet", le_sex.classes_)
            yas_input = st.number_input("Yaş (Yıl)", value=3.0, step=0.5)
            agirlik_input = st.number_input("Canlı Ağırlık (kg)", value=10.0, step=0.5)
            kisir_input = st.checkbox("Kısırlaştırılmış")
            
            ates_input = st.number_input("Vücut Sıcaklığı (°C)", value=38.5, step=0.1)
            nabiz_input = col_a.number_input("Nabız (bpm)", value=110, step=1)
            solunum_input = col_b.number_input("Solunum (Nfes/dk)", value=24, step=1)
            crt_input = st.number_input("CRT (Saniye)", value=1.5, step=0.5)
            
            mukosa_input = st.selectbox("Mukosa Rengi", le_mucosa.classes_)
            hidrasyon_input = st.selectbox("Dehidrasyon Durumu", le_hydration.classes_)

        with st.sidebar.expander("🩺 Semptom Kontrol Listesi"):
            s1, s2 = st.columns(2)
            istah = s1.checkbox("İştahsızlık")
            kusma = s2.checkbox("Kusma")
            ishal = s1.checkbox("İshal")
            halsizlik = s2.checkbox("Halsizlik / Letarji")
            oksuruk = s1.checkbox("Öksürük")
            nefes_darligi = s2.checkbox("Nefes Darlığı")
            kilo_kaybi = s1.checkbox("Kilo Kaybı")
            pd_inp = s2.checkbox("Polidipsi (Çok Su İçme)")
            pu_inp = s1.checkbox("Poliüri (Çok İdrar)")
            seizure_inp = s2.checkbox("Nöbet / Konvülsiyon")
            bleeding_inp = s1.checkbox("Kanama Eğilimi / Petişi")

        with st.sidebar.expander("🩸 Genişletilmiş Hemogram (CBC)"):
            hemogram_yok = st.checkbox("❌ Hemogram Verisi Yok (Bu testi es geç)")
            if not hemogram_yok:
                wbc_i = st.number_input("WBC (10^9/L)", value=10.0)
                rbc_i = st.number_input("RBC (10^12/L)", value=6.5)
                hgb_i = st.number_input("HGB (g/dL)", value=14.0)
                hct_i = st.number_input("HCT (%)", value=42.0)
                plt_i = st.number_input("PLT (10^9/L)", value=300.0)
                lym_i = st.number_input("LYM (%)", value=30.0)
                mon_i = st.number_input("MON (%)", value=5.0)
                eos_i = st.number_input("EOS (%)", value=3.0)
                mcv_i = st.number_input("MCV (fL)", value=70.0)
                mchc_i = st.number_input("MCHC (g/dL)", value=33.0)
                ret_i = st.number_input("Retikülosit (%)", value=1.0)
            else:
                wbc_i, rbc_i, hgb_i, hct_i, plt_i = 10.0, 6.5, 14.0, 42.0, 300.0
                lym_i, mon_i, eos_i, mcv_i, mchc_i, ret_i = 30.0, 5.0, 3.0, 70.0, 33.0, 1.0

        with st.sidebar.expander("🧪 Genişletilmiş Biyokimya & Enzimler"):
            biyokimya_yok = st.checkbox("❌ Biyokimya Verisi Yok (Bu testi es geç)")
            if not biyokimya_yok:
                glu_i = st.number_input("Glukoz (mg/dL)", value=100.0)
                urea_i = st.number_input("Üre/BUN (mg/dL)", value=25.0)
                crea_i = st.number_input("Kreatinin (mg/dL)", value=1.0)
                alt_i = st.number_input("ALT (U/L)", value=45.0)
                ast_i = st.number_input("AST (U/L)", value=35.0)
                alp_i = st.number_input("ALP (U/L)", value=60.0)
                gha_i = st.number_input("GGT (U/L)", value=5.0)
                tbili_i = st.number_input("Total Bilirubin", value=0.4)
                tp_i = st.number_input("Total Protein", value=6.8)
                alb_i = st.number_input("Albumin", value=3.4)
                glob_i = st.number_input("Globulin", value=3.4)
                amyl_i = st.number_input("Amilaz", value=500.0)
                lip_i = st.number_input("Lipaz", value=400.0)
            else:
                glu_i, urea_i, crea_i, alt_i, ast_i, alp_i, gha_i = 100.0, 25.0, 1.0, 45.0, 35.0, 60.0, 5.0
                tbili_i, tp_i, alb_i, glob_i, amyl_i, lip_i = 0.4, 6.8, 3.4, 3.4, 500.0, 400.0

        with st.sidebar.expander("⚡ Elektrolitler & Kan Gazı"):
            elektrolit_yok = st.checkbox("❌ Elektrolit Verisi Yok (Bu testi es geç)")
            if not elektrolit_yok:
                pot_i = st.number_input("Potasyum (K)", value=4.2)
                sod_i = st.number_input("Sodyum (Na)", value=145.0)
                chlor_i = st.number_input("Klor (Cl)", value=110.0)
                calc_i = st.number_input("Kalsiyum (Ca)", value=10.0)
                phos_i = st.number_input("Fosfor (P)", value=4.0)
                co2_i = st.number_input("Total CO2", value=20.0)
            else:
                pot_i, sod_i, chlor_i, calc_i, phos_i, co2_i = 4.2, 145.0, 110.0, 10.0, 4.0, 20.0

        if st.sidebar.button("🧠 Kapsamlı AI Teşhis Analizi Başlat", type="primary", use_container_width=True):
            st.subheader("🎯 Olası Tanı Sıralaması")
            
            input_array = [
                le_species.transform([tur_input])[0], le_sex.transform([cinsiyet_input])[0],
                yas_input, agirlik_input, 1 if kisir_input else 0, ates_input, nabiz_input,
                solunum_input, crt_input, le_mucosa.transform([mukosa_input])[0],
                le_hydration.transform([hidrasyon_input])[0], int(istah), int(kusma),
                int(ishal), int(halsizlik), int(oksuruk), int(nefes_darligi), int(kilo_kaybi),
                int(pd_inp), int(pu_inp), int(seizure_inp), int(bleeding_inp),
                wbc_i, rbc_i, hgb_i, hct_i, plt_i, lym_i, mon_i, eos_i, mcv_i, mchc_i, ret_i,
                glu_i, urea_i, crea_i, alt_i, ast_i, alp_i, gha_i, tbili_i, tp_i, alb_i, glob_i,
                amyl_i, lip_i, pot_i, sod_i, chlor_i, calc_i, phos_i, co2_i
            ]
            
            input_data = pd.DataFrame([input_array], columns=features_list)
            probs = model.predict_proba(input_data)[0]
            prob_df = pd.DataFrame({'Tanı': le_tani.classes_, 'Olasılık': probs}).sort_values(by='Olasılık', ascending=False)
            
            for i, row in prob_df.head(4).iterrows():
                st.write(f"**{row['Tanı']}**: %{row['Olasılık']*100:.1f}")
                st.progress(float(row['Olasılık']))
    else:
        st.warning(f"⚠️ Veritabanında yeterli vaka kaydı bulunamadı (Aktif kayıt: {aktif_vaka_sayisi}). Lütfen terminalde `python veri_uret.py` komutunu tekrar çalıştırın.")

# =====================================================================
# SAYFA 2: PROFESYONEL PRE-OP (CERRAHİ HAZIRLIK SİSTEMİ)
# =====================================================================
elif secilen_sayfa == "✂️ Pre-Op (Cerrahi Hazırlık)":
    st.title("✂️ Profesyonel Pre-Anestezik Cerrahi Hazırlık Sistemi")
    st.markdown("Operasyon öncesi risk skorlaması, organ rezervi doğrulaması ve acil stabilizasyon protokolü.")
    
    col_t1, col_t2, col_t3 = st.columns(3)
    tur_pre = col_t1.selectbox("Hasta Türü", ["Köpek", "Kedi"])
    irk_tipi = col_t2.checkbox("Brakisefalik Irk (Basık Yüzlü)")
    yas_pre = col_t3.number_input("Yaş (Yıl)", value=3.0, step=0.5)

    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🩸 Hematoloji & Koagülasyon")
        hct_pre = st.number_input("HCT (%)", value=40.0)
        plt_pre = st.number_input("PLT (Trombosit)", value=250.0)
        wbc_pre = st.number_input("WBC", value=10.0)

    with col2:
        st.subheader("🧪 Organ Fonksiyonları")
        alt_pre = st.number_input("ALT", value=40.0)
        bun_pre = st.number_input("BUN (Üre)", value=25.0)
        crea_pre = st.number_input("Kreatinin", value=1.0)
        alb_pre = st.number_input("Albumin", value=3.2)
        glu_pre = st.number_input("Glukoz", value=100.0)

    with col3:
        st.subheader("🫀 Fiziksel Durum")
        bcs_pre = st.selectbox("Vücut Kondisyonu (BCS)", ["İdeal", "Obez", "Kaşektik/Zayıf"])
        kalp_pre = st.selectbox("Oskültasyon", ["Normal", "Üfürüm / Aritmi Tespit Edildi"])
        durum_pre = st.selectbox("Klinik Stabilite", ["Stabil / Ayaktan", "Deprese / Acil", "Şok / Travma"])

    if st.button("✂️ Kapsamlı Cerrahi Risk ve Hazırlık Raporu Oluştur", type="primary", use_container_width=True):
        st.divider()
        st.subheader("📊 Anestezi Protokolü ve Risk Matrisi")
        
        risk = 0
        protokoller = []
        
        if irk_tipi:
            risk += 2
            protokoller.append("**Havayolu Yönetimi:** Brakisefalik sendrom riski. Ekstübasyon, yutkunma refleksi tam olarak geri geldikten sonra yapılmalı; entübasyon süresince oksijen desteği kesilmemelidir.")
        if kalp_pre == "Üfürüm / Aritmi Tespit Edildi":
            risk += 3
            protokoller.append("**Kardiyak Güvence:** Anestezi öncesi EKO/Kardiak değerlendirme önerilir. Pozitif inotropik etkili ve kalbi yormayan anestezi ajanları (örn. Etomidat) tercih edilmelidir.")
        if alb_pre < 2.5:
            risk += 2
            protokoller.append("**Doz Ayarlaması:** Hipoalbuminemi mevcut. Serbest ilaç fraksiyonu artacağı için anestezik madde dozları %30 oranında azaltılmalıdır.")
        if crea_pre > 2.0 or bun_pre > 50:
            risk += 2
            protokoller.append("**Sıvı Protokolü:** Renal yetersizlik riski. Operasyon boyunca İzotonik/RL yerine dengeli sıvı desteği ve tansiyon takibi zorunludur.")
        if hct_pre < 28:
            risk += 2
            protokoller.append("**Oksijenasyon:** Anemi tablosu var. Peroperatif %100 O2 sağlanmalı, kanama takibi sıkı yapılmalıdır.")

        if risk <= 1:
            st.success("✅ **ASA I / II - DÜŞÜK RİSK:** Standart anestezi protokolü uygulanabilir.")
        elif 2 <= risk <= 4:
            st.warning("⚠️ **ASA III - ORTA RİSK:** Hasta yakından izlenmeli, IV kateter açık tutulmalı ve ısı kaybı önlenmelidir.")
        else:
            st.error("🛑 **ASA IV / V - YÜKSEK RİSK:** Operasyon acil değilse ertelenmeli, hasta yoğun bakımda stabilize edilmelidir.")

        if protokoller:
            st.markdown("### 📋 Anestezi ve Cerrahi Öncesi Hazırlık Talimatları:")
            for p in protokoller:
                st.markdown(f"- {p}")

# =====================================================================
# SAYFA 3: ÇOKLU RÖNTGEN & KLİNİK KONSÜLTASYON (VERİ YOK KUTUCUKLU)
# =====================================================================
elif secilen_sayfa == "📸 Çoklu Röntgen & Hibrit Konsültasyon":
    st.title("📸 Çoklu Radyografi ve Hibrit Klinik Konsültasyon")
    st.markdown("Yüklenen röntgen görsellerini hastanın eksiksiz hemogram, biyokimya ve elektrolit parametreleriyle birlikte 'Veri Yok' esnekliğiyle analiz eder.")
    
    yuklenen_fotolar = st.file_uploader("Birden Fazla Röntgen Görüntüsü Yükleyin (JPG, PNG)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if yuklenen_fotolar:
        st.subheader("🖼️ Yüklenen Radyografiler Önizlemesi")
        cols = st.columns(len(yuklenen_fotolar) if len(yuklenen_fotolar) <= 4 else 4)
        for idx, foto in enumerate(yuklenen_fotolar):
            with cols[idx % 4]:
                st.image(foto, caption=f"Grafi {idx+1}", use_container_width=True)

    st.divider()
    with st.expander("📋 Hastanın Klinik ve Laboratuvar Parametreleri", expanded=True):
        rc1, rc2, rc3, rc4 = st.columns(4)
        r_tur = rc1.selectbox("Tür", ["Köpek", "Kedi"], key="r_tur")
        r_yas = rc2.number_input("Yaş (Yıl)", value=3.0, step=0.5, key="r_yas")
        r_ates = rc3.number_input("Vücut Isısı (°C)", value=38.5, step=0.1, key="r_ates")
        r_solunum = rc4.number_input("Solunum Sayısı (Nfes/dk)", value=24, key="r_solunum")
        
        st.markdown("--- **Hemogram (CBC)** ---")
        r_hemogram_yok = st.checkbox("❌ Hemogram Verisi Yok", key="r_hemogram_yok")
        if not r_hemogram_yok:
            hb1, hb2, hb3, hb4 = st.columns(4)
            r_wbc = hb1.number_input("WBC", value=10.0, key="r_wbc")
            r_rbc = hb2.number_input("RBC", value=6.5, key="r_rbc")
            r_hgb = hb3.number_input("HGB", value=14.0, key="r_hgb")
            r_hct = hb4.number_input("HCT (%)", value=42.0, key="r_hct")

            hb5, hb6, hb7, hb8 = st.columns(4)
            r_plt = hb5.number_input("PLT", value=300.0, key="r_plt")
            r_lym = hb6.number_input("LYM (%)", value=30.0, key="r_lym")
            r_mon = hb7.number_input("MON (%)", value=5.0, key="r_mon")
            r_eos = hb8.number_input("EOS (%)", value=3.0, key="r_eos")

            hb9, hb10, hb11, _ = st.columns(4)
            r_mcv = hb9.number_input("MCV", value=70.0, key="r_mcv")
            r_mchc = hb10.number_input("MCHC", value=33.0, key="r_mchc")
            r_ret = hb11.number_input("Retikülosit (%)", value=1.0, key="r_ret")
        else:
            r_wbc, r_rbc, r_hgb, r_hct, r_plt, r_lym, r_mon, r_eos, r_mcv, r_mchc, r_ret = "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok"

        st.markdown("--- **Biyokimya & Enzimler** ---")
        r_biyokimya_yok = st.checkbox("❌ Biyokimya Verisi Yok", key="r_biyokimya_yok")
        if not r_biyokimya_yok:
            bb1, bb2, bb3, bb4 = st.columns(4)
            r_glu = bb1.number_input("Glukoz", value=100.0, key="r_glu")
            r_urea = bb2.number_input("Üre (BUN)", value=25.0, key="r_urea")
            r_crea = bb3.number_input("Kreatinin", value=1.0, key="r_crea")
            r_alt = bb4.number_input("ALT", value=45.0, key="r_alt")

            bb5, bb6, bb7, bb8 = st.columns(4)
            r_ast = bb5.number_input("AST", value=35.0, key="r_ast")
            r_alp = bb6.number_input("ALP", value=60.0, key="r_alp")
            r_gha = bb7.number_input("GGT", value=5.0, key="r_gha")
            r_tbili = bb8.number_input("Total Bilirubin", value=0.4, key="r_tbili")

            bb9, bb10, bb11, bb12 = st.columns(4)
            r_tp = bb9.number_input("Total Protein", value=6.8, key="r_tp")
            r_alb = bb10.number_input("Albumin", value=3.4, key="r_alb")
            r_glob = bb11.number_input("Globulin", value=3.4, key="r_glob")
            r_amyl = bb12.number_input("Amilaz", value=500.0, key="r_amyl")

            bb13, _, _, _ = st.columns(4)
            r_lip = bb13.number_input("Lipaz", value=400.0, key="r_lip")
        else:
            r_glu, r_urea, r_crea, r_alt, r_ast, r_alp, r_gha, r_tbili, r_tp, r_alb, r_glob, r_amyl, r_lip = "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok"

        st.markdown("--- **Elektrolitler & Kan Gazı** ---")
        r_elektrolit_yok = st.checkbox("❌ Elektrolit Verisi Yok", key="r_elektrolit_yok")
        if not r_elektrolit_yok:
            eb1, eb2, eb3, eb4 = st.columns(4)
            r_pot = eb1.number_input("Potasyum (K)", value=4.2, key="r_pot")
            r_sod = eb2.number_input("Sodyum (Na)", value=145.0, key="r_sod")
            r_chlor = eb3.number_input("Klor (Cl)", value=110.0, key="r_chlor")
            r_calc = eb4.number_input("Kalsiyum (Ca)", value=10.0, key="r_calc")

            eb5, eb6, _, _ = st.columns(4)
            r_phos = eb5.number_input("Fosfor (P)", value=4.0, key="r_phos")
            r_co2 = eb6.number_input("Total CO2", value=20.0, key="r_co2")
        else:
            r_pot, r_sod, r_chlor, r_calc, r_phos, r_co2 = "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok", "Veri Yok"

        r_notlar = st.text_input("Ek Klinik Semptomlar / Notlar", value="Hibrit konsültasyon talep ediliyor.")

    analiz_baslat = st.button("🔍 Röntgen ve Lab Verilerini Eş Zamanlı Analiz Et", type="primary", use_container_width=True)

    if analiz_baslat:
        with st.spinner('Yapay zeka röntgen piksellerini ve laboratuvar verilerini sentezliyor...'):
            try:
                parts_list = []
                foto_bilgi = f"{len(yuklenen_fotolar)} adet röntgen görseli yüklenmiştir." if yuklenen_fotolar else "Röntgen görseli yüklenmemiştir."
                
                prompt = f"""
                Sen kıdemli bir veteriner dahiliye uzmanı, cerrah ve radyologsun. Sana bu hasta için {foto_bilgi} ve şu klinik/laboratuvar parametreler sunulmuştur:
                - Tür: {r_tur} | Yaş: {r_yas} | Ateş: {r_ates}°C | Solunum: {r_solunum}/dk
                - Hemogram: WBC={r_wbc}, RBC={r_rbc}, HGB={r_hgb}, HCT={r_hct}%, PLT={r_plt}, LYM={r_lym}%, MON={r_mon}%, EOS={r_eos}%, MCV={r_mcv}, MCHC={r_mchc}, Retikülosit={r_ret}%
                - Biyokimya: Glukoz={r_glu}, Üre={r_urea}, Kreatinin={r_crea}, ALT={r_alt}, AST={r_ast}, ALP={r_alp}, GGT={r_gha}, Total Bilirubin={r_tbili}, Total Protein={r_tp}, Albumin={r_alb}, Globulin={r_glob}, Amilaz={r_amyl}, Lipaz={r_lip}
                - Elektrolitler: Potasyum={r_pot}, Sodyum={r_sod}, Klor={r_chlor}, Kalsiyum={r_calc}, Fosfor={r_phos}, Total CO2={r_co2}
                - Ek Notlar: {r_notlar}

                Lütfen yüklenen görseller ile bu laboratuvar ve klinik bulgularını çapraz bağlayarak kapsamlı bir rapor sun. Şu formatı kullan:
                1. **Radyolojik ve Klinik Bulguların Sentezi**
                2. **Kesin Vaka Teşhisi**
                3. **Medikal / Cerrahi Tedavi ve Reçete Protokolü**
                """
                parts_list.append({"text": prompt})
                
                if yuklenen_fotolar:
                    for foto in yuklenen_fotolar:
                        encoded_img = base64.b64encode(foto.getvalue()).decode("utf-8")
                        parts_list.append({"inline_data": {"mime_type": foto.type, "data": encoded_img}})
                
                api_key_temiz = SECURE_GEMINI_API_KEY.strip()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key_temiz}"
                
                payload = {"contents": [{"parts": parts_list}]}
                response = requests.post(url, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    ai_metin = result['candidates'][0]['content']['parts'][0]['text']
                    st.divider()
                    st.subheader("📑 Konsültasyon Raporu")
                    st.write(ai_metin)
                else:
                    st.divider()
                    st.error(f"❌ API Bağlantı Hatası (Kod: {response.status_code})")
                    st.write("API Yanıtı:", response.text) # Hatanın detayını ekrana basar
            except Exception as e:
                st.error(f"Bağlantı hatası: {e}")

# =====================================================================
# SAYFA 4: DETAYLI VAKA GİRİŞİ, ÖZEL HASTALIK EKLEME, KULLANICI YÖNETİMİ & GÜVENLİK
# =====================================================================
elif secilen_sayfa == "📂 Detaylı Vaka Girişi & Güvenlik":
    st.title("📂 Kurumsal Vaka Kayıt, Hastalık Havuzu, Kullanıcı Yönetimi & Güvenlik")
    st.markdown("Sisteme yeni hekim/admin ekleyebilir, hastalık havuzunu yönetebilir ve SQLite veritabanına şifreli vaka kaydı yapabilirsiniz.")
    
    col_g1, col_g2 = st.columns(2)
    admin_kadi = col_g1.text_input("Yetkili Kullanıcı Adı", placeholder="Örn: admin")
    sifre_giris = col_g2.text_input("Kriptografik Erişim Şifresi", type="password")
    
    if guvenlik_dogrula(admin_kadi, sifre_giris):
        st.success(f"🔒 **Güvenlik Duvarı Doğrulandı:** Hoş geldiniz, *{admin_kadi}*. Kriptografik oturum aktif.")
        
        onerilen_id = otomatik_hasta_id_uret()
        
        try:
            conn_db = sqlite3.connect(DB_PATH)
            hastaliklar_df = pd.read_sql("SELECT hastalik_adi FROM hastaliklar", conn_db)
            conn_db.close()
            hastaliklar_listesi = hastaliklar_df['hastalik_adi'].tolist()
        except:
            hastaliklar_listesi = ['Böbrek hastalığı', 'Hepatobiliyer hastalık']

        with st.expander("🔐 Sistem İçinden Yeni Hekim / Kullanıcı Ekle", expanded=False):
            st.markdown("Sisteme yeni bir hekim veya yönetici tanımlayarak onların da güvenli şifreyle giriş yapabilmesini sağlayabilirsiniz.")
            uk1, uk2, uk3 = st.columns([2, 2, 1])
            yeni_kullanici_adi = uk1.text_input("Yeni Kullanıcı Adı", placeholder="Örn: vet_mehmet")
            yeni_kullanici_sifre = uk2.text_input("Yeni Kullanıcı Şifresi", type="password", placeholder="Güçlü bir şifre girin")
            
            if uk3.button("➕ Kullanıcı Ekle", use_container_width=True):
                k_adi_temiz = yeni_kullanici_adi.strip().lower()
                k_sifre_temiz = yeni_kullanici_sifre.strip()
                if k_adi_temiz and k_sifre_temiz:
                    sifre_hash_yeni = hashlib.sha256(k_sifre_temiz.encode()).hexdigest()
                    try:
                        conn_u = sqlite3.connect(DB_PATH)
                        curr_u = conn_u.cursor()
                        curr_u.execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash) VALUES (?, ?)", (k_adi_temiz, sifre_hash_yeni))
                        conn_u.commit()
                        conn_u.close()
                        st.success(f"✅ **'{k_adi_temiz}'** veritabanına başarıyla kaydedildi!")
                    except sqlite3.IntegrityError:
                        st.warning(f"⚠️ **'{k_adi_temiz}'** kullanıcı adı zaten veritabanında mevcut.")
                else:
                    st.error("Lütfen hem kullanıcı adı hem de şifre alanlarını doldurun.")

        st.divider()

        with st.container():
            st.subheader("📋 1. Hastalık Havuzuna Yeni Hastalık Ekle")
            col_h1, col_h2 = st.columns([3, 1])
            yeni_hastalik_input = col_h1.text_input("Sisteme Eklenecek Yeni Hastalık / Tanı Adı", placeholder="Örn: Parvovirütik Enterit vb.", key="yeni_hastalik_text")
            
            if col_h2.button("➕ Hastalığı Ekle", use_container_width=True):
                if yeni_hastalik_input.strip() != "":
                    tanim_adi = yeni_hastalik_input.strip()
                    try:
                        conn_h = sqlite3.connect(DB_PATH)
                        curr_h = conn_h.cursor()
                        curr_h.execute("INSERT INTO hastaliklar (hastalik_adi) VALUES (?)", (tanim_adi,))
                        conn_h.commit()
                        conn_h.close()
                        st.success(f"✅ **'{tanim_adi}'** veritabanı hastalık havuzuna eklendi!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.warning(f"⚠️ **'{tanim_adi}'** zaten veritabanında mevcut.")
                else:
                    st.error("Lütfen geçerli bir hastalık adı giriniz.")

        st.divider()

        with st.form("detayli_vaka_formu"):
            st.subheader("📋 2. Hasta Kimliği, Fiziksel ve Laboratuvar Bulguları")
            c1, c2, c3, c4 = st.columns(4)
            p_id = c1.text_input("Hasta ID (Otomatik Atandı)", value=onerilen_id, disabled=True)
            p_tur = c2.selectbox("Tür", ["Köpek", "Kedi"])
            p_irk = c3.text_input("Irk", value="Golden Retriever")
            p_yas = c4.number_input("Yaş", value=3.0, step=0.5)
            
            c5, c6, c7, c8 = st.columns(4)
            p_agirlik = c5.number_input("Ağırlık (kg)", value=15.0)
            p_cinsiyet = c6.selectbox("Cinsiyet", ["Dişi", "Erkek"])
            p_kısır = c7.selectbox("Kısırlaştırılmış", [0, 1], format_func=lambda x: "Evet" if x==1 else "Hayır")
            p_ates = c8.number_input("Vücut Isısı (°C)", value=38.5)
            
            c9, c10, c11, c12 = st.columns(4)
            p_hr = c9.number_input("Nabız (bpm)", value=110)
            p_rr = c10.number_input("Solunum (Nfes/dk)", value=24)
            p_crt = c11.number_input("CRT (sn)", value=1.5)
            p_mukosa = c12.selectbox("Mukosa", ['Pembe (Normal)', 'Soluk (Anemi)', 'Konjestif/Hiperemik', 'İkterik (Sarılık)'])

            st.markdown("--- **Hemogram & Biyokimya & Elektrolitler** ---")
            b1, b2, b3, b4 = st.columns(4)
            p_wbc = b1.number_input("WBC", value=10.0)
            p_rbc = b2.number_input("RBC", value=6.5)
            p_hgb = b3.number_input("HGB", value=14.0)
            p_hct = b4.number_input("HCT (%)", value=42.0)
            
            b5, b6, b7, b8 = st.columns(4)
            p_plt = b5.number_input("PLT", value=300.0)
            p_lym = b6.number_input("LYM (%)", value=30.0)
            p_mon = b7.number_input("MON (%)", value=5.0)
            p_eos = b8.number_input("EOS (%)", value=3.0)

            b9, b10, b11, b12 = st.columns(4)
            p_mcv = b9.number_input("MCV", value=70.0)
            p_mchc = b10.number_input("MCHC", value=33.0)
            p_ret = b11.number_input("Retikülosit (%)", value=1.0)
            p_glu = b12.number_input("Glukoz", value=100.0)

            b13, b14, b15, b16 = st.columns(4)
            p_urea = b13.number_input("Üre (BUN)", value=25.0)
            p_crea = b14.number_input("Kreatinin", value=1.0)
            p_alt = b15.number_input("ALT", value=45.0)
            p_ast = b16.number_input("AST", value=35.0)

            b17, b18, b19, b20 = st.columns(4)
            p_alp = b17.number_input("ALP", value=60.0)
            p_gha = b18.number_input("GGT", value=5.0)
            p_tbili = b19.number_input("Total Bilirubin", value=0.4)
            p_tp = b20.number_input("Total Protein", value=6.8)

            b21, b22, b23, b24 = st.columns(4)
            p_alb = b21.number_input("Albumin", value=3.4)
            p_glob = b22.number_input("Globulin", value=3.4)
            p_amyl = b23.number_input("Amilaz", value=500.0)
            p_lip = b24.number_input("Lipaz", value=400.0)

            b25, b26, b27, b28 = st.columns(4)
            p_pot = b25.number_input("Potasyum (K)", value=4.2)
            p_sod = b26.number_input("Sodyum (Na)", value=145.0)
            p_chlor = b27.number_input("Klor (Cl)", value=110.0)
            p_calc = b28.number_input("Kalsiyum (Ca)", value=10.0)

            b29, b30, _, _ = st.columns(4)
            p_phos = b29.number_input("Fosfor (P)", value=4.0)
            p_co2 = b30.number_input("Total CO2", value=20.0)

            st.subheader("🎯 3. Kesin Klinik Tanı Seçimi")
            p_tani = st.selectbox("Hastalık Havuzundan Kesin Tanı Seçin", hastaliklar_listesi)
            
            kaydet_btn = st.form_submit_button("🛡️ SQLite Veritabanına Şifreli Kayıt Yap", type="primary")
            
            if kaydet_btn:
                gercek_id = otomatik_hasta_id_uret()
                try:
                    conn_v = sqlite3.connect(DB_PATH)
                    yeni_kayit_df = pd.DataFrame([{
                        'patient_id': gercek_id, 'species': p_tur, 'breed': p_irk, 'age_years': p_yas, 'weight_kg': p_agirlik,
                        'sex': p_cinsiyet, 'neutered': p_kısır, 'body_temperature_c': p_ates, 'heart_rate_bpm': p_hr, 
                        'resp_rate_bpm': p_rr, 'crt_sec': p_crt, 'mucosa': p_mukosa, 'hydration': 'Normal (<5%)',
                        'appetite_loss': 0, 'vomiting': 0, 'diarrhea': 0, 'lethargy': 0, 'cough': 0, 'dyspnea': 0, 
                        'weight_loss': 0, 'polydipsia': 0, 'polyuria': 0, 'seizures': 0, 'bleeding_tendency': 0,
                        'wbc_10e9_l': p_wbc, 'rbc_10e12_l': p_rbc, 'hgb_g_dl': p_hgb, 'hct_pct': p_hct, 'plt_10e9_l': p_plt,
                        'lym_pct': p_lym, 'mon_pct': p_mon, 'eos_pct': p_eos, 'mcv_fl': p_mcv, 'mchc_g_dl': p_mchc,
                        'reticulocyte_pct': p_ret, 'glucose_mg_dl': p_glu, 'urea_mg_dl': p_urea, 'creatinine_mg_dl': p_crea,
                        'alt_u_l': p_alt, 'ast_u_l': p_ast, 'alp_u_l': p_alp, 'gha_u_l': p_gha, 'total_bilirubin_mg_dl': p_tbili,
                        'total_protein_g_dl': p_tp, 'albumin_g_dl': p_alb, 'globulin_g_dl': p_glob, 'amylase_u_l': p_amyl,
                        'lipase_u_l': p_lip, 'potassium_mmol_l': p_pot, 'sodium_mmol_l': p_sod, 'chloride_mmol_l': p_chlor,
                        'calcium_mg_dl': p_calc, 'phosphorus_mg_dl': p_phos, 'total_co2_mmol_l': p_co2, 'final_diagnosis': p_tani
                    }])
                    yeni_kayit_df.to_sql('vakalar', conn_v, if_exists='append', index=False)
                    conn_v.close()
                    st.success(f"🛡️ Veritabanına Kayıt Başarılı! Atanan Hasta ID: **{gercek_id}**")
                except Exception as ex:
                    st.error(f"Kayıt eklenirken hata oluştu: {ex}")
                
    elif sifre_giris != "" or admin_kadi != "":
        st.error("🚨 **Güvenlik İhlali / Hatalı Bilgi:** Kullanıcı adı veya şifre hatalı. Erişim reddedildi.")
    else:
        st.info("💡 Veritabanına veri eklemek ve kullanıcı yönetimine erişmek için yetkili kullanıcı adı (örn: `admin`) ve şifresini (`vetmed2026`) giriniz.")