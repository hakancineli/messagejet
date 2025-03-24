import requests
import time
import sqlite3
import csv
from datetime import datetime

API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"
API_URL = "https://waba-v2.360dialog.io/messages"

def send_template_message(to_number, customer_name):
    headers = {
        "D360-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    # + işaretini kaldırarak API'ye gönder
    original_number = to_number
    if to_number.startswith("+"):
        to_number = to_number[1:]
    
    print(f"\nNumara detayları:")
    print(f"Orijinal numara: {original_number}")
    print(f"API'ye gönderilen numara: {to_number}")
    print(f"Numara uzunluğu: {len(to_number)} hane")
    
    data = {
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
    
    response = requests.post(API_URL, headers=headers, json=data)
    response_data = response.json()
    
    if 'messages' in response_data and len(response_data['messages']) > 0:
        print(f"✅ API Yanıtı: Başarılı - Message ID: {response_data['messages'][0]['id']}")
    else:
        print(f"❌ API Yanıtı: Başarısız")
        if 'error' in response_data:
            print(f"Hata Detayı: {response_data['error'].get('message', 'Bilinmeyen hata')}")
            print(f"Hata Kodu: {response_data['error'].get('code', 'Kod yok')}")
    
    return response_data

def save_to_db(message_id, phone, name, direction, status="sent"):
    conn = sqlite3.connect('messagejet.db')
    cursor = conn.cursor()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    template_message = """سلام الله عليكم ورحمة وبركاته  هذا هو رقمنا الجديد
السلام عليكم ورحمة الله وبركاته، هذا هو رقمنا الجديد.
نقل من مطار إسطنبول فقط 30 دولار.
نقل من مطار صبيحة كوكجن فقط 35 دولار.
نحن نوفر حجوزات بأسعار مناسبة للفنادق والشقق عبر موقعنا الإلكتروني.
هل أنتم مستعدون لاكتشاف إسطنبول بطريقة مختلفة؟
•  مقهى بيير لوتي المطل على خليج القرن الذهبي.
•  شوارع التاريخية لفنر وبالات.
•  قصر تشيران الفاخر.
•  حديقة يلدز الجميلة.
•  مسجد سليمان القانوني وآيا صوفيا الصغيرة.
استمتعوا بجولة VIP في إسطنبول مع سيارة مرسيدس فيتو مقابل 125 دولار فقط.
لمزيد من المعلومات، تابعونا على إنستغرام: https://www.instagram.com/airporttohotel/

احجز الآن واستمتع بامتيازات الـ VIP!

+905545832034
احجز الآن واستمتع بامتيازات الـ VIP!"""
    
    cursor.execute("""
        INSERT INTO messages (message_id, phone, name, message, direction, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (message_id, phone, name, template_message, direction, status, current_time))
    
    conn.commit()
    conn.close()

def format_phone_number(phone):
    original = str(phone)
    # Boşlukları ve özel karakterleri kaldır
    phone = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # + işaretini ekle
    if not phone.startswith("+"):
        phone = "+" + phone
    
    # Eğer +0 ile başlıyorsa 0'ı kaldır
    if phone.startswith("+0"):
        phone = "+" + phone[2:]
    
    print(f"\nNumara format detayları:")
    print(f"Ham numara: {original}")
    print(f"Temizlenmiş numara: {phone}")
    print(f"Uzunluk: {len(phone)} hane")
    
    return phone

def main():
    with open('numbers.txt', 'r') as f:
        # CSV başlığını oku
        fieldnames = ['phone', 'name']
        reader = csv.DictReader(f, delimiter='\t', fieldnames=fieldnames)
        
        # Başlık satırını atla
        next(reader)
        
        success_count = 0
        failed_count = 0
        
        for row in reader:
            phone = format_phone_number(row['phone'])
            name = row['name']
            
            try:
                print(f"Mesaj gönderiliyor: {phone} - {name}")
                response = send_template_message(phone, name)
                
                if 'messages' in response and len(response['messages']) > 0:
                    message_id = response['messages'][0]['id']
                    save_to_db(message_id, phone, name, "outgoing")
                    print(f"✅ Başarılı: {phone} - {name}")
                    success_count += 1
                else:
                    print(f"❌ Başarısız: {phone} - {name}")
                    print(f"Hata: {response}")
                    failed_count += 1
                
                # API limitlerini aşmamak için her mesaj arasında 1 saniye bekle
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Hata: {phone} - {name}")
                print(f"Hata detayı: {str(e)}")
                failed_count += 1
    
    print("\n=== Toplu Mesaj Gönderim Raporu ===")
    print(f"Başarılı: {success_count}")
    print(f"Başarısız: {failed_count}")
    print(f"Toplam: {success_count + failed_count}")

if __name__ == "__main__":
    main() 