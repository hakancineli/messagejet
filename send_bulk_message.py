import requests
import time
import json
import os

# API Anahtarı
API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"

def send_message(phone, message):
    url = "https://waba-v2.360dialog.io/v1/messages"
    headers = {
        "D360-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    data = {
        "recipient_type": "individual",
        "to": f"90{phone}",
        "type": "text",
        "text": {
            "body": message
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"✅ Başarılı: {phone}")
            return True
        else:
            print(f"❌ Hata ({response.status_code}): {phone} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Hata: {phone} - {str(e)}")
        return False

def main():
    # Kontrol dosyası
    control_file = "bulk_message_sent.json"
    
    # Eğer daha önce gönderilmişse çık
    if os.path.exists(control_file):
        print("Bu mesaj daha önce gönderilmiş. Tekrar göndermek için bulk_message_sent.json dosyasını silin.")
        return
    
    # Mesaj içeriği
    message = "aktif2"
    
    # Başarılı ve başarısız numaraları takip et
    successful = []
    failed = []
    
    # 1'den 3500'e kadar numaralara gönder
    for number in range(1, 3501):
        # Numarayı 4 haneli formata getir
        formatted_number = str(number).zfill(4)
        
        print(f"Gönderiliyor: {formatted_number}")
        
        if send_message(formatted_number, message):
            successful.append(formatted_number)
        else:
            failed.append(formatted_number)
        
        # Her 10 mesajda bir 5 saniye bekle (API limitlerine takılmamak için)
        if number % 10 == 0:
            print("5 saniye bekleniyor...")
            time.sleep(5)
    
    # Sonuçları kaydet
    results = {
        "message": message,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_sent": len(successful),
        "total_failed": len(failed),
        "successful": successful,
        "failed": failed
    }
    
    # Sonuçları dosyaya yaz
    with open(control_file, "w") as f:
        json.dump(results, f, indent=4)
    
    print("\nGönderim tamamlandı!")
    print(f"Başarılı: {len(successful)}")
    print(f"Başarısız: {len(failed)}")
    print(f"Sonuçlar {control_file} dosyasına kaydedildi.")

if __name__ == "__main__":
    main() 