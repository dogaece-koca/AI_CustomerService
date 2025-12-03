import os
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def ana_sayfa():
    return "Sistem ve Veritabanı Aktif! Dialogflow buraya bağlanabilir."

# Veritabanı dosyasının yolu (Setup dosyasının oluşturduğu dosya)
DB_PATH = os.path.join(os.path.dirname(__file__), 'sirket_veritabani.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Sütun isimleriyle erişim sağlar
    return conn


# --- FONKSİYON 1: DETAYLI KARGO SORGULAMA ---
def kargo_bilgisi_getir(takip_no_veya_siparis_no):
    conn = get_db_connection()

    # Yeni yapıya uygun JOIN sorgusu (Hareketler, Şubeler, Kuryeler, Durum Tanımları)
    query = """
        SELECT 
            k.takip_no, 
            m.ad_soyad AS musteri,
            hc.durum_adi,     -- ID yerine metin (Örn: DAGITIMDA)
            hc.aciklama,      -- Durum açıklaması
            s.sube_adi,       -- Hangi şubede?
            s.telefon AS sube_tel,
            kr.ad_soyad AS kurye, -- Hangi kuryede?
            kr.puan AS kurye_puan,
            k.tahmini_teslim
        FROM kargo_takip k
        JOIN siparisler sip ON k.siparis_no = sip.siparis_no
        JOIN musteriler m ON sip.musteri_id = m.musteri_id
        LEFT JOIN hareket_cesitleri hc ON k.durum_id = hc.id
        LEFT JOIN subeler s ON k.su_anki_sube_id = s.sube_id
        LEFT JOIN kuryeler kr ON k.atanan_kurye_id = kr.kurye_id
        WHERE k.takip_no = ? OR k.siparis_no = ?
    """

    row = conn.execute(query, (takip_no_veya_siparis_no, takip_no_veya_siparis_no)).fetchone()
    conn.close()

    if not row:
        return "Bu numaraya ait bir kayıt bulamadım. Lütfen sipariş veya takip numaranızı kontrol edin."

    # Duruma göre akıllı cevap oluşturma
    cevap = f"Sayın {row['musteri']}, kargonuzun durumu: {row['durum_adi']} ({row['aciklama']}).\n"

    if row['durum_adi'] == 'DAGITIMDA':
        cevap += f"Kargonuz şu an {row['kurye']} isimli kuryemizde (Puanı: {row['kurye_puan']}). Gün içinde teslim edilecek."
    elif row['durum_adi'] == 'SUBEDE':
        cevap += f"Kargonuz {row['sube_adi']} şubemizde bekliyor. İletişim: {row['sube_tel']}."
    elif row['durum_adi'] == 'TESLIM_EDILDI':
        cevap += "Teslimat başarıyla gerçekleşmiş görünüyor. Bizi tercih ettiğiniz için teşekkürler."

    return cevap


# --- FONKSİYON 2: DİNAMİK FİYAT HESAPLAMA ---
def fiyat_hesapla(desi, nereye_gidecek):
    conn = get_db_connection()

    # 1. Parametreleri Çek
    params = conn.execute("SELECT parametre_adi, deger FROM fiyat_parametreleri").fetchall()
    param_dict = {p['parametre_adi']: p['deger'] for p in params}

    conn.close()

    # Parametreleri değişkenlere ata
    baz_ucret = param_dict.get('baz_ucret', 30.0)
    birim_ucret = param_dict.get('desi_birim_ucret', 5.0)

    # 2. Çarpan Belirle (Basit mantık)
    # Dialogflow'dan 'sehir_ici', 'yakin', 'uzak' gelirse harika olur.
    # Gelmezse varsayılan olarak 'uzak' kabul edelim.
    if 'istanbul' in nereye_gidecek.lower() or 'içi' in nereye_gidecek.lower():
        carpan = param_dict.get('carpan_sehir_ici', 1.0)
    elif 'ankara' in nereye_gidecek.lower() or 'izmir' in nereye_gidecek.lower():
        carpan = param_dict.get('carpan_yakin_sehir', 1.5)
    else:
        carpan = param_dict.get('carpan_uzak_sehir', 2.2)

    # 3. Formül: (Baz + (Desi * Birim)) * Çarpan
    try:
        desi = float(desi)
        ham_fiyat = baz_ucret + (desi * birim_ucret)
        son_fiyat = ham_fiyat * carpan

        return f"{desi} desi için {nereye_gidecek} bölgesine tahmini kargo ücretiniz: {son_fiyat:.2f} TL'dir."
    except ValueError:
        return "Fiyat hesaplayabilmem için desiyi sayı olarak girmelisiniz."


@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)

    # Dialogflow'dan gelen veriler
    try:
        intent_name = req['queryResult']['intent']['displayName']
        parameters = req['queryResult']['parameters']
    except (KeyError, TypeError):
        return jsonify({"fulfillmentText": "Veri yapısı anlaşılamadı."})

    response_text = "Bunu tam anlayamadım."

    # --- INTENT YÖNLENDİRMESİ ---

    if intent_name == 'Siparis_Sorgulama':
        # Dialogflow parametresi: 'siparis_no'
        no = parameters.get('siparis_no')
        if no:
            response_text = kargo_bilgisi_getir(no)
        else:
            response_text = "Sipariş numaranızı alabilir miyim?"

    elif intent_name == 'Fiyat_Sorgulama':
        # Dialogflow parametreleri: 'desi' (number), 'sehir' (geo-city veya string)
        desi = parameters.get('desi')
        sehir = parameters.get('sehir', 'uzak')  # Şehir girilmezse uzak kabul et

        if desi:
            response_text = fiyat_hesapla(desi, str(sehir))
        else:
            response_text = "Fiyat hesaplamam için kargonun desi bilgisini söylemeniz gerekiyor."

    # Diğer intentler (Selamlama vb.) Dialogflow içinde statik halledilebilir
    # veya buraya eklenebilir.

    return jsonify({
        "fulfillmentText": response_text
    })


if __name__ == '__main__':
    app.run(debug=True)