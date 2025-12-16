from flask import Flask, request, jsonify, render_template
import os
import uuid
from gtts import gTTS

from dotenv import load_dotenv
from modules.gemini_ai import process_with_gemini


app = Flask(__name__)

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FOLDER = os.path.join(BASE_DIR, 'static')
ENV_FILE = os.path.join(BASE_DIR, '.env')

load_dotenv(ENV_FILE)

if not os.path.exists(AUDIO_FOLDER): os.makedirs(AUDIO_FOLDER)

user_sessions = {}

def metni_sese_cevir(text):
    filename = f"ses_{uuid.uuid4().hex}.mp3"
    try:
        if not text: return None
        gTTS(text=text, lang='tr').save(os.path.join(AUDIO_FOLDER, filename))
        return f"/static/{filename}"
    except Exception as e:
        print(f"Ses Hatası: {e}")
        return None


@app.route('/')
def ana_sayfa(): return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    msg = data.get('message', '')
    sid = data.get('session_id')

    if not sid: sid = "test_user"

    # Kullanıcı ilk kez geliyorsa hafızada yer aç
    if sid not in user_sessions:
        user_sessions[sid] = {
            'history': [],
            'verified': False,
            'tracking_no': None,
            'role': None,
            'user_name': None,
            'user_id': None,
            'pending_intent': None
        }

    resp = process_with_gemini(sid, msg, user_sessions)

    audio = metni_sese_cevir(resp)
    return jsonify({"response": resp, "audio": audio, "session_id": sid})

if __name__ == '__main__':
    app.run(debug=True)