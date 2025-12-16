import pandas as pd
import os
from sklearn.linear_model import LinearRegression
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

def teslimat_suresi_hesapla(mesafe, agirlik):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))  # modules klasörü
        base_dir = os.path.dirname(current_dir)  # Ana proje klasörü

        csv_path = os.path.join(base_dir, 'teslimat_verisi.csv')

        # Hata Ayıklama İçin: Konsola aradığı yolu yazdıralım
        print(f"🔍 ML Modülü CSV Arıyor: {csv_path}")

        if not os.path.exists(csv_path):
            return "HATA: 'teslimat_verisi.csv' dosyası bulunamadı."

        df = pd.read_csv(csv_path)

        df = df[df['Status'].isin(['Delivered', 'Delayed'])]

        df = df.dropna(subset=['Distance_miles', 'Weight_kg', 'Transit_Days'])

        X = df[['Distance_miles', 'Weight_kg']]
        y = df['Transit_Days']

        model = LinearRegression()
        model.fit(X, y)

        yeni_veri = pd.DataFrame({
            'Distance_miles': [float(mesafe)],
            'Weight_kg': [float(agirlik)]
        })

        tahmin = model.predict(yeni_veri)[0]

        if tahmin < 1.0: tahmin = 1.0

        return round(tahmin, 1)

    except Exception as e:
        return f"Model Hatası: {e}"


def duygu_analizi_yap(gelen_cumle):
    try:
        CSV_DOSYA_ADI = 'duygu_analizi.csv'
        SUTUN_YORUM = 'text'
        SUTUN_ETIKET = 'label'

        # 1. DOSYAYI BUL
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(current_dir)
        csv_path = os.path.join(base_dir, CSV_DOSYA_ADI)

        if not os.path.exists(csv_path):
            print(f"ML UYARI: '{CSV_DOSYA_ADI}' dosyası bulunamadı.")
            return "NÖTR (Veri Yok)", 0

        # 2. VERİYİ OKU
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
        except:
            # Türkçe karakter sorunu olursa diye
            df = pd.read_csv(csv_path, encoding='utf-16')

            # 3. VERİ TEMİZLİĞİ
        df = df.dropna(subset=[SUTUN_YORUM, SUTUN_ETIKET])
        df[SUTUN_YORUM] = df[SUTUN_YORUM].astype(str)

        # 4. MODELİ EĞİT
        vectorizer = CountVectorizer()
        X = vectorizer.fit_transform(df[SUTUN_YORUM])
        y = df[SUTUN_ETIKET]

        clf = MultinomialNB()
        clf.fit(X, y)

        # 5. TAHMİN YAP
        tahmin = clf.predict(vectorizer.transform([gelen_cumle]))[0]
        sonuc_str = str(tahmin)  # Büyük/küçük harf duyarlılığı için string yapalım

        # --- YENİ VERİ SETİNE GÖRE ETİKET KONTROLÜ ---
        # Senin veri setinde: "Olumlu", "Olumsuz", "Tarafsız" yazıyor.

        if sonuc_str in ["Olumlu", "Pozitif", "1", "positive", "iyi"]:
            return "MUTLU (POZİTİF)", 2
        elif sonuc_str in ["Olumsuz", "Negatif", "-1", "negative", "kötü"]:
            return "KIZGIN (NEGATİF)", -2
        else:
            # "Tarafsız" veya diğer durumlar
            return "NÖTR", 0

    except Exception as e:
        print(f"ML Hatası: {e}")
        return "NÖTR", 0