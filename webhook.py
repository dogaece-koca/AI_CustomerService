from flask import Flask, request, jsonify, render_template
import os
import sqlite3
import uuid
import json
from gtts import gTTS
from dotenv import load_dotenv

# --- SADECE GEMINI VAR ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("UYARI: 'google-generativeai' kütüphanesi eksik.")

app = Flask(__name__)

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'sirket_veritabani.db')
KEY_FILE = os.path.join(BASE_DIR, 'google_key.json')
AUDIO_FOLDER = os.path.join(BASE_DIR, 'static')
ENV_FILE = os.path.join(BASE_DIR, '.env')

# .env Yükle
load_dotenv(ENV_FILE)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini Başlat
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Config Hatası: {e}")

if not os.path.exists(AUDIO_FOLDER): os.makedirs(AUDIO_FOLDER)


chat_histories = {}


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# --- VERİTABANI FONKSİYONLARI ---
def kargo_bilgisi_getir(no):
    conn = get_db_connection()
    try:
        query = "SELECT durum_adi FROM kargo_takip JOIN hareket_cesitleri ON durum_id = id WHERE takip_no = ? OR siparis_no = ?"
        row = conn.execute(query, (no, no)).fetchone()
        return f"Kargo Durumu: {row['durum_adi']}" if row else "Kayıt Bulunamadı"
    except:
        return "Veritabanı Hatası"
    finally:
        conn.close()


def fiyat_hesapla(desi, nereye):
    try:
        tutar = 35.0 + (float(desi) * 5.0)
        return f"{desi} desi, {nereye} bölgesi için tahmini tutar: {tutar} TL"
    except:
        return "Hesaplama Hatası"


# --- SES ---
def metni_sese_cevir(text):
    filename = f"ses_{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_FOLDER, filename)
    try:
        tts = gTTS(text=text, lang='tr')
        tts.save(filepath)
        return f"/static/{filename}"
    except:
        return None

def process_with_gemini(session_id, user_message):
    if not genai: return "Yapay zeka sistemi kapalı."

    model = genai.GenerativeModel('gemini-2.5-flash')

    history = chat_histories.get(session_id, [])

    system_prompt = """
    GÖREV: Sen 'Hızlı Kargo' firmasının yapay zeka asistanısın.

    TALİMATLAR:
    Kullanıcının mesajını analiz et. İki tür cevap verebilirsin:

    DURUM 1: Eğer kullanıcı veritabanı işlemi gerektiren bir şey sorarsa (Kargo durumu, Fiyat hesaplama):
    Aşağıdaki JSON formatında yanıt ver:
    {
        "type": "action",
        "function": "kargo_sorgula" (veya "fiyat_hesapla"),
        "parameters": { "no": "12345" } (veya { "desi": 5, "nereye": "Ankara" })
    }

    DURUM 2: Eğer kullanıcı sohbet ediyorsa, selam veriyorsa veya veri gerektirmeyen bir şey soruyorsa:
    Aşağıdaki JSON formatında yanıt ver:
    {
        "type": "chat",
        "reply": "Buraya doğal, nazik ve Türkçe cevabını yaz."
    }

    DURUM 3: Kullanıcı kargo soruyor ama numara vermediyse:
    {
        "type": "chat",
        "reply": "Hemen yardımcı olayım. Kargo takip numaranızı söyler misiniz?"
    }

    ÖNEMLİ: Cevabın SADECE JSON olmalı. Başka bir şey yazma.
    """

    full_prompt = f"{system_prompt}\n\nGEÇMİŞ SOHBET:\n{history}\n\nKULLANICI: {user_message}\nCEVAP (JSON):"

    try:
        result = model.generate_content(full_prompt)
        text_response = result.text.strip()

        if text_response.startswith("```json"):
            text_response = text_response.replace("```json", "").replace("```", "").strip()

        data = json.loads(text_response)

        if data.get("type") == "action":
            func = data.get("function")
            params = data.get("parameters", {})

            system_info = ""

            if func == "kargo_sorgula":
                no = params.get("no")
                if no:
                    db_result = kargo_bilgisi_getir(no)
                    system_info = f"Sistemden Gelen Bilgi: {db_result}"
                else:
                    system_info = "Hata: Numara anlaşılamadı."

            elif func == "fiyat_hesapla":
                desi = params.get("desi", 1)
                nereye = params.get("nereye", "Bilinmiyor")
                db_result = fiyat_hesapla(desi, nereye)
                system_info = f"Sistemden Gelen Bilgi: {db_result}"

            final_prompt = f"""
            GÖREV: Müşteri temsilcisi olarak kullanıcıya cevap ver.
            KULLANICI MESAJI: {user_message}
            SİSTEM BİLGİSİ: {system_info}

            Talimat: Sistem bilgisini kullanarak kullanıcıya nazik, doğal bir cevap yaz.
            """
            final_resp = model.generate_content(final_prompt).text

            chat_histories.setdefault(session_id, []).append(f"User: {user_message}")
            chat_histories[session_id].append(f"Bot: {final_resp}")

            return final_resp

        elif data.get("type") == "chat":
            reply = data.get("reply")
            chat_histories.setdefault(session_id, []).append(f"User: {user_message}")
            chat_histories[session_id].append(f"Bot: {reply}")
            return reply

    except Exception as e:
        print(f"Gemini Router Hatası: {e}")
        return "Şu an sistemlerimde bir yoğunluk var, lütfen tekrar deneyin."


# --- ROUTES ---
@app.route('/')
def ana_sayfa():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))

    # Gemini Router'a gönder (Dialogflow yok!)
    final_response = process_with_gemini(session_id, user_message)

    # Sese çevir
    audio_url = metni_sese_cevir(final_response)

    return jsonify({"response": final_response, "audio": audio_url})


if __name__ == '__main__':
    app.run(debug=True)