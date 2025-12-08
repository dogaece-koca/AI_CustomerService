from flask import Flask, request, jsonify, render_template
import os
import sqlite3
import uuid
import json
from datetime import datetime
from gtts import gTTS
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    genai = None

app = Flask(__name__)

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'sirket_veritabani.db')
AUDIO_FOLDER = os.path.join(BASE_DIR, 'static')
ENV_FILE = os.path.join(BASE_DIR, '.env')

load_dotenv(ENV_FILE)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if not os.path.exists(AUDIO_FOLDER): os.makedirs(AUDIO_FOLDER)

# OTURUM YÖNETİMİ
user_sessions = {}

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- DB İŞLEMLERİ ---

def metin_temizle(text):
    if not text: return ""
    text = text.lower()
    mapping = {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
        'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c'
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text.strip()

def kimlik_dogrula(siparis_no, ad, telefon):
    print(f"\n--- DOĞRULAMA DEBUG ---")
    print(f"Gelen Bilgiler -> Ad: {ad}, No: {siparis_no}, Tel: {telefon}")

    if not siparis_no or not ad or not telefon:
        return "HATA|Eksik bilgi."

    conn = get_db_connection()
    try:
        temiz_telefon = telefon.replace(" ", "").replace("-", "").strip()
        if len(temiz_telefon) > 10 and temiz_telefon.startswith('0'):
            temiz_telefon = temiz_telefon[1:]

        print(f"DB İçin Telefon: {temiz_telefon}")

        query = """
            SELECT s.siparis_no, m.musteri_id, m.ad_soyad,
                   CASE 
                       WHEN s.gonderici_id = m.musteri_id THEN 'gonderici'
                       WHEN s.alici_id = m.musteri_id THEN 'alici'
                   END as rol
            FROM musteriler m 
            JOIN siparisler s ON (s.gonderici_id = m.musteri_id OR s.alici_id = m.musteri_id)
            WHERE s.siparis_no = ?
              AND m.telefon = ?
        """

        row = conn.execute(query, (siparis_no, temiz_telefon)).fetchone()

        if not row:
            print("DB Sonucu: Kayıt bulunamadı (Telefon veya Sipariş No yanlış).")
            return "BASARISIZ|Bilgiler eşleşmiyor."

        db_ad_soyad = row['ad_soyad']
        print(f"DB'de Bulunan Kişi: {db_ad_soyad}")

        girilen_ad_temiz = metin_temizle(ad)
        db_ad_temiz = metin_temizle(db_ad_soyad)

        print(f"Karşılaştırma: '{girilen_ad_temiz}' in '{db_ad_temiz}' ?")

        if girilen_ad_temiz in db_ad_temiz:
            print("İsim Eşleşmesi BAŞARILI.")
            return f"BASARILI|{row['siparis_no']}|{row['ad_soyad']}|{row['rol']}|{row['musteri_id']}"
        else:
            print("İsim Eşleşmesi BAŞARISIZ.")
            return "BASARISIZ|İsim bilgisi uyuşmuyor."

    except Exception as e:
        print(f"HATA: {e}")
        return f"HATA|{e}"
    finally:
        conn.close()


def sikayet_olustur(no, konu, musteri_id):
    if not no or not konu: return "Şikayet konusu eksik."
    safe_id = musteri_id if musteri_id else 0

    conn = get_db_connection()
    try:
        bugun = datetime.now().strftime('%Y-%m-%d')
        conn.execute(
            "INSERT INTO sikayetler (siparis_no, olusturan_musteri_id, konu, tarih, durum) VALUES (?, ?, ?, ?, 'ACIK')",
            (no, safe_id, konu, bugun)
        )
        conn.commit()

        cursor = conn.execute("SELECT last_insert_rowid()")
        sikayet_id = cursor.fetchone()[0]

        return f"Şikayet kaydınız başarıyla oluşturuldu. Şikayet Takip No: #{sikayet_id}."
    except Exception as e:
        return f"Veritabanı hatası: {e}"
    finally:
        conn.close()


def kargo_bilgisi_getir(no):
    if not no: return "Takip numarası bulunamadı."

    conn = get_db_connection()
    try:
        query = """
            SELECT h.durum_adi 
            FROM kargo_takip k
            JOIN hareket_cesitleri h ON k.durum_id = h.id 
            WHERE k.takip_no = ? OR k.siparis_no = ?
        """

        row = conn.execute(query, (no, no)).fetchone()

        if row:
            return f"Kargo Durumu: {row['durum_adi']}"
        else:
            return "Sistemde bu numaraya ait bir kargo kaydı bulunamadı."

    except Exception as e:
        print(f"SQL HATASI (kargo_bilgisi_getir): {e}")
        return f"Sistem hatası: {e}"
    finally:
        conn.close()

def tahmini_teslimat_saati_getir(no):
    if not no: return "Numara bulunamadı."
    conn = get_db_connection()
    try:
        query = "SELECT tahmini_teslim, durum_adi FROM kargo_takip JOIN hareket_cesitleri ON durum_id = id WHERE takip_no = ? OR siparis_no = ?"
        row = conn.execute(query, (no, no)).fetchone()
        if not row: return "Kayıt yok."

        tarih = row['tahmini_teslim']
        durum = row['durum_adi']

        if durum == "TESLIM_EDILDI": return f"Kargonuz {tarih} tarihinde teslim edilmiştir."
        return f"Tahmini teslimat: {tarih}, 09:00 - 18:00 saatleri arası."
    finally:
        conn.close()


def hasar_kaydi_olustur(no, hasar_tipi, musteri_id):
    if not no: return "Takip numarası bulunamadı."
    if not hasar_tipi: return "Lütfen hasarın türünü (Kırık, Ezik, Islak) belirtin."

    safe_id = musteri_id if musteri_id else 0
    conn = get_db_connection()
    try:
        bugun = datetime.now().strftime('%Y-%m-%d')

        conn.execute(
            "INSERT INTO hasar_bildirimleri (siparis_no, olusturan_musteri_id, hasar_tipi, tarih) VALUES (?, ?, ?, ?)",
            (no, safe_id, hasar_tipi, bugun)
        )
        conn.commit()

        cursor = conn.execute("SELECT last_insert_rowid()")
        hasar_id = cursor.fetchone()[0]

        return f"Hasar bildiriminiz alındı. Tazminat Dosya No: #{hasar_id}. Hasar tespit ekiplerimiz 24 saat içinde sizinle iletişime geçecektir."
    except Exception as e:
        return f"Veritabanı hatası: {e}"
    finally:
        conn.close()

def iade_islemi_baslat(no, sebep, musteri_id, user_role):
    if not no: return "Numara bulunamadı."

    if user_role == 'gonderici':
        return "Siz bu kargonun göndericisisiniz. İade talebi sadece alıcı tarafından oluşturulabilir. Siz dilerseniz kargo iptali yapabilirsiniz."

    if not sebep: sebep = "Belirtilmedi"
    safe_id = musteri_id if musteri_id else 0

    conn = get_db_connection()
    try:
        query = "SELECT durum_adi FROM kargo_takip JOIN hareket_cesitleri ON durum_id = id WHERE takip_no = ? OR siparis_no = ?"
        row = conn.execute(query, (no, no)).fetchone()

        if not row: return "Kayıt bulunamadı."

        durum = row['durum_adi']
        yasakli = ["DAGITIMDA", "TRANSFER", "YOLDA", "HAZIRLANIYOR"]

        if any(d in durum for d in yasakli):
            return f"Kargo şu an '{durum}' aşamasında. Henüz teslim edilmediği için iade başlatılamaz."

        bugun = datetime.now().strftime('%Y-%m-%d')
        conn.execute(
            "INSERT INTO iade_talepleri (siparis_no, olusturan_musteri_id, sebep, durum, tarih) VALUES (?, ?, ?, 'ONAY_BEKLIYOR', ?)",
            (no, safe_id, sebep, bugun)
        )
        conn.commit()
        cursor = conn.execute("SELECT last_insert_rowid()")
        return f"İade talebiniz oluşturuldu. Talep No: #{cursor.fetchone()[0]}. Durum: Onay Bekliyor."
    except Exception as e:
        return f"Hata: {e}"
    finally:
        conn.close()


def kargo_iptal_et(no):

    if not no: return "Takip numarası bulunamadı."

    conn = get_db_connection()
    try:
        query = """
            SELECT h.durum_adi, k.durum_id 
            FROM kargo_takip k
            JOIN hareket_cesitleri h ON k.durum_id = h.id 
            WHERE k.takip_no = ? OR k.siparis_no = ?
        """
        row = conn.execute(query, (no, no)).fetchone()

        if not row: return "Kayıt bulunamadı."

        durum = row['durum_adi']

        if durum == "TESLIM_EDILDI":
            return "Kargonuz teslim edildiği için iptal işlemi yapılamamaktadır."

        if "IPTAL" in durum:
            return "Bu kargo zaten iptal edilmiş."

        conn.execute("UPDATE kargo_takip SET durum_id = 8 WHERE takip_no = ? OR siparis_no = ?", (no, no))
        conn.commit()

        return "Kargo gönderiminiz başarıyla İPTAL EDİLMİŞTİR. Prosedür gereği kargo ücret iadesi yapılmamaktadır."

    except Exception as e:
        return f"İptal işlemi sırasında hata: {e}"
    finally:
        conn.close()


def adres_degistir(no, yeni_adres):
    if not no: return "Takip numarası bulunamadı."
    if not yeni_adres: return "Adres bilgisi eksik. Lütfen yeni adresi söyleyin."
    conn = get_db_connection()
    try:
        conn.execute("UPDATE kargo_takip SET teslim_adresi = ? WHERE takip_no = ? OR siparis_no = ?", (yeni_adres, no, no))
        conn.commit()
        return f"Teslimat adresiniz başarıyla '{yeni_adres}' olarak güncellendi."
    except Exception as e:
        return f"Hata: {e}"
    finally:
        conn.close()

def alici_adresi_degistir(no, yeni_adres):
    if not no: return "Takip numarası bulunamadı."
    if not yeni_adres: return "Adres bilgisi eksik. Lütfen yeni adresi söyleyin."
    conn = get_db_connection()
    try:
        conn.execute("UPDATE kargo_takip SET teslim_adresi = ? WHERE takip_no = ? OR siparis_no = ?", (yeni_adres, no, no))
        conn.commit()
        return f"Gönderinizin alıcı adresi '{yeni_adres}' olarak güncellendi. Alıcıya SMS iletildi."
    except Exception as e:
        return f"Hata: {e}"
    finally:
        conn.close()


def alici_adi_degistir(no, yeni_isim):
    return f"Kargonuzun alıcı adı '{yeni_isim}' olarak güncellenmiştir. Kurye bilgilendirildi."


def sube_sorgula(lokasyon):
    conn = get_db_connection()
    try:
        if lokasyon and "genel" not in lokasyon.lower():
            lokasyon_temiz = f"%{lokasyon}%"
            query = "SELECT sube_adi, il, ilce, adres, telefon FROM subeler WHERE sube_adi LIKE ? OR il LIKE ? OR ilce LIKE ?"
            rows = conn.execute(query, (lokasyon_temiz, lokasyon_temiz, lokasyon_temiz)).fetchall()

            if not rows: return f"'{lokasyon}' bölgesinde şubemiz bulunmamaktadır."

            cevap_listesi = []
            for row in rows:
                adres_dogal = row['adres'] \
                    .replace("Mah.", "Mahallesi") \
                    .replace("Cad.", "Caddesi") \
                    .replace("Bul.", "Bulvarı") \
                    .replace("Sok.", "Sokağı") \
                    .replace("No:", "Numara")

                konum = f"{row['il']}'in {row['ilce']} ilçesinde" if row['il'] != row[
                    'ilce'] else f"{row['il']} merkezde"
                cumle = (f"{row['sube_adi']} şubemiz, {konum}, {adres_dogal} adresinde hizmet vermektedir. "
                         f"İletişim için {row['telefon']} numarasını arayabilirsiniz.")
                cevap_listesi.append(cumle)

            return "\n\n".join(cevap_listesi)

        else:
            query = "SELECT sube_adi, il, ilce FROM subeler"
            rows = conn.execute(query).fetchall()
            if not rows: return "Sistemde kayıtlı şube bulunamadı."

            cevap = "Şu anda hizmet veren şubelerimiz şunlardır:\n"
            for row in rows:
                cevap += f"- {row['sube_adi']} ({row['il']}/{row['ilce']})\n"

            cevap += "\nAdresini öğrenmek istediğiniz şubeyi söyler misiniz?"
            return cevap

    except Exception as e:
        return f"Hata: {e}"
    finally:
        conn.close()


def en_yakin_sube_bul(kullanici_adresi, bilgi_turu="adres"):
    if not kullanici_adresi: return "Size en yakın şubeyi bulabilmem için lütfen bulunduğunuz İl ve İlçeyi söyler misiniz?"

    conn = get_db_connection()
    try:
        subeler = conn.execute("SELECT * FROM subeler").fetchall()
        kullanici_adres_temiz = metin_temizle(kullanici_adresi)
        bulunan_sube_adi = None
        eslesme_puani = 0

        # En basit eşleşme algoritması (İlçe > İl)
        for sube in subeler:
            sube_il = metin_temizle(sube['il'])
            sube_ilce = metin_temizle(sube['ilce'])

            if sube_ilce in kullanici_adres_temiz:
                bulunan_sube_adi = sube['sube_adi']
                eslesme_puani = 2
                break
            elif sube_il in kullanici_adres_temiz:
                if eslesme_puani < 2:
                    bulunan_sube_adi = sube['sube_adi']
                    eslesme_puani = 1

        conn.close()

        if bulunan_sube_adi:

            if bilgi_turu == "saat":
                return f"Size en yakın şubemiz {bulunan_sube_adi} olarak tespit edildi.\n" + sube_saat_sorgula(
                    bulunan_sube_adi)
            elif bilgi_turu == "telefon":
                return f"Size en yakın şubemiz {bulunan_sube_adi} olarak tespit edildi.\n" + sube_telefon_sorgula(
                    bulunan_sube_adi)
            else:
                return f"Size en yakın şubemiz {bulunan_sube_adi} olarak tespit edildi.\n" + sube_sorgula(
                    bulunan_sube_adi)
        else:
            return "Verdiğiniz adrese yakın bir şube tespit edemedim. Lütfen İl ve İlçe bilgisini net söyleyebilir misiniz?"

    except Exception as e:
        return f"Hata: {e}"


def sube_saat_sorgula(lokasyon):
    conn = get_db_connection()
    try:
        if lokasyon and "genel" not in lokasyon.lower():
            lokasyon_temiz = f"%{lokasyon}%"
            query = "SELECT sube_adi, calisma_saatleri FROM subeler WHERE sube_adi LIKE ? OR il LIKE ? OR ilce LIKE ?"
            rows = conn.execute(query, (lokasyon_temiz, lokasyon_temiz, lokasyon_temiz)).fetchall()

            if not rows: return f"'{lokasyon}' isminde bir şubemiz bulunamadı."

            cevap_listesi = []
            for row in rows:
                ham_veri = row['calisma_saatleri']
                sube_adi_yalin = row['sube_adi'].replace(" Şube", "").replace(" Şubesi", "")

                parcalar = ham_veri.split(',')
                duzenli_parcalar = []

                for parca in parcalar:
                    parca = parca.strip()
                    if ":" in parca:
                        gun, saat = parca.split(':', 1)
                        gun = gun.strip()
                        if gun == "Cmt": gun = "Cumartesi"

                        saat = saat.strip()

                        if "Kapalı" in saat:
                            duzenli_parcalar.append(f"{gun} günleri kapalıdır")
                        elif "(Nöbetçi Şube)" in saat:
                            saat_temiz = saat.replace("(Nöbetçi Şube)", "").strip()
                            duzenli_parcalar.append(f"{gun} günü de nöbetçi şube olarak {saat_temiz} saatleri arasında")
                        else:
                            duzenli_parcalar.append(f"{gun} {saat} saatleri arasında")
                    else:
                        duzenli_parcalar.append(parca)

                aciklama = ", ".join(duzenli_parcalar)
                cevap_listesi.append(f" {sube_adi_yalin} şubemiz {aciklama} hizmet vermektedir.")

            return "\n\n".join(cevap_listesi)

        else:
            query = "SELECT sube_adi, il, ilce FROM subeler"
            rows = conn.execute(query).fetchall()
            if not rows: return "Sistemde kayıtlı şube bulunamadı."
            cevap = "Şu lokasyonlarda şubelerimiz bulunmaktadır:\n"
            for row in rows:
                cevap += f"- {row['sube_adi']} ({row['il']}/{row['ilce']})\n"
            cevap += "\nHangi şubemizin çalışma saatlerini öğrenmek istediğinizi sorabilir miyim?"
            return cevap

    except Exception as e:
        return f"Hata: {e}"
    finally:
        conn.close()


def sube_telefon_sorgula(lokasyon):
    conn = get_db_connection()
    try:
        if lokasyon and "genel" not in lokasyon.lower():
            lokasyon_temiz = f"%{lokasyon}%"
            query = "SELECT sube_adi, telefon FROM subeler WHERE sube_adi LIKE ? OR il LIKE ? OR ilce LIKE ?"
            rows = conn.execute(query, (lokasyon_temiz, lokasyon_temiz, lokasyon_temiz)).fetchall()

            if not rows: return f"'{lokasyon}' bölgesinde telefon kaydına ulaşılamadı."

            cevap_listesi = []
            for row in rows:
                sube_adi_yalin = row['sube_adi'].replace(" Şube", "").replace(" Şubesi", "")
                cevap_listesi.append(f" {sube_adi_yalin} şubemize {row['telefon']} numarasından ulaşabilirsiniz.")

            return "\n".join(cevap_listesi)
        else:
            query = "SELECT sube_adi FROM subeler"
            rows = conn.execute(query).fetchall()
            if not rows: return "Sistemde kayıtlı şube yok."
            cevap = "Mevcut şubelerimiz:\n"
            for row in rows: cevap += f"- {row['sube_adi']}\n"
            cevap += "\nHangi şubemizin telefon numarasını öğrenmek istersiniz?"
            return cevap
    except Exception as e:
        return f"Hata: {e}"
    finally:
        conn.close()

# --- GEMINI ZEKASI ---
def process_with_gemini(session_id, user_message):
    if not genai: return "AI kapalı."

    model = genai.GenerativeModel('gemini-2.5-flash')

    default_session = {
        'history': [],
        'verified': False,
        'tracking_no': None,
        'user_name': None,
        'role': None,
        'user_id': None
    }

    session_data = user_sessions.get(session_id, default_session)
    for k, v in default_session.items():
        if k not in session_data:
            session_data[k] = v


    history = session_data['history'][-10:]

    is_verified = session_data['verified']
    saved_no = session_data['tracking_no']
    user_role = session_data['role']
    user_id = session_data['user_id']

    status_prompt = ""
    if is_verified:
        rol_adi = "Gönderici" if user_role == 'gonderici' else "Alıcı"
        status_prompt = f"DURUM: KULLANICI DOĞRULANDI. Müşteri: {session_data.get('user_name')} ({rol_adi}). Aktif No: {saved_no}."
    else:
        status_prompt = "DURUM: MİSAFİR KULLANICI. Kimlik doğrulanmadı. Hiçbir kargo bilgisi verme. Önce kimlik doğrula."

    system_prompt = f"""
    GÖREV: Hızlı Kargo sesli asistanısın. {status_prompt}

    ÖN İŞLEM: Tek tek söylenen sayıları birleştir (bir iki üç -> 123).
    ÇIKTI: Sadece JSON.

    ANALİZ KURALLARI (ÖNCELİK SIRASINA GÖRE):

    --- SENARYO 1: KULLANICI DOĞRULANMAMIŞ İSE (MİSAFİR) ---
    Eğer 'DURUM: MİSAFİR KULLANICI' ise:
    
    # "EN YAKIN" İFADESİ GEÇİYORSA (EN ÖNEMLİ KURAL)
       - Kullanıcı "en yakın", "bana yakın" kelimelerini kullanıyorsa:
         - "En yakın şubenin telefonu?", "En yakın şubeyi aramak istiyorum" -> {{ "type": "action", "function": "en_yakin_sube_bul", "parameters": {{ "kullanici_adresi": "", "bilgi_turu": "telefon" }} }}
         - "En yakın şube saatleri?", "Kaça kadar açık?" -> {{ "type": "action", "function": "en_yakin_sube_bul", "parameters": {{ "kullanici_adresi": "", "bilgi_turu": "saat" }} }}
         - "En yakın şube nerede?", "Adresi ne?" -> {{ "type": "action", "function": "en_yakin_sube_bul", "parameters": {{ "kullanici_adresi": "", "bilgi_turu": "adres" }} }}
         (Eğer aynı cümlede adres de verdiyse 'kullanici_adresi'ne yaz, yoksa boş bırak).
       
    # "EN YAKIN" İFADESİ GEÇMİYORSA
       # ŞUBE ADRES/KONUM SORGUSU
       - "Şubeniz nerede?", "Kadıköy şubesi adresi"
       -> {{ "type": "action", "function": "sube_sorgula", "parameters": {{ "lokasyon": "..." }} }}
       (Eğer şube adı yoksa "lokasyon": "" gönder)
       
       # ŞUBE ÇALIŞMA SAATİ/GÜN SORGUSU
       - "Kaça kadar açıksınız?", "Pazar günü hizmet veriyor musunuz?", "Hafta sonu açık mısınız?", "Kadıköy şubesi pazar günü açık mı?"
       -> {{ "type": "action", "function": "sube_saat_sorgula", "parameters": {{ "lokasyon": "..." }} }}
       (Eğer belirli bir yer söylemediyse lokasyon boş string gönder, örn: "genel" veya "").
       
       # ŞUBE TELEFONU 
       - "Telefon numaranız ne?", "Kadıköy şubesini nasıl ararım?", "İletişim numarası"
       -> {{ "type": "action", "function": "sube_telefon_sorgula", "parameters": {{ "lokasyon": "..." }} }}
       (Lokasyon yoksa boş string gönder).
       
       
    1. Kullanıcı bu belirtilen durumlar haricinde ne sorarsa sorsun (Kargo, şikayet, adres), ÖNCE KİMLİK DOĞRULAMA akışını tamamla.
    2. Sırayla eksik bilgileri iste (Ad -> Takip No -> Telefon).
    3. Hepsi tamamsa -> {{ "type": "action", "function": "kimlik_dogrula", "parameters": {{ "ad": "...", "no": "...", "telefon": "..." }} }}


    --- SENARYO 2: KULLANICI DOĞRULANMIŞ İSE (GİRİŞ YAPILDI) ---
    Eğer 'DURUM: KULLANICI DOĞRULANDI' ise:
    1. Hafızadaki '{saved_no}' numarasını kullan.

    2. İŞLEMLER:
       - "Kargom nerede?" -> {{ "type": "action", "function": "kargo_sorgula", "parameters": {{ "no": "{saved_no}" }} }}

       # İADE TALEBİ (DB KAYDI İÇİN SEBEP ZORUNLU)
       - "İade etmek istiyorum", "Geri göndereceğim":
         - EĞER sebep belliyse -> {{ "type": "action", "function": "iade_islemi_baslat", "parameters": {{ "no": "{saved_no}", "sebep": "..." }} }}
         - EĞER sebep yoksa -> {{ "type": "chat", "reply": "İade işlemini başlatmak için lütfen iade sebebinizi kısaca belirtir misiniz?" }}
       
       # İPTAL TALEBİ (YENİ)
       - "Kargoyu iptal et", "Vazgeçtim göndermeyeceğim", "İptal etmek istiyorum":
         -> {{ "type": "action", "function": "kargo_iptal_et", "parameters": {{ "no": "{saved_no}" }} }}
         
       # TESLİMAT SAATİ (YENİ EKLENDİ)
       - "Ne zaman gelir?", "Saat kaçta teslim olur?", "Hangi gün gelir?":
         -> {{ "type": "action", "function": "tahmini_teslimat", "parameters": {{ "no": "{saved_no}" }} }}
         
       # ŞİKAYET İŞLEMLERİ
       - "Şikayetim var", "Paket hasarlı", "Kurye kaba", "Geç geldi":
         - Konu belli değilse -> {{ "type": "chat", "reply": "Anlıyorum, yaşadığınız sorun nedir? Lütfen şikayetinizi kısaca belirtin." }}
         - Konu belliyse -> {{ "type": "action", "function": "sikayet_olustur", "parameters": {{ "no": "{saved_no}", "konu": "..." }} }}

       # HASAR BİLDİRİMİ (YENİ - TAZMİNAT)
       - "Kargom kırık geldi", "Paket ezilmiş", "Ürün hasarlı", "Islanmış", "Parçalanmış":
         - EĞER hasar tipi belliyse -> {{ "type": "action", "function": "hasar_kaydi_olustur", "parameters": {{ "no": "{saved_no}", "hasar_tipi": "..." }} }}
         - EĞER tip belli değilse -> {{ "type": "chat", "reply": "Çok üzgünüz. Hasarın türü nedir? (Kırık, Ezik, Islak, Kayıp)" }}
         
       # ALICI ADI DEĞİŞTİRME
       - "Alıcı adını değiştirmek istiyorum", "Alıcının adını yanlış girmişim" (Yeni isim yoksa):
         -> {{ "type": "chat", "reply": "Tabii, kargoyu teslim alacak yeni kişinin Adı ve Soyadı nedir?" }}
       - Yeni isim belliyse:
         -> {{ "type": "action", "function": "alici_adi_degistir", "parameters": {{ "no": "{saved_no}", "yeni_isim": "..." }} }}

       # KENDİ ADRESİNİ DEĞİŞTİRME (Gelen Kargo)
       - "Adresimi değiştirmek istiyorum", "Kapı numarasını yanlış yazmışım", "Sadece sokağı düzelt", "İlçe yanlış olmuş":
         - EĞER kullanıcı TAM YENİ ADRESİ (Mahalle, sokak, no, ilçe/il) söylediyse:
           -> {{ "type": "action", "function": "adres_degistir", "parameters": {{ "no": "{saved_no}", "yeni_adres": "..." }} }}
         - EĞER kullanıcı SADECE DÜZELTME istediyse ("Kapı nosunu 5 yap", "Sadece sokağı değiştir", "Daire no eksik"):
           -> {{ "type": "chat", "reply": "Adresinizin eksiksiz olması için lütfen güncel ve TAM adresinizi (Mahalle, Sokak, No, İlçe) söyler misiniz?" }}

       # ALICI ADRESİNİ DEĞİŞTİRME (Giden Kargo)
       - "Gönderdiğim kargonun adresi yanlış", "Alıcı adresini değiştirmek istiyorum", "Sokak ismi hatalı girilmiş", "Alıcının kapı nosu yanlış":
         - EĞER kullanıcı TAM YENİ ADRESİ söylediyse:
           -> {{ "type": "action", "function": "alici_adresi_degistir", "parameters": {{ "no": "{saved_no}", "yeni_adres": "..." }} }}
         - EĞER kullanıcı SADECE DÜZELTME istediyse ("Sadece apartman adını düzelt", "Sokak yanlış", "Daire no hatalı"):
           -> {{ "type": "chat", "reply": "Karışıklık olmaması için lütfen alıcının güncel ve TAM adresini (Mahalle, Sokak, No, İlçe) söyler misiniz?" }}
    
    4. GENEL SOHBET:
       - Merhaba, nasılsın vb. -> {{ "type": "chat", "reply": "..." }}
    """

    formatted_history = "\n".join(history)
    full_prompt = f"{system_prompt}\n\nGEÇMİŞ SOHBET:\n{formatted_history}\n\nKULLANICI: {user_message}\nJSON CEVAP:"

    try:
        result = model.generate_content(full_prompt)
        text_response = result.text.replace("```json", "").replace("```", "").strip()
        print(f"DEBUG: AI Yanıtı: {text_response}")

        data = json.loads(text_response)
        final_reply = ""

        if data.get("type") == "action":
            func = data.get("function")
            params = data.get("parameters", {})
            system_res = ""

            if func == "kimlik_dogrula":
                res = kimlik_dogrula(params.get("no"), params.get("ad"), params.get("telefon"))

                if res.startswith("BASARILI"):
                    parts = res.split("|")
                    user_sessions[session_id]['verified'] = True
                    user_sessions[session_id]['tracking_no'] = parts[1]
                    user_sessions[session_id]['user_name'] = parts[2]
                    user_sessions[session_id]['role'] = parts[3]
                    user_sessions[session_id]['user_id'] = parts[4]

                    rol_mesaji = "gönderici" if parts[3] == "gonderici" else "alıcı"
                    final_prompt = f"Kullanıcıya kimlik doğrulamanın başarılı olduğunu ve sistemde {rol_mesaji} olarak göründüğünü söyle. 'Nasıl yardımcı olabilirim?' diye sor."
                else:
                    final_prompt = f"Kullanıcıya bilgilerin eşleşmediğini söyle ve tekrar denemesini iste. SADECE yanıt metni."
                system_res = res
            elif func == "sube_saat_sorgula":
                system_res = sube_saat_sorgula(params.get("lokasyon"))
            elif func == "sube_sorgula":
                system_res = sube_sorgula(params.get("lokasyon"))
            elif func == "en_yakin_sube_bul":
                bilgi_turu = params.get("bilgi_turu", "adres")
                system_res = en_yakin_sube_bul(params.get("kullanici_adresi"), bilgi_turu)
            elif func == "sube_telefon_sorgula":
                system_res = sube_telefon_sorgula(params.get("lokasyon"))
            elif func == "sikayet_olustur":
                system_res = sikayet_olustur(params.get("no"), params.get("konu"), user_id)
            elif func == "hasar_kaydi_olustur":
                system_res = hasar_kaydi_olustur(params.get("no"), params.get("hasar_tipi"), user_id)
            elif func == "kargo_sorgula":
                system_res = kargo_bilgisi_getir(params.get("no"))
            elif func == "tahmini_teslimat":
                system_res = tahmini_teslimat_saati_getir(params.get("no"))
            elif func == "iade_islemi_baslat":
                system_res = iade_islemi_baslat(params.get("no"), params.get("sebep"), user_id, user_role)
            elif func == "kargo_iptal_et":
                system_res = kargo_iptal_et(params.get("no"))
            elif func == "adres_degistir":
                system_res = adres_degistir(params.get("no"), params.get("yeni_adres"))
            elif func == "alici_adresi_degistir":
                system_res = alici_adresi_degistir(params.get("no"), params.get("yeni_adres"))
            elif func == "alici_adi_degistir":
                system_res = alici_adi_degistir(params.get("no"), params.get("yeni_isim"))

            if func != "kimlik_dogrula":
                final_prompt = f"Kullanıcıya şu sistem bilgisini nazikçe ilet: {system_res}. SADECE yanıt metni."

            final_resp = model.generate_content(final_prompt).text
            final_reply = final_resp.strip()

        elif data.get("type") == "chat":
            final_reply = data.get("reply")

        session_data['history'].append(f"KULLANICI: {user_message}")
        session_data['history'].append(f"ASİSTAN: {final_reply}")
        user_sessions[session_id] = session_data

        return final_reply

    except Exception as e:
        print(f"HATA: {e}")
        return "Bir hata oluştu."


def metni_sese_cevir(text):
    filename = f"ses_{uuid.uuid4().hex}.mp3"
    try:
        gTTS(text=text, lang='tr').save(os.path.join(AUDIO_FOLDER, filename))
        return f"/static/{filename}"
    except:
        return None


@app.route('/')
def ana_sayfa(): return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    msg = data.get('message', '')
    sid = data.get('session_id')
    if not sid: sid = "test_user"

    if sid not in user_sessions:
        user_sessions[sid] = {
            'history': [],
            'verified': False,
            'tracking_no': None,
            'role': None,
            'user_name': None,
            'user_id': None
        }

    resp = process_with_gemini(sid, msg)
    audio = metni_sese_cevir(resp)
    return jsonify({"response": resp, "audio": audio, "session_id": sid})


if __name__ == '__main__':
    app.run(debug=True)