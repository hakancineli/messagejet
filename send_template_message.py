import requests
import time
import json
import os
import pandas as pd
from datetime import datetime
import sqlite3

# API Anahtarı
API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"  # Lütfen doğru API anahtarınızı girin
BASE_URL = "https://waba-v2.360dialog.io"

def save_to_database(phone, name, message_id, status):
    try:
        conn = sqlite3.connect('messagejet.db')
        cursor = conn.cursor()
        
        # Mesajı veritabanına kaydet
        cursor.execute('''
            INSERT INTO messages (phone, name, message, direction, message_id, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (phone, name, "pro_transfer şablonu gönderildi", "outgoing", message_id, status, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"Veritabanına kaydedildi: {phone} -> {name}")
    except Exception as e:
        print(f"Veritabanı hatası: {str(e)}")

def format_phone_number(number):
    # Numarayı string'e çevir ve boşlukları kaldır
    number = str(number).strip()
    
    # Başındaki + işaretini kaldır
    if number.startswith('+'):
        number = number[1:]
        
    return number

def send_template_message(phone, name):
    # Telefon numarasını formatla
    phone = format_phone_number(phone)
    
    url = f"{BASE_URL}/messages"
    
    headers = {
        "D360-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "template",
        "template": {
            "name": "pro_transfer",
            "language": {
                "code": "ar"
            }
        }
    }

    try:
        print(f"Gönderiliyor: {phone} -> {name}")  # Debug için
        response = requests.post(url, headers=headers, json=payload)
        print(f"API Yanıtı: {response.text}")  # Debug için
        response.raise_for_status()
        
        message_id = response.json().get("messages", [{}])[0].get("id")
        status = response.json().get("messages", [{}])[0].get("message_status")
        
        # Veritabanına kaydet
        save_to_database(phone, name, message_id, status)
        
        result = {
            "success": True,
            "phone": phone,
            "name": name,
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Hata: {phone} -> {name} ({str(e)})")  # Debug için
        result = {
            "success": False,
            "phone": phone,
            "name": name,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    
    return result

def save_results(results, success_file="template_results.json", failed_file="failed_messages.xlsx"):
    # Başarılı sonuçları JSON dosyasına kaydet
    with open(success_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Başarısız sonuçları Excel dosyasına kaydet
    failed_results = [r for r in results if not r["success"]]
    if failed_results:
        df_failed = pd.DataFrame(failed_results)
        df_failed.to_excel(failed_file, index=False)

def process_excel_file():
    try:
        # Excel dosyasını oku
        df = pd.read_excel('aktif3 1-3500 arası.xlsx')
        total_numbers = len(df)
        print(f"Toplam {total_numbers} numara işlenecek")
        
        success_count = 0
        failed_count = 0
        
        # Her numara için mesaj gönder
        for index, row in df.iterrows():
            phone = str(row['number'])
            name = str(row['name'])
            
            print(f"\nGönderiliyor: {phone} -> {name}")
            
            # Mesajı gönder
            success = send_template_message(phone, name)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            # Her 10 numarada bir ilerleme göster
            if (index + 1) % 10 == 0:
                print(f"{index + 1}/{total_numbers} numara işlendi")
            
            # API limitlerini aşmamak için kısa bir bekleme
            time.sleep(0.5)
        
        print(f"\nİşlem tamamlandı:")
        print(f"Başarılı: {success_count}")
        print(f"Başarısız: {failed_count}")
        print(f"Toplam: {total_numbers}")
        
    except Exception as e:
        print(f"Hata: {str(e)}")

if __name__ == "__main__":
    process_excel_file() 