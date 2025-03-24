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
import fcntl  # Dosya kilitleme için
import logging
import argparse

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('messagejet.log')
    ]
)
logger = logging.getLogger(__name__)

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
        headers = {
            'D360-API-KEY': API_KEY,
            'Content-Type': 'application/json'
        }
        response = requests.get("https://waba-v2.360dialog.io", headers=headers, timeout=5)
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
    try:
        # Dosyayı kilit mekanizması ile aç
        with open('sent_messages.json', 'r+') as f:
            # Dosyayı kilitle
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            
            try:
                # Mevcut içeriği oku
                sent_messages = json.load(f)
                
                # Yeni mesajı ekle
                if phone and phone not in sent_messages['phones']:
                    sent_messages['phones'].append(phone)
                if customer_id and customer_id not in sent_messages['customer_ids']:
                    sent_messages['customer_ids'].append(customer_id)
                
                # Dosyanın başına git
                f.seek(0)
                # Yeni içeriği yaz
                json.dump(sent_messages, f, indent=2)
                # Dosyayı kırp (eski içerik daha uzunsa)
                f.truncate()
                # Değişiklikleri diske zorla
                f.flush()
                os.fsync(f.fileno())
            
            finally:
                # Kilidi kaldır
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
    except Exception as e:
        print(f"Mesaj kaydetme hatası: {str(e)}")
        # Dosya yoksa oluştur
        if not os.path.exists('sent_messages.json'):
            with open('sent_messages.json', 'w') as f:
                json.dump({'phones': [], 'customer_ids': []}, f, indent=2)

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
    
    logger.debug(f"Mesaj gönderiliyor: {to_number} ({customer_name})")
    
    # Daha önce başarıyla gönderilmiş mi kontrol et
    if is_message_sent(to_number, customer_id):
        logger.warning(f"Bu mesaj daha önce başarıyla gönderilmiş: {to_number} ({customer_id})")
        return True
    
    # İnternet bağlantısını kontrol et
    if not check_internet():
        logger.error("İnternet bağlantısı yok! Bağlantı bekleniyor...")
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
            "name": "sorunyok",
            "language": {
                "code": "ar"
            }
        }
    }
    
    try:
        logger.debug(f"API isteği gönderiliyor: {payload}")
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        if response.status_code == 200:
            logger.info(f"Mesaj başarıyla gönderildi: {to_number}")
            
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
                "Template Message: sorunyok",
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
            
            # Başarılı mesajı tum_basarili_mesajlar.txt'ye ekle
            with open('tum_basarili_mesajlar.txt', 'a') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{to_number}|{customer_name}|{timestamp}|sent\n")
            
            return True
            
        else:
            error_message = f"API Hatası: {response_data}"
            if 'error' in response_data:
                error_details = response_data['error']
                error_message = f"Hata Kodu: {error_details.get('code')}, Mesaj: {error_details.get('message')}"
                if 'error_data' in error_details:
                    error_message += f", Detay: {error_details['error_data']}"
            
            logger.error(f"Mesaj gönderilemedi: {to_number}, {error_message}")
            
            # Başarısız mesajı kaydet
            save_failed_message(to_number, customer_id, customer_name)
            
            # Veritabanına başarısız durumu kaydet
            conn = sqlite3.connect('messagejet.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (phone, name, message, direction, status, timestamp, customer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                to_number,
                customer_name,
                error_message,
                'outgoing',
                'failed',
                get_current_time(),
                customer_id
            ))
            conn.commit()
            conn.close()
            
            return False
            
    except Exception as e:
        logger.exception(f"Beklenmeyen hata: {str(e)}")
        save_failed_message(to_number, customer_id, customer_name)
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
    # Numarayı temizle
    cleaned = str(phone).strip()
    
    # Müşteri adı veya ID'yi ayır
    if '|' in cleaned:
        cleaned = cleaned.split('|')[0]
    
    # + işaretini ekle
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    logger.debug(f"Numara formatlandı: {cleaned}")
    return cleaned

def retry_failed_messages(start_id=None, end_id=None):
    """Başarısız mesajları yeniden gönder"""
    logger.info("Başarısız mesajlar yeniden gönderiliyor...")
    failed_messages = load_failed_messages()
    
    for msg in failed_messages['messages']:
        customer_id = msg.get('customer_id')
        
        # Eğer ID aralığı belirtilmişse, sadece o aralıktaki mesajları gönder
        if start_id and end_id:
            if not customer_id or customer_id < start_id or customer_id > end_id:
                continue
        
        phone = msg.get('phone')
        name = msg.get('name')
        
        if phone and name:
            # Telefon numarasını formatla
            formatted_phone = format_phone_number(phone)
            logger.info(f"Yeniden gönderiliyor: {formatted_phone} ({name})")
            send_template_message(formatted_phone, name, customer_id)
            time.sleep(1)  # API limitlerini aşmamak için bekle

def main():
    """Ana program"""
    parser = argparse.ArgumentParser(description='Toplu mesaj gönderme programı')
    parser.add_argument('--retry-all', action='store_true', help='Tüm başarısız mesajları yeniden gönder')
    parser.add_argument('--retry-range', nargs=2, type=int, metavar=('START_ID', 'END_ID'),
                      help='Belirtilen ID aralığındaki mesajları yeniden gönder')
    parser.add_argument('--from-excel', type=str, help='Excel dosyasından mesaj gönder')
    
    args = parser.parse_args()
    
    if args.retry_all:
        retry_all_failed()
    elif args.retry_range:
        start_id, end_id = args.retry_range
        retry_failed_messages(start_id, end_id)
    elif args.from_excel:
        numbers = load_numbers_from_excel(args.from_excel)
        for phone, customer_id in numbers:
            customer_name = f"Müşteri {customer_id}"
            send_template_message(phone, customer_name, customer_id)
    else:
        print("Geçersiz komut! Kullanım:")
        print("  python3 send_bulk_template.py --retry-all")
        print("  python3 send_bulk_template.py --retry-range START_ID END_ID")
        print("  python3 send_bulk_template.py --from-excel EXCEL_DOSYASI")

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

def load_numbers_from_excel(filename='numbers.xlsx'):
    """Excel veya metin dosyasından numara ve müşteri ID'lerini yükle"""
    try:
        # Excel dosyasını oku
        df = pd.read_excel(filename)
        
        # Sütun isimlerini kontrol et
        if 'phone' not in df.columns or 'name' not in df.columns:
            print("Excel dosyasında 'phone' ve 'name' sütunları bulunamadı!")
            return []
        
        valid_numbers = []
        for _, row in df.iterrows():
            try:
                phone = str(row['phone']).strip()
                name = str(row['name']).strip()
                
                # Müşteri ID'yi ayıkla
                customer_id = name.replace('Müşteri ', '')
                
                # NaN değerleri kontrol et
                if pd.isna(phone) or pd.isna(name):
                    continue
                
                # Telefon numarasını formatla
                if phone.startswith('+900'):
                    phone = '+' + phone[4:]
                elif not phone.startswith('+'):
                    if phone.startswith('0'):
                        phone = '+' + phone[1:]
                    else:
                        phone = '+' + phone
                
                valid_numbers.append((phone, customer_id))
                print(f"Numara okundu: {phone} (Müşteri ID: {customer_id})")
            except Exception as e:
                print(f"Satır işlenirken hata: {str(e)}")
                continue
        
        print(f"Toplam {len(valid_numbers)} geçerli numara bulundu.")
        return valid_numbers
    except Exception as e:
        print(f"Dosya okunurken hata: {str(e)}")
        return []

def save_message_with_customer_id(message_id, phone, customer_id, message, direction, status):
    conn = sqlite3.connect('messagejet.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (message_id TEXT PRIMARY KEY,
                  phone TEXT,
                  customer_id TEXT,
                  message TEXT,
                  direction TEXT,
                  status TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''INSERT OR REPLACE INTO messages 
                 (message_id, phone, customer_id, message, direction, status)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (message_id, phone, customer_id, message, direction, status))
    
    conn.commit()
    conn.close()

def send_message(phone, customer_id, template_name="sorunyok", template_language="ar"):
    """Mesaj gönderme fonksiyonu (müşteri ID'si ile)"""
    try:
        # Daha önce başarıyla gönderilmiş mi kontrol et
        conn = sqlite3.connect('messagejet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM messages WHERE phone = ? AND customer_id = ?', 
                      (phone, customer_id))
        result = cursor.fetchone()
        conn.close()

        if result and result[0] == 'success':
            print(f"Bu mesaj daha önce başarıyla gönderilmiş: {phone} (Müşteri ID: {customer_id})")
            return False

        url = "https://waba-v2.360dialog.io/messages"
        headers = {
            "D360-API-KEY": API_KEY,
            "Content-Type": "application/json"
        }

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": template_language
                }
            }
        }

        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            message_id = response.json().get('messages', [{}])[0].get('id')
            save_message_with_customer_id(message_id, phone, customer_id, "Template Message", "outgoing", "sent")
            print(f"Mesaj başarıyla gönderildi: {phone} (Müşteri ID: {customer_id})")
            return True
        else:
            # Başarısız durumda message_id olmayacak, None kullan
            save_message_with_customer_id(None, phone, customer_id, "Template Message", "outgoing", "failed")
            print(f"Mesaj gönderimi başarısız: {phone} (Müşteri ID: {customer_id})")
            print(f"Hata: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        # Hata durumunda message_id olmayacak, None kullan
        save_message_with_customer_id(None, phone, customer_id, "Template Message", "outgoing", "error")
        print(f"Mesaj gönderiminde hata: {phone} (Müşteri ID: {customer_id})")
        print(f"Hata detayı: {str(e)}")
        return False

if __name__ == "__main__":
    main() 