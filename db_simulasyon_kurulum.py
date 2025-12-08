import sqlite3
import os
from datetime import datetime

DB_NAME = "sirket_veritabani.db"

def create_simulation_db():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print("Eski veritabanı silindi, yenisi kuruluyor...")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. MÜŞTERİLER
    cursor.execute('''
        CREATE TABLE musteriler (
            musteri_id INTEGER PRIMARY KEY,
            ad_soyad TEXT,
            telefon TEXT,
            email TEXT
        )
    ''')
    musteriler = [
        (1001, 'Zeynep Yılmaz', '5551112233', 'zeynep@mail.com'),
        (1002, 'Can Demir', '5554445566', 'can@mail.com'),
        (1003, 'Elif Kaya', '5559998877', 'elif@mail.com')
    ]
    cursor.executemany('INSERT INTO musteriler VALUES (?,?,?,?)', musteriler)

    # 2. SABİTLER (Hareketler)
    cursor.execute('CREATE TABLE hareket_cesitleri (id INTEGER PRIMARY KEY, durum_adi TEXT)')
    cursor.executemany('INSERT INTO hareket_cesitleri VALUES (?,?)', [
        (1, 'HAZIRLANIYOR'),
        (2, 'TRANSFER'),
        (3, 'DAGITIMDA'),
        (4, 'TESLIM_EDILDI'),
        (8, 'IPTAL EDILDI')
    ])

    # 3. SİPARİŞLER (2 Adet Sipariş Ekliyoruz)
    cursor.execute('''
        CREATE TABLE siparisler (
            siparis_no TEXT PRIMARY KEY,
            gonderici_id INTEGER,
            alici_id INTEGER,
            urun_tanimi TEXT,
            FOREIGN KEY(gonderici_id) REFERENCES musteriler(musteri_id),
            FOREIGN KEY(alici_id) REFERENCES musteriler(musteri_id)
        )
    ''')
    siparisler = [
        ('123456', 1001, 1002, 'Kitap Kolisi'),  # Zeynep -> Can
        ('999999', 1003, 1001, 'Mobilya')  # Elif -> Zeynep (Teslim Edilmiş Testi)
    ]
    cursor.executemany('INSERT INTO siparisler VALUES (?,?,?,?)', siparisler)

    # 4. KARGO TAKİP (Durumları Farklı Ayarlıyoruz)
    cursor.execute('''
        CREATE TABLE kargo_takip (
            takip_no TEXT PRIMARY KEY,
            siparis_no TEXT,
            durum_id INTEGER,
            tahmini_teslim DATE,
            teslim_adresi TEXT,
            FOREIGN KEY(siparis_no) REFERENCES siparisler(siparis_no)
        )
    ''')
    bugun = datetime.now().strftime('%Y-%m-%d')

    kargolar = [
        # Durum 3: DAGITIMDA (İptal edilebilir, İade edilemez)
        ('123456', '123456', 3, bugun, 'Moda Cad. No:10 Kadıköy/İSTANBUL'),

        # Durum 4: TESLIM_EDILDI (İptal edilemez, İade edilebilir)
        ('999999', '999999', 4, bugun, 'Pınar Mah. No:5 Sarıyer/İSTANBUL')
    ]
    cursor.executemany('INSERT INTO kargo_takip VALUES (?,?,?,?,?)', kargolar)

    # 5. ŞİKAYETLER
    cursor.execute('''
        CREATE TABLE sikayetler (
            sikayet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            siparis_no TEXT,
            olusturan_musteri_id INTEGER,
            konu TEXT,
            durum TEXT DEFAULT 'ACIK',
            tarih DATE
        )
    ''')

    # 6. İADE TALEPLERİ
    cursor.execute('''
        CREATE TABLE iade_talepleri (
            iade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            siparis_no TEXT,
            olusturan_musteri_id INTEGER,
            sebep TEXT,
            durum TEXT DEFAULT 'ONAY_BEKLIYOR',
            tarih DATE,
            FOREIGN KEY(siparis_no) REFERENCES siparisler(siparis_no)
        )
    ''')

    # 7. HASAR BİLDİRİMLERİ
    cursor.execute('''
            CREATE TABLE hasar_bildirimleri (
                hasar_id INTEGER PRIMARY KEY AUTOINCREMENT,
                siparis_no TEXT,
                olusturan_musteri_id INTEGER,
                hasar_tipi TEXT, -- Kırık, Ezik, Islak vb.
                tazminat_durumu TEXT DEFAULT 'INCELEMEDE', -- INCELEMEDE, ONAYLANDI, RED
                tarih DATE,
                FOREIGN KEY(siparis_no) REFERENCES siparisler(siparis_no)
            )
        ''')

    # 8. ŞUBELER TABLOSU
    cursor.execute('''
            CREATE TABLE subeler (
                sube_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sube_adi TEXT,
                il TEXT,
                ilce TEXT,
                adres TEXT,
                telefon TEXT,
                calisma_saatleri TEXT
            )
        ''')

    # GÜNCELLENMİŞ ÖRNEK VERİLER (Pazar Bilgisi Eklendi)
    ornek_subeler = [
        ('Kadıköy Merkez', 'İstanbul', 'Kadıköy', 'Caferağa Mah. Moda Cad. No:10', '0216 333 44 55',
         'Hafta içi: 09:00-18:00, Cmt: 09:00-13:00, Pazar: Kapalı'),
        ('Beşiktaş Şube', 'İstanbul', 'Beşiktaş', 'Çırağan Cad. No:25', '0212 222 11 00',
         'Hafta içi: 09:00-18:00, Cmt: Kapalı, Pazar: Kapalı'),
        ('Çankaya Şube', 'Ankara', 'Çankaya', 'Atatürk Bulvarı No:50', '0312 444 55 66',
         'Hafta içi: 08:30-17:30, Cmt: 09:00-12:00, Pazar: Kapalı'),
        ('Alsancak Şube', 'İzmir', 'Konak', 'Kıbrıs Şehitleri Cad. No:15', '0232 555 66 77',
         'Hafta içi: 09:00-18:00, Cmt: 09:00-14:00, Pazar: 10:00-16:00 (Nöbetçi Şube)')
    ]

    cursor.executemany(
        'INSERT INTO subeler (sube_adi, il, ilce, adres, telefon, calisma_saatleri) VALUES (?,?,?,?,?,?)',
        ornek_subeler)

    conn.commit()
    conn.close()
    print("✅ Veritabanı GÜNCELLENDİ!")
    print("-> Sipariş 123456: DAĞITIMDA (İptal Testi İçin)")
    print("-> Sipariş 999999: TESLİM EDİLDİ (İade Testi İçin)")


if __name__ == "__main__":
    create_simulation_db()