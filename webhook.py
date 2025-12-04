from flask import Flask, request, jsonify, render_template
import os
import sqlite3
import uuid
from gtts import gTTS
from dotenv import load_dotenv

# --- GÜVENLİ IMPORTLAR ---
try:
    from google.cloud import dialogflow_v2 as dialogflow
    import google.generativeai as genai
except ImportError:
    dialogflow = None
    genai = None
    print("UYARI: Kütüphaneler eksik.")

app = Flask(__name__)

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'sirket_veritabani.db')
KEY_FILE = os.path.join(BASE_DIR, 'google_key.json')
AUDIO_FOLDER = os.path.join(BASE_DIR, 'static')
ENV_FILE = os.path.join(BASE_DIR, '.env')


load_dotenv(ENV_FILE)

error_counters = {}

PROJECT_ID = "yardimci-musteri-jdch"
if os.path.exists(KEY_FILE): os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_FILE

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("UYARI: .env dosyasında GEMINI_API_KEY bulunamadı!")

if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if not os.path.exists(AUDIO_FOLDER): os.makedirs(AUDIO_FOLDER)


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# --- GEMINI AI ---
def ask_gemini(user_input, data=None):
    if not genai: return "Yapay zeka modülü aktif değil."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')

        system_prompt = """
        GÖREV: 'Hızlı Kargo' firmasının yardımsever müşteri temsilcisisin.
        Duygusal zeka kullan. Veri varsa net cevap ver. Yalan söyleme.
        """

        if data:
            prompt = f"{system_prompt}\nKullanıcı: {user_input}\nSistem Verisi: {data}\nCevap:"
        else:
            prompt = f"{system_prompt}\nKullanıcı: {user_input}\nVeri: Yok\nCevap:"

        response = model.generate_content(prompt)
        return response.text.replace('*', '')
    except Exception as e:
        return "Sistemsel bir durum var."


# --- TTS ---
def metni_sese_cevir(text):
    filename = f"ses_{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(AUDIO_FOLDER, filename)
    try:
        tts = gTTS(text=text, lang='tr')
        tts.save(filepath)
        return f"/static/{filename}"
    except:
        return None


# --- DIALOGFLOW ---
def detect_intent_texts(project_id, session_id, text):
    if dialogflow is None: return None
    try:
        session_client = dialogflow.SessionsClient(transport="rest")
        session = session_client.session_path(project_id, session_id)
        text_input = dialogflow.types.TextInput(text=text, language_code="tr")
        query_input = dialogflow.types.QueryInput(text=text_input)
        return session_client.detect_intent(session=session, query_input=query_input).query_result
    except:
        return None


# --- DB ---
def kargo_bilgisi_getir(no):
    conn = get_db_connection()
    try:
        query = "SELECT durum_adi FROM kargo_takip JOIN hareket_cesitleri ON durum_id = id WHERE takip_no = ? OR siparis_no = ?"
        row = conn.execute(query, (no, no)).fetchone()
        return f"Kargo durumu: {row['durum_adi']}" if row else None
    except:
        return None
    finally:
        conn.close()


def fiyat_hesapla(desi, nereye):
    return f"{desi} desi, {nereye} için fiyat hesaplandı."


# --- ROUTES ---
@app.route('/')
def ana_sayfa():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    user_message = data.get('message', '')

    # Frontend'den gelen kalıcı Session ID'yi al
    session_id = data.get('session_id', str(uuid.uuid4()))

    try:
        ai_result = detect_intent_texts(PROJECT_ID, session_id, user_message)

        intent_name = None
        params = None
        dialogflow_answer = None

        if ai_result:
            intent_name = ai_result.intent.display_name
            params = ai_result.parameters
            dialogflow_answer = ai_result.fulfillment_text

        db_data = None
        gemini_context_note = None

        if intent_name == "Siparis_Sorgulama":
            no = None
            if params and params.fields.get('siparis_no'):
                val = params.fields['siparis_no']
                no = str(int(val.number_value)) if val.kind == 'number_value' else val.string_value

            if no:
                db_data = kargo_bilgisi_getir(no)

                if db_data:
                    error_counters[session_id] = 0
                else:
                    current_fails = error_counters.get(session_id, 0) + 1
                    error_counters[session_id] = current_fails

                    if current_fails >= 3:
                        gemini_context_note = """
                        DURUM: Kullanıcı 3 kez hatalı sipariş numarası girdi.
                        GÖREVİN: Ona "Kargo numaranızı bulamadım. Güvenlik gereği daha fazla sorgulama yapamıyorum. Lütfen size gelen SMS veya E-posta bildirimlerini kontrol edin." de.
                        """
                        error_counters[session_id] = 0
                    else:
                        gemini_context_note = f"""
                        DURUM: Kullanıcı hatalı numara girdi. (Hata Sayısı: {current_fails}/3).
                        GÖREVİN: "Numarayı bulamadım, yanlış yazmış olabilirsiniz. Lütfen kontrol edip tekrar yazın" de.
                        """

        elif intent_name == "Fiyat_Sorgulama":
            desi = params.fields.get('desi').number_value if params and params.fields.get('desi') else 1
            sehir = params.fields.get('sehir').string_value if params and params.fields.get('sehir') else 'uzak'
            db_data = fiyat_hesapla(desi, sehir)

        # Cevap Oluşturma
        if gemini_context_note:
            final_response = ask_gemini(user_message, gemini_context_note)
        else:
            final_response = ask_gemini(user_message, db_data)

        if not final_response and dialogflow_answer:
            final_response = dialogflow_answer
        if not final_response:
            final_response = "Bağlantı sorunu."

        audio_url = metni_sese_cevir(final_response)

        return jsonify({"response": final_response, "audio": audio_url})

    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({"response": "Hata oluştu.", "audio": None})


if __name__ == '__main__':
    app.run(debug=True)