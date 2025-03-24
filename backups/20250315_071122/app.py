from flask import Flask, render_template, jsonify, request, send_from_directory
import json
from datetime import datetime
import requests
import pandas as pd
from werkzeug.utils import secure_filename
import os
import sqlite3

app = Flask(__name__)

# Veritabanı bağlantısı
def get_db():
    db = sqlite3.connect('messagejet.db')
    db.row_factory = sqlite3.Row
    return db

# Veritabanı tablolarını oluştur
def init_db():
    with get_db() as db:
        # Tablolar zaten var mı kontrol et
        tables = db.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND (name='messages' OR name='contacts')
        """).fetchall()
        
        # Eğer tablolar yoksa oluştur
        if len(tables) < 2:
            print("Veritabanı tabloları oluşturuluyor...")
            
            # Tabloları oluştur
            db.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE,
                    phone TEXT,
                    name TEXT,
                    message TEXT,
                    direction TEXT,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    media_type TEXT,
                    media_url TEXT,
                    media_filename TEXT
                )
            ''')
            
            db.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE,
                    name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            db.commit()
            print("Veritabanı tabloları başarıyla oluşturuldu.")
        else:
            print("Veritabanı tabloları zaten mevcut.")

# Uygulama başlangıcında tabloları oluştur
init_db()

# API Yapılandırması
BASE_URL = "https://waba-v2.360dialog.io"
API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"

# Excel dosyaları için upload klasörü
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def load_messages():
    try:
        with open('message_tracking.json', 'r') as f:
            data = json.load(f)
            if isinstance(data.get('messages'), dict) and 'messages' in data['messages']:
                messages = data['messages']['messages']
            else:
                messages = data.get('messages', [])
            
            # Mesajları tarihe göre sırala (en yeni en üstte)
            messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return {"messages": messages}
    except:
        return {"messages": []}

def save_messages(messages):
    with open('message_tracking.json', 'w') as f:
        if isinstance(messages, dict) and 'messages' in messages:
            json.dump(messages, f, indent=2)
        else:
            json.dump({"messages": messages}, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("\n=== Webhook İsteği Alındı ===")
        print("İstek Başlıkları:", request.headers)
        data = request.get_json()
        print("İstek Gövdesi:", data)
        
        if not data:
            print("Hata: JSON verisi bulunamadı")
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        # Test isteği kontrolü
        if data.get('test'):
            print("Test isteği alındı")
            return jsonify({"status": "success"}), 200

        print("\nMesaj İşleme:")
        
        # WhatsApp API'den gelen mesajları işle
        if data.get('object') == 'whatsapp_business_account':
            with get_db() as db:
                for entry in data.get('entry', []):
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        
                        # Gelen mesajları işle
                        if value.get('messages'):
                            for message in value['messages']:
                                try:
                                    message_id = message.get('id')
                                    if not message_id:
                                        print("Hata: message_id bulunamadı")
                                        continue

                                    print(f"\nMesaj ID: {message_id}")
                                    print(f"Tüm mesaj verisi: {message}")

                                    # Mesaj tipini kontrol et
                                    msg_type = message.get('type', '')
                                    print(f"Mesaj tipi: {msg_type}")

                                    # Gönderen bilgilerini al
                                    phone = message.get('from', '')
                                    
                                    # Kişi bilgisini kontrol et
                                    contact_info = value.get('contacts', [{}])[0]
                                    name = contact_info.get('profile', {}).get('name') or phone
                                    print(f"Gönderen: {phone}, İsim: {name}")

                                    # Timestamp'i al ve dönüştür
                                    timestamp_str = message.get('timestamp', '')
                                    try:
                                        timestamp = datetime.fromtimestamp(int(timestamp_str))
                                        print(f"Timestamp: {timestamp}")
                                    except:
                                        timestamp = datetime.now()
                                        print(f"Timestamp dönüştürme hatası, şu anki zaman kullanılıyor: {timestamp}")

                                    # Kişiyi veritabanına ekle veya güncelle
                                    db.execute('INSERT OR REPLACE INTO contacts (phone, name) VALUES (?, ?)', 
                                             (phone, name))
                                    db.commit()
                                    
                                    # Mesaj içeriğini al
                                    message_content = ""
                                    media_type = None
                                    media_url = None
                                    media_filename = None
                                    
                                    if msg_type == 'text':
                                        message_content = message.get('text', {}).get('body', '')
                                    elif msg_type == 'image':
                                        message_content = "[Resim]"
                                        media_type = 'image'
                                        media_url = message.get('image', {}).get('url')
                                    elif msg_type == 'video':
                                        message_content = "[Video]"
                                        media_type = 'video'
                                        media_url = message.get('video', {}).get('url')
                                    elif msg_type == 'document':
                                        message_content = "[Döküman]"
                                        media_type = 'document'
                                        media_url = message.get('document', {}).get('url')
                                        media_filename = message.get('document', {}).get('filename')
                                    elif msg_type == 'location':
                                        message_content = "[Konum]"
                                        media_type = 'location'
                                    elif msg_type == 'contacts':
                                        message_content = "[Kişi Kartı]"
                                        media_type = 'contacts'
                                    
                                    print(f"Mesaj içeriği: {message_content}")
                                    
                                    # Mesajı veritabanına kaydet
                                    db.execute('''
                                        INSERT INTO messages (
                                            message_id, phone, name, message, direction, status,
                                            media_type, media_url, media_filename, timestamp
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (
                                        message_id,
                                        phone,
                                        name,
                                        message_content,
                                        'incoming',  # Webhook'tan gelen mesajlar her zaman 'incoming'
                                        'delivered',
                                        media_type,
                                        media_url,
                                        media_filename,
                                        timestamp.strftime('%Y-%m-%d %H:%M:%S')
                                    ))
                                    db.commit()
                                    print(f"Mesaj başarıyla kaydedildi: {message_id}")
                                    print(f"Mesaj yönü: incoming")
                                    print(f"Kaydedilen veri: message_id={message_id}, phone={phone}, name={name}, message={message_content}, direction=incoming")
                                except Exception as e:
                                    print(f"Mesaj işlenirken hata: {str(e)}")
                                    continue
                        
                        # Durum güncellemelerini işle
                        if value.get('statuses'):
                            for status in value['statuses']:
                                try:
                                    msg_id = status.get('id')
                                    status_type = status.get('status')
                                    
                                    print(f"\nDurum güncellemesi alındı:")
                                    print(f"Mesaj ID: {msg_id}")
                                    print(f"Yeni durum: {status_type}")
                                    
                                    if msg_id:
                                        db.execute('''
                                            UPDATE messages 
                                            SET status = ? 
                                            WHERE message_id = ?
                                        ''', (status_type, msg_id))
                                        db.commit()
                                        print(f"Mesaj durumu güncellendi: {msg_id} -> {status_type}")
                                except Exception as e:
                                    print(f"Durum güncellenirken hata: {str(e)}")
                                    continue
                            
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Webhook işlenirken hata oluştu: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Webhook doğrulama endpoint'i
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    try:
        print("Webhook doğrulama isteği alındı")
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        print(f"Mode: {mode}, Token: {token}, Challenge: {challenge}")
        
        verify_token = "messagejet_webhook_verify_token"
        
        if mode and token:
            if mode == 'subscribe' and token == verify_token:
                print("Webhook başarıyla doğrulandı!")
                return challenge
            else:
                print("Webhook doğrulama başarısız: Token eşleşmedi")
                return 'Forbidden', 403
        else:
            print("Webhook doğrulama başarısız: Eksik parametreler")
            return 'Bad Request', 400
    except Exception as e:
        print(f"Webhook doğrulamada hata: {str(e)}")
        return 'Internal Server Error', 500

@app.route('/api/messages')
def get_messages():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, message_id, phone, name, message, direction, status, 
                   datetime(timestamp, '+3 hours') as timestamp,
                   media_type, media_url, media_filename
            FROM messages 
            ORDER BY timestamp DESC
        """)
        
        messages = cursor.fetchall()
        return jsonify([{
            'id': msg[0],
            'message_id': msg[1],
            'phone': msg[2],
            'name': msg[3],
            'message': msg[4],
            'direction': msg[5],
            'status': msg[6],
            'timestamp': msg[7],
            'media_type': msg[8],
            'media_url': msg[9],
            'media_filename': msg[10]
        } for msg in messages])
    except Exception as e:
        print(f"Hata: {str(e)}")
        return jsonify([])

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    phone = data.get('phone')
    message = data.get('message')
    message_type = data.get('type', 'text')
    
    if not phone:
        return jsonify({'success': False, 'message': 'Telefon numarası gerekli'})
    
    try:
        # Telefon numarasını düzenle
        if not phone.startswith('+'):
            phone = '+' + phone.replace(' ', '').replace('-', '')
        
        # API isteği için payload hazırla
        if message_type == 'text':
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone,
                "type": "text",
                "text": {
                    "body": message
                }
            }
        elif message_type.startswith('template:'):
            _, template_name, language = message_type.split(':')
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language
                    }
                }
            }
        else:
            return jsonify({'success': False, 'message': 'Geçersiz mesaj tipi'})

        # API'ye gönder
        headers = {
            "D360-API-KEY": API_KEY,
            "Content-Type": "application/json"
        }
        
        print(f"API isteği gönderiliyor: {json.dumps(payload, indent=2)}")
        response = requests.post(f"{BASE_URL}/messages", json=payload, headers=headers)
        response_data = response.json()
        print(f"API yanıtı: {json.dumps(response_data, indent=2)}")

        if response.status_code == 200:
            with get_db() as db:
                # Kişi bilgisini al
                contact = db.execute('SELECT * FROM contacts WHERE phone = ?', (phone,)).fetchone()
                name = contact['name'] if contact else phone
                
                # Mesajı veritabanına kaydet
                message_id = response_data.get('messages', [{}])[0].get('id', f"local_{int(datetime.now().timestamp())}")
                db.execute('''
                    INSERT INTO messages (
                        message_id, phone, name, message, direction, status, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message_id,
                    phone,
                    name,
                    message,
                    'outgoing',
                    'sent',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                db.commit()
            
            return jsonify({
                'success': True, 
                'message': 'Mesaj başarıyla gönderildi',
                'message_id': message_id
            })
        else:
            error_msg = response_data.get('error', {}).get('message', 'Bilinmeyen hata')
            return jsonify({
                'success': False, 
                'message': f'API Hatası: {error_msg}'
            })
            
    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/contacts', methods=['POST'])
def add_contact():
    data = request.json
    phone = data.get('phone')
    name = data.get('name', '').strip() or phone  # İsim boşsa telefon numarasını kullan
    
    if not phone:
        return jsonify({'success': False, 'message': 'Telefon numarası gerekli'})
    
    try:
        with get_db() as db:
            # Önce kişiyi contacts tablosuna ekle
            db.execute('INSERT OR REPLACE INTO contacts (phone, name) VALUES (?, ?)', 
                      (phone, name))
            
            # Örnek bir hoşgeldin mesajı ekle
            welcome_message = "Hoş geldiniz! Size nasıl yardımcı olabilirim?"
            db.execute('''
                INSERT INTO messages (
                    message_id, phone, name, message, direction, status, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"welcome_{phone}_{int(datetime.now().timestamp())}", 
                phone, 
                name,  # Güncellenmiş ismi kullan
                welcome_message,
                'outgoing',
                'sent',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            db.commit()
            
        return jsonify({'success': True, 'message': 'Kişi başarıyla eklendi'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/templates')
def get_templates():
    # Örnek template listesi
    templates = [
        {
            "name": "welcome",
            "language": "tr",
            "components": [
                {
                    "type": "body",
                    "text": "Merhaba! Size nasıl yardımcı olabilirim?"
                }
            ]
        },
        {
            "name": "order_confirmation",
            "language": "tr",
            "components": [
                {
                    "type": "body",
                    "text": "Siparişiniz alındı. Teşekkür ederiz!"
                }
            ]
        }
    ]
    return jsonify({"success": True, "templates": templates})

@app.route('/send_bulk_messages', methods=['POST'])
def send_bulk_messages():
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'Dosya yüklenmedi'
            })

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'Dosya seçilmedi'
            })

        if not file.filename.endswith('.xlsx'):
            return jsonify({
                'success': False,
                'message': 'Sadece Excel (.xlsx) dosyaları kabul edilir'
            })

        # Dosyayı geçici olarak kaydet
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Excel dosyasını oku
        df = pd.read_excel(filepath)
        
        if 'phone' not in df.columns:
            os.remove(filepath)
            return jsonify({
                'success': False,
                'message': 'Excel dosyasında "phone" sütunu bulunamadı'
            })

        success_count = 0
        failed_count = 0
        failed_numbers = []

        # Her numara için mesaj gönder
        for index, row in df.iterrows():
            phone = str(row['phone'])
            
            # Telefon numarası formatını düzenle
            if not phone.startswith('+'):
                phone = '+' + phone

            try:
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

                headers = {
                    "D360-API-KEY": API_KEY,
                    "Content-Type": "application/json"
                }

                response = requests.post(f"{BASE_URL}/messages", json=payload, headers=headers)
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_numbers.append(phone)
                
            except Exception as e:
                failed_count += 1
                failed_numbers.append(phone)

        # Geçici dosyayı sil
        os.remove(filepath)

        return jsonify({
            'success': True,
            'message': f'Toplu mesaj gönderme tamamlandı. Başarılı: {success_count}, Başarısız: {failed_count}',
            'failed_numbers': failed_numbers
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata oluştu: {str(e)}'
        })

if __name__ == '__main__':
    app.run(port=3002, debug=True)