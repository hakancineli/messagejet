import json
import requests
import time
from datetime import datetime

# 360dialog API yapılandırması
API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"
BASE_URL = "https://waba-v2.360dialog.io"
WEBHOOK_URL = "https://f904-151-135-80-154.ngrok-free.app/webhook"

def send_bulk_message():
    data = load_messages()
    results = []
    
    for message in data['messages']:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message['phone'],
            "type": "template",
            "template": {
                "name": "pro_transfer",
                "language": {
                    "code": "ar"
                }
            }
        }
        
        headers = {
            "D360-API-KEY": API_KEY,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/messages", json=payload, headers=headers)
            response_data = response.json()
            
            print(f"API Yanıtı ({message['phone']}): {response.status_code} - {response_data}")
            
            if response.status_code == 200:
                message['message_id'] = response_data.get('messages', [{}])[0].get('id', '')
                message['status'] = 'sent'
                message['timestamp'] = datetime.now().isoformat()
                print(f"Mesaj gönderildi: {message['phone']}")
            else:
                message['status'] = 'failed'
                message['timestamp'] = datetime.now().isoformat()
                print(f"Mesaj gönderilemedi: {message['phone']} - Hata: {response_data}")
            
            results.append({
                'phone': message['phone'],
                'success': response.status_code == 200,
                'response': response_data
            })
            
            # API rate limit'e uymak için kısa bekleme
            time.sleep(1)
            
        except Exception as e:
            print(f"Hata oluştu ({message['phone']}): {str(e)}")
            results.append({
                'phone': message['phone'],
                'success': False,
                'error': str(e)
            })
    
    save_messages(data)
    return results

def update_message_status(message_id):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/messages/{message_id}", headers=headers)
    return response.json()

def load_messages():
    with open('message_tracking.json', 'r') as f:
        return json.load(f)

def save_messages(data):
    with open('message_tracking.json', 'w') as f:
        json.dump(data, f, indent=2)

def check_message_status():
    data = load_messages()
    
    for message in data['messages']:
        if message['message_id']:
            status = update_message_status(message['message_id'])
            message['status'] = status.get('status', 'unknown')
            message['timestamp'] = datetime.now().isoformat()
    
    save_messages(data)
    return data

if __name__ == '__main__':
    # Önce toplu mesaj gönder
    print("Toplu mesaj gönderme başlıyor...")
    results = send_bulk_message()
    print("\nToplu mesaj gönderme sonuçları:")
    for result in results:
        print(f"Telefon: {result['phone']} - Başarılı: {result['success']}")
    
    print("\nMesaj durumları takip ediliyor...")
    # Sonra durumları takip et
    while True:
        try:
            messages = check_message_status()
            print(f"\nMesaj durumları güncellendi: {datetime.now()}")
            for msg in messages['messages']:
                print(f"Telefon: {msg['phone']}, Durum: {msg['status']}")
        except Exception as e:
            print(f"Hata oluştu: {e}")
        
        time.sleep(60)  # Her 1 dakikada bir kontrol et 