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

    # ---------------------------------------------------------
    # 1. ŞUBELER
    # ---------------------------------------------------------
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

    ornek_subeler = [
        ('Kadıköy Merkez', 'İstanbul', 'Kadıköy', 'Caferağa Mah. Moda Cad. No:10', '0216 333 44 55', 'Hafta içi: 09:00-18:00, Cmt: 09:00-13:00, Pazar: Kapalı'),
        ('Beşiktaş Şube', 'İstanbul', 'Beşiktaş', 'Çırağan Cad. No:25', '0212 222 11 00', 'Hafta içi: 09:00-18:00, Cmt: Kapalı, Pazar: Kapalı'),
        ('Çankaya Şube', 'Ankara', 'Çankaya', 'Atatürk Bulvarı No:50', '0312 444 55 66', 'Hafta içi: 08:30-17:30, Cmt: 09:00-12:00, Pazar: Kapalı'),
        ('Alsancak Şube', 'İzmir', 'Konak', 'Kıbrıs Şehitleri Cad. No:15', '0232 555 66 77', 'Hafta içi: 09:00-18:00, Cmt: 09:00-14:00, Pazar: 10:00-16:00 (Nöbetçi Şube)')
    ]
    cursor.executemany('INSERT INTO subeler (sube_adi, il, ilce, adres, telefon, calisma_saatleri) VALUES (?,?,?,?,?,?)', ornek_subeler)

    # ---------------------------------------------------------
    # 2. KURYELER
    # ---------------------------------------------------------
    cursor.execute('''
        CREATE TABLE kuryeler (
            kurye_id INTEGER PRIMARY KEY,
            ad_soyad TEXT,
            bagli_sube_id INTEGER,
            telefon TEXT,
            puan REAL,
            FOREIGN KEY(bagli_sube_id) REFERENCES subeler(sube_id)
        )
    ''')
    kuryeler = [
        (201, 'Ahmet Hızlı', 1, '0532 111 22 33', 4.8), 
        (202, 'Mehmet Çevik', 2, '0533 444 55 66', 4.5), 
        (203, 'Ayşe Seri', 4, '0544 777 88 99', 4.9), 
        (204, 'Burak Yıldırım', 3, '0555 000 11 22', 4.2)
    ]
    cursor.executemany('INSERT INTO kuryeler VALUES (?,?,?,?,?)', kuryeler)

    # ---------------------------------------------------------
    # 3. MÜŞTERİLER (37. Niyet için bildirim_tercihi kolonu eklendi)
    # ---------------------------------------------------------
    cursor.execute('''
        CREATE TABLE musteriler (
            musteri_id INTEGER PRIMARY KEY,
            ad_soyad TEXT,
            telefon TEXT,
            email TEXT,
            bildirim_tercihi TEXT DEFAULT 'SMS'
        )
    ''')
    musteriler = [
        (1001, 'Zeynep Yılmaz', '5551112233', 'zeynep@mail.com', 'SMS'),
        (1002, 'Can Demir', '5554445566', 'can@mail.com', 'SMS'),
        (1003, 'Elif Kaya', '5559998877', 'elif@mail.com', 'E-posta'),
        (1004, 'Doğa Ece Koca', '5415998046', 'doga@mail.com', 'SMS'),
        (9999, 'Misafir Kullanıcı', '1234567890', 'misafir@test.com', 'SMS') # Takip No Hatası için eklenen mock kullanıcı
    ]
    cursor.executemany('INSERT INTO musteriler VALUES (?,?,?,?,?)', musteriler)

    # ---------------------------------------------------------
    # 4. HAREKET ÇEŞİTLERİ
    # ---------------------------------------------------------
    cursor.execute('CREATE TABLE hareket_cesitleri (id INTEGER PRIMARY KEY, durum_adi TEXT)')
    cursor.executemany('INSERT INTO hareket_cesitleri VALUES (?,?)', [
        (1, 'HAZIRLANIYOR'),
        (2, 'TRANSFER'),
        (3, 'DAGITIMDA'),
        (4, 'TESLIM_EDILDI'),
        (8, 'IPTAL EDILDI')
    ])

    # ---------------------------------------------------------
    # 5. SİPARİŞLER
    # ---------------------------------------------------------
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
        ('123456', 1001, 1002, 'Kitap Kolisi'),
        ('999999', 1003, 1001, 'Mobilya'),
        ('456789', 1004, 1003, 'Kıyafet')
    ]
    cursor.executemany('INSERT INTO siparisler VALUES (?,?,?,?)', siparisler)

    # ---------------------------------------------------------
    # 6. KARGO TAKİP
    # ---------------------------------------------------------
    cursor.execute('''
        CREATE TABLE kargo_takip (
            takip_no TEXT PRIMARY KEY,
            siparis_no TEXT,
            durum_id INTEGER,
            tahmini_teslim DATE,
            teslim_adresi TEXT,
            kurye_id INTEGER,
            FOREIGN KEY(siparis_no) REFERENCES siparisler(siparis_no),
            FOREIGN KEY(kurye_id) REFERENCES kuryeler(kurye_id)
        )
    ''')
    bugun = datetime.now().strftime('%Y-%m-%d')

    kargolar = [
        ('123456', '123456', 3, bugun, 'Moda Cad. No:10 Kadıköy/İSTANBUL', 201),
        ('999999', '999999', 4, bugun, 'Pınar Mah. No:5 Sarıyer/İSTANBUL', 202),
        ('456789', '456789', 1, '2025-12-10', 'Barbaros Hayrettin Paşa Mah. Beylikdüzü/İSTANBUL', 203)
    ]
    cursor.executemany('INSERT INTO kargo_takip VALUES (?,?,?,?,?,?)', kargolar)

    # ---------------------------------------------------------
    # 7. ŞİKAYETLER (4. Niyet için gerekli kolonlar)
    # ---------------------------------------------------------
    cursor.execute('''
        CREATE TABLE sikayetler (
            sikayet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            siparis_no TEXT,
            olusturan_musteri_id INTEGER,
            konu TEXT,
            durum TEXT DEFAULT 'ACIK',
            tarih DATE,
            tip TEXT,               
            takip_no TEXT,         
            aciklama TEXT          
        )
    ''')
    
    # ... Diğer tablolar (İade, Hasar, Ücret, Fatura) buraya eklenmeli

    conn.commit()
    conn.close()
    print("✅ Veritabanı YENİ NİYETLER İÇİN güncellendi ve hazır!")


if __name__ == "__main__":
    create_simulation_db()