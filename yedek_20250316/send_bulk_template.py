import requests
import time
import sqlite3
import csv
from datetime import datetime, timedelta
import pandas as pd
import schedule
import sys
import socket
import json
import os
from datetime import datetime, timedelta
import pytz

API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"
API_URL = "https://waba-v2.360dialog.io/messages"

# Sabah başlama saati
BASLAMA_SAATI = "09:00"
# Başlangıç müşteri numarası
BASLANGIC_MUSTERI = 3000
# Maksimum yeniden deneme sayısı
MAX_RETRY = 3
# İnternet kontrolü için bekleme süresi (saniye)
INTERNET_CHECK_WAIT = 30
# Türkiye saat dilimi
TIMEZONE = pytz.timezone('Europe/Istanbul')

def get_current_time():
    """Türkiye saatini döndür"""
    return datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')

def check_internet():
    """İnternet bağlantısını kontrol et"""
    try:
        # 360dialog API'sine bağlantıyı test et
        response = requests.get("https://waba-v2.360dialog.io", timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

def wait_for_internet():
    """İnternet bağlantısı gelene kadar bekle"""
    while not check_internet():
        print("\n❌ İnternet bağlantısı yok! 30 saniye sonra tekrar deneniyor...")
        time.sleep(INTERNET_CHECK_WAIT)
    print("\n✅ İnternet bağlantısı tekrar sağlandı. İşleme devam ediliyor...")

def get_db():
    db = sqlite3.connect('messagejet.db')
    db.row_factory = sqlite3.Row
    return db

def get_last_customer():
    """Son mesaj gönderilen müşteriyi bul"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(customer_id) as last_id FROM messages")
        result = cursor.fetchone()
        conn.close()
        return result['last_id'] if result and result['last_id'] else BASLANGIC_MUSTERI
    except Exception as e:
        print(f"Son müşteri bulma hatası: {str(e)}")
        return BASLANGIC_MUSTERI

def load_sent_messages():
    """Başarıyla gönderilen mesajları yükle"""
    if os.path.exists('sent_messages.json'):
        try:
            with open('sent_messages.json', 'r') as f:
                return json.load(f)
        except:
            return {'phones': [], 'customer_ids': []}
    return {'phones': [], 'customer_ids': []}

def save_sent_message(phone, customer_id):
    """Başarıyla gönderilen mesajı kaydet"""
    sent_messages = load_sent_messages()
    if phone not in sent_messages['phones']:
        sent_messages['phones'].append(phone)
    if customer_id and customer_id not in sent_messages['customer_ids']:
        sent_messages['customer_ids'].append(customer_id)
    
    with open('sent_messages.json', 'w') as f:
        json.dump(sent_messages, f, indent=2)

def is_message_sent(phone=None, customer_id=None):
    """Mesajın daha önce başarıyla gönderilip gönderilmediğini kontrol et"""
    sent_messages = load_sent_messages()
    if phone and phone in sent_messages['phones']:
        return True
    if customer_id and customer_id in sent_messages['customer_ids']:
        return True
    return False

def load_failed_messages():
    """Başarısız mesajları yükle"""
    if os.path.exists('failed_messages.json'):
        try:
            with open('failed_messages.json', 'r') as f:
                return json.load(f)
        except:
            return {'messages': []}
    return {'messages': []}

def save_failed_message(phone, customer_id, name):
    """Başarısız mesajı kaydet"""
    failed_messages = load_failed_messages()
    
    # Eğer bu mesaj zaten kayıtlıysa ekleme
    for msg in failed_messages['messages']:
        if msg['phone'] == phone or (customer_id and msg['customer_id'] == customer_id):
            return
    
    failed_messages['messages'].append({
        'phone': phone,
        'customer_id': customer_id,
        'name': name
    })
    
    with open('failed_messages.json', 'w') as f:
        json.dump(failed_messages, f, indent=2)

def remove_from_failed_messages(phone, customer_id):
    """Başarısız mesajlar listesinden sil"""
    failed_messages = load_failed_messages()
    failed_messages['messages'] = [
        msg for msg in failed_messages['messages']
        if msg['phone'] != phone and (not customer_id or msg['customer_id'] != customer_id)
    ]
    
    with open('failed_messages.json', 'w') as f:
        json.dump(failed_messages, f, indent=2)

def send_template_message(to_number, customer_name, customer_id, retry_count=0):
    """Mesaj gönderme fonksiyonu, internet bağlantısı kontrolü ile"""
    
    # Daha önce başarıyla gönderilmiş mi kontrol et
    if is_message_sent(to_number, customer_id):
        print(f"\n⚠️ Bu mesaj daha önce başarıyla gönderilmiş:")
        print(f"Telefon: {to_number}")
        print(f"Müşteri ID: {customer_id}")
        print(f"İsim: {customer_name}")
        return True
    
    # İnternet bağlantısını kontrol et
    if not check_internet():
        print("\n❌ İnternet bağlantısı yok! Bağlantı bekleniyor...")
        wait_for_internet()
    
    url = API_URL
    headers = {
        'D360-API-KEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "pro_transfer",
            "language": {
                "code": "ar"
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        if response.status_code == 200:
            print(f"Mesaj başarıyla gönderildi: {to_number}")
            
            # Mesajı veritabanına kaydet
            conn = sqlite3.connect('messagejet.db')
            cursor = conn.cursor()
            
            message_id = response_data.get('messages', [{}])[0].get('id')
            cursor.execute('''
                INSERT INTO messages (message_id, phone, name, message, direction, status, timestamp, customer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_id,
                to_number,
                customer_name,
                "Template Message: pro_transfer",
                'outgoing',
                'sent',
                get_current_time(),
                customer_id
            ))
            
            # Kişiyi contacts tablosuna da ekle/güncelle
            cursor.execute('''
                INSERT OR REPLACE INTO contacts (phone, name)
                VALUES (?, ?)
            ''', (to_number, customer_name))
            
            conn.commit()
            conn.close()
            
            # Başarılı mesajı kaydet ve başarısız listesinden sil
            save_sent_message(to_number, customer_id)
            remove_from_failed_messages(to_number, customer_id)
            
            return True
            
        else:
            error_message = f"API Hatası: {response_data}"
            if 'error' in response_data:
                error_details = response_data['error']
                error_message = f"Hata Kodu: {error_details.get('code')}, Mesaj: {error_details.get('message')}"
                if 'error_data' in error_details:
                    error_message += f", Detay: {error_details['error_data']}"
            
            print(f"Mesaj gönderilemedi: {to_number}, {error_message}")
            
            # Eğer maksimum deneme sayısına ulaşılmadıysa tekrar dene
            if retry_count < MAX_RETRY:
                print(f"Yeniden deneniyor... ({retry_count + 1}/{MAX_RETRY})")
                time.sleep(5)  # 5 saniye bekle
                return send_template_message(to_number, customer_name, customer_id, retry_count + 1)
            
            # Maksimum deneme sayısına ulaşıldıysa hatayı kaydet
            conn = sqlite3.connect('messagejet.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (message_id, phone, name, message, direction, status, timestamp, customer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                None,
                to_number,
                customer_name,
                f"Error: {error_message}",
                'outgoing',
                'failed',
                get_current_time(),
                customer_id
            ))
            conn.commit()
            conn.close()
            
            # Başarısız mesajı kaydet
            save_failed_message(to_number, customer_id, customer_name)
            
            return False

    except Exception as e:
        error_message = f"Sistem Hatası: {str(e)}"
        print(f"Hata oluştu: {error_message}")
        
        # Bağlantı hatası durumunda tekrar dene
        if isinstance(e, (requests.ConnectionError, requests.Timeout)) and retry_count < MAX_RETRY:
            print(f"Bağlantı hatası! Yeniden deneniyor... ({retry_count + 1}/{MAX_RETRY})")
            time.sleep(5)  # 5 saniye bekle
            return send_template_message(to_number, customer_name, customer_id, retry_count + 1)
        
        # Maksimum deneme sayısına ulaşıldıysa hatayı kaydet
        conn = sqlite3.connect('messagejet.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (message_id, phone, name, message, direction, status, timestamp, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            None,
            to_number,
            customer_name,
            f"System Error: {error_message}",
            'outgoing',
            'failed',
            get_current_time(),
            customer_id
        ))
        conn.commit()
        conn.close()
        
        return False

def save_to_db(message_id, phone, name, direction, status="sent", customer_id=None):
    conn = sqlite3.connect('messagejet.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO messages (message_id, phone, name, message, direction, status, timestamp, customer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (message_id, phone, name, "Template Message", direction, status, get_current_time(), customer_id))
    
    conn.commit()
    conn.close()

def format_phone_number(phone):
    # Numara format detaylarını göster
    print("\nNumara format detayları:")
    print(f"Ham numara: {phone}")
    
    # Numarayı temizle
    cleaned = str(phone).strip()
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    print(f"Temizlenmiş numara: {cleaned}")
    print(f"Uzunluk: {len(cleaned)} hane")
    
    return cleaned

def retry_failed_messages(start_id=None, end_id=None):
    """Belirli aralıktaki veya tüm başarısız mesajları tekrar gönder"""
    failed_messages = load_failed_messages()
    
    if not failed_messages['messages']:
        print("\nBaşarısız mesaj bulunamadı.")
        return True
    
    # Müşteri ID aralığına göre filtrele
    if start_id and end_id:
        messages_to_retry = [
            msg for msg in failed_messages['messages']
            if msg['customer_id'] and start_id <= msg['customer_id'] <= end_id
        ]
    else:
        messages_to_retry = failed_messages['messages']
    
    if not messages_to_retry:
        print("\nBelirtilen aralıkta başarısız mesaj bulunamadı.")
        return True
    
    print(f"\n{'='*50}")
    print(f"BAŞARISIZ MESAJLAR RAPORU")
    print(f"{'='*50}")
    print(f"Toplam {len(messages_to_retry)} başarısız mesaj bulundu.")
    if start_id and end_id:
        print(f"Müşteri aralığı: {start_id} - {end_id}")
    print("\nTekrar gönderme işlemi başlıyor...\n")
    
    success_count = 0
    still_failed = 0
    
    for msg in messages_to_retry:
        phone = msg['phone']
        customer_id = msg['customer_id']
        name = msg['name']
        
        print(f"\nMüşteri {customer_id if customer_id else 'ID yok'} için mesaj tekrar gönderiliyor...")
        print(f"Telefon: {phone}")
        print(f"İsim: {name}")
        
        if send_template_message(phone, name, customer_id):
            success_count += 1
            print(f"✅ Başarılı: {phone} - {name}")
        else:
            still_failed += 1
            print(f"❌ Hala başarısız: {phone} - {name}")
        
        time.sleep(3)  # Her mesaj arasında 3 saniye bekle
    
    print(f"\n{'='*50}")
    print(f"BAŞARISIZ MESAJ GÖNDERİM SONUÇLARI")
    print(f"{'='*50}")
    print(f"Toplam denenen: {len(messages_to_retry)}")
    print(f"Başarılı: {success_count}")
    print(f"Hala başarısız: {still_failed}")
    print(f"{'='*50}\n")
    
    return still_failed == 0  # Tüm mesajlar başarılı ise True döndür

def main():
    success_count = 0
    failed_count = 0
    last_customer = get_last_customer()
    start_index = last_customer - 301  # Excel'deki indeks hesaplaması
    rapor_noktasi = 3100

    # Önce başarısız mesajları tekrar gönder
    print("\nÖnce başarısız mesajlar kontrol ediliyor...")
    retry_failed_messages()
    print("\nNormal gönderim işlemine devam ediliyor...")

    try:
        # Excel dosyasını oku
        df = pd.read_excel('aktif.xltx')
        
        print(f"Müşteri {last_customer}'dan devam ediliyor...")
        
        for index, row in df.iloc[start_index:].iterrows():
            current_customer_id = index + 301
            phone = str(row.iloc[0]).strip()  # İlk sütun
            name = str(row.iloc[1]).strip() if len(row) > 1 else f"Müşteri {current_customer_id}"
            
            if phone and str(phone).lower() != 'nan':
                formatted_phone = format_phone_number(phone)
                
                try:
                    print(f"Mesaj gönderiliyor: {formatted_phone} - {name}")
                    if send_template_message(formatted_phone, name, current_customer_id):
                        print(f"✅ Başarılı: {formatted_phone} - {name}")
                        success_count += 1
                    else:
                        print(f"❌ Başarısız: {formatted_phone} - {name}")
                        failed_count += 1
                    
                    # 3100. müşteride rapor ver
                    if current_customer_id == rapor_noktasi:
                        print(f"\n{'='*50}")
                        print(f"3100. MÜŞTERİ RAPORU")
                        print(f"{'='*50}")
                        print(f"Başlangıç müşteri no: {last_customer}")
                        print(f"Şu anki müşteri no: {current_customer_id}")
                        print(f"Toplam gönderilen: {success_count + failed_count}")
                        print(f"Başarılı: {success_count}")
                        print(f"Başarısız: {failed_count}")
                        print(f"Başarı oranı: {(success_count/(success_count + failed_count))*100:.2f}%")
                        print(f"{'='*50}")
                        print("Program çalışmaya devam ediyor...\n")
                    
                    time.sleep(3)  # Her mesaj arasında 3 saniye bekle
                    
                except Exception as e:
                    print(f"Hata: {str(e)}")
                    save_to_db(None, formatted_phone, name, 'outgoing', 'error', current_customer_id)
                    failed_count += 1
    
    except Exception as e:
        print(f"Excel dosyası okuma hatası: {str(e)}")
        return

    print(f"\nToplam sonuç:")
    print(f"Başarılı: {success_count}")
    print(f"Başarısız: {failed_count}")

def run_scheduler():
    """Programı planlanan zamanda çalıştır"""
    print(f"Program {BASLAMA_SAATI}'da başlayacak şekilde ayarlandı...")
    schedule.every().day.at(BASLAMA_SAATI).do(main)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def load_failed_numbers_from_txt():
    """failed_numbers.txt dosyasından başarısız numaraları yükle"""
    failed_numbers = []
    if os.path.exists('failed_numbers.txt'):
        try:
            with open('failed_numbers.txt', 'r') as f:
                for line in f:
                    # Satırı temizle ve boş satırları atla
                    line = line.strip()
                    if line:
                        failed_numbers.append(line)
        except Exception as e:
            print(f"failed_numbers.txt okuma hatası: {str(e)}")
    return failed_numbers

def import_failed_numbers_to_json():
    """failed_numbers.txt dosyasındaki numaraları failed_messages.json'a aktar"""
    failed_numbers = load_failed_numbers_from_txt()
    if not failed_numbers:
        print("failed_numbers.txt dosyası boş veya okunamadı.")
        return
    
    print(f"\n{'='*50}")
    print(f"FAILED_NUMBERS.TXT DOSYASI İÇERİĞİ")
    print(f"{'='*50}")
    print(f"Toplam {len(failed_numbers)} numara bulundu.")
    print("JSON dosyasına aktarılıyor...\n")
    
    for phone in failed_numbers:
        # Numarayı temizle ve formatla
        formatted_phone = format_phone_number(phone)
        # failed_messages.json'a ekle
        save_failed_message(formatted_phone, None, f"Müşteri (failed_numbers.txt)")
    
    print("\nAktarım tamamlandı.")
    print(f"Toplam {len(failed_numbers)} numara failed_messages.json dosyasına eklendi.")

def retry_all_failed():
    """Tüm başarısız mesajları tekrar gönder (hem JSON hem TXT)"""
    # Önce failed_numbers.txt dosyasını kontrol et ve içe aktar
    if os.path.exists('failed_numbers.txt'):
        print("\nfailed_numbers.txt dosyası bulundu. İçe aktarılıyor...")
        import_failed_numbers_to_json()
    
    # Şimdi tüm başarısız mesajları göndermeyi dene
    return retry_failed_messages()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--now":
            main()  # Normal çalıştırma
        elif sys.argv[1] == "--retry":
            # Eğer müşteri aralığı belirtilmişse o aralığı kullan
            if len(sys.argv) > 3:
                start_id = int(sys.argv[2])
                end_id = int(sys.argv[3])
                retry_failed_messages(start_id, end_id)
            else:
                retry_all_failed()  # Tüm başarısız mesajları tekrar gönder
        elif sys.argv[1] == "--import-failed":
            import_failed_numbers_to_json()  # failed_numbers.txt'yi içe aktar
    else:
        run_scheduler()  # Zamanlanmış çalıştırma 