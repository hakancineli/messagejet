from flask import Flask, render_template, jsonify, request, send_from_directory
import json
from datetime import datetime
import requests
import pandas as pd
from werkzeug.utils import secure_filename
import os
import sqlite3
from send_bulk_template import send_message, load_numbers_from_excel
import threading
import queue
import time
import logging
from functools import wraps
from cachetools import TTLCache

app = Flask(__name__)

# Loglama seviyesini ayarla
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
app.logger.setLevel(logging.DEBUG)

# Cache ve rate limiting için
messages_cache = TTLCache(maxsize=100, ttl=3)  # 3 saniyelik cache
mark_read_cache = TTLCache(maxsize=1000, ttl=5)  # 5 saniyelik cache

def cache_response(cache, key_prefix=''):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f"{key_prefix}:{request.path}"
            response = cache.get(cache_key)
            if response is not None:
                return response
            response = f(*args, **kwargs)
            cache[cache_key] = response
            return response
        return decorated_function
    return decorator

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
                    customer_id TEXT,
                    name TEXT,
                    message TEXT,
                    direction TEXT,
                    status TEXT,
                    is_read INTEGER DEFAULT 0,
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
                    customer_id TEXT,
                    unread_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            db.commit()
            print("Veritabanı tabloları başarıyla oluşturuldu.")
        else:
            # Mevcut tablolara yeni alanları ekle
            try:
                db.execute('ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 0')
            except:
                print("is_read alanı zaten mevcut")
                
            try:
                db.execute('ALTER TABLE contacts ADD COLUMN unread_count INTEGER DEFAULT 0')
            except:
                print("unread_count alanı zaten mevcut")
            
            db.commit()
            print("Veritabanı tabloları güncellendi.")

# Uygulama başlangıcında tabloları oluştur
init_db()

# API Yapılandırması
BASE_URL = "https://waba-v2.360dialog.io"
API_KEY = "MISyrZTxjZFZTH52tF8M7hwSAK"
WEBHOOK_URL = "https://9a04-151-135-80-53.ngrok-free.app/webhook"
CHANNEL_ID = "570676119468253"

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

def save_sent_message(phone, customer_id):
    """Başarıyla gönderilen mesajı sent_messages.json dosyasına kaydet"""
    try:
        # Dosyayı oku veya yeni oluştur
        if os.path.exists('sent_messages.json'):
            with open('sent_messages.json', 'r') as f:
                sent_messages = json.load(f)
        else:
            sent_messages = {'phones': [], 'customer_ids': []}
        
        # Yeni mesajı ekle
        if phone and phone not in sent_messages['phones']:
            sent_messages['phones'].append(phone)
        if customer_id and customer_id not in sent_messages['customer_ids']:
            sent_messages['customer_ids'].append(customer_id)
        
        # Dosyaya kaydet
        with open('sent_messages.json', 'w') as f:
            json.dump(sent_messages, f, indent=2)
            
    except Exception as e:
        print(f"sent_messages.json kaydetme hatası: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    return jsonify({"status": "ok"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        app.logger.info("==================== YENİ WEBHOOK İSTEĞİ ====================")
        app.logger.info(f"Webhook ham verisi: {json.dumps(data, indent=2)}")
        
        # Mesaj durumu güncellemesi
        if 'entry' in data and len(data['entry']) > 0:
            app.logger.info(f"Entry verisi bulundu: {json.dumps(data['entry'], indent=2)}")
            entry = data['entry'][0]
            if 'changes' in entry and len(entry['changes']) > 0:
                app.logger.info(f"Changes verisi bulundu: {json.dumps(entry['changes'], indent=2)}")
                change = entry['changes'][0]
                if 'value' in change:
                    value = change['value']
                    app.logger.info(f"Value verisi: {json.dumps(value, indent=2)}")
                    
                    # Mesaj durumu güncellemesi
                    if 'statuses' in value:
                        app.logger.debug("Durum güncellemesi alındı")
                        for status in value['statuses']:
                            message_id = status.get('id')
                            new_status = status.get('status')
                            timestamp = status.get('timestamp')
                            app.logger.debug(f"Durum güncelleniyor - ID: {message_id}, Status: {new_status}, Timestamp: {timestamp}")
                            
                            if message_id and new_status:
                                with get_db() as db:
                                    sql = '''
                                        UPDATE messages 
                                        SET status = ?, 
                                            timestamp = datetime(?, 'unixepoch')
                                        WHERE message_id = ?
                                    '''
                                    app.logger.debug(f"SQL sorgusu: {sql} - Parametreler: {(new_status, timestamp, message_id)}")
                                    db.execute(sql, (new_status, timestamp, message_id))
                                    db.commit()
                                    app.logger.debug(f"Durum güncellendi - ID: {message_id}")
                    
                    # Yeni gelen mesajları kaydet
                    if 'messages' in value:
                        app.logger.info("Yeni mesaj alındı")
                        messages = value['messages']
                        app.logger.info(f"İşlenecek mesajlar: {json.dumps(messages, indent=2)}")
                        
                        for message in messages:
                            message_id = message.get('id')
                            from_number = message.get('from')
                            
                            # Mesaj içeriğini al
                            message_text = ''
                            if 'text' in message:
                                message_text = message['text'].get('body', '')
                            elif 'button' in message:
                                message_text = message['button'].get('text', '')
                            elif 'interactive' in message:
                                interactive = message['interactive']
                                if 'button_reply' in interactive:
                                    message_text = interactive['button_reply'].get('title', '')
                                elif 'list_reply' in interactive:
                                    message_text = interactive['list_reply'].get('title', '')
                            
                            timestamp = message.get('timestamp')
                            app.logger.info(f"Mesaj kaydediliyor - ID: {message_id}, From: {from_number}, Text: {message_text}, Timestamp: {timestamp}")
                            
                            if message_id and from_number:
                                with get_db() as db:
                                    # Önce kişiyi kontrol et/ekle
                                    sql = '''
                                        INSERT OR IGNORE INTO contacts (phone, name, unread_count)
                                        VALUES (?, ?, 1)
                                    '''
                                    app.logger.info(f"Kişi SQL sorgusu: {sql} - Parametreler: {(from_number, f'Kişi {from_number}')}")
                                    db.execute(sql, (from_number, f"Kişi {from_number}"))
                                    app.logger.info(f"Kişi kaydedildi/güncellendi - Phone: {from_number}")
                                    
                                    # Mesajı kaydet
                                    sql = '''
                                        INSERT OR IGNORE INTO messages 
                                        (message_id, phone, name, message, direction, status, timestamp)
                                        VALUES (?, ?, ?, ?, 'incoming', 'received', datetime(?, 'unixepoch'))
                                    '''
                                    params = (message_id, from_number, f"Kişi {from_number}", message_text, timestamp)
                                    app.logger.info(f"Mesaj SQL sorgusu: {sql} - Parametreler: {params}")
                                    db.execute(sql, params)
                                    app.logger.info(f"Mesaj kaydedildi - ID: {message_id}")
                                    
                                    # Okunmamış mesaj sayısını güncelle
                                    sql = '''
                                        UPDATE contacts 
                                        SET unread_count = unread_count + 1
                                        WHERE phone = ?
                                    '''
                                    app.logger.info(f"Okunmamış sayacı SQL sorgusu: {sql} - Parametreler: {(from_number,)}")
                                    db.execute(sql, (from_number,))
                                    
                                    db.commit()
                                    app.logger.info("Veritabanı işlemleri tamamlandı")
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        app.logger.error(f"Webhook hatası: {str(e)}")
        app.logger.exception("Hata detayı:")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/messages')
@cache_response(messages_cache, 'messages')
def get_messages():
    try:
        with get_db() as db:
            messages = db.execute('''
                SELECT m.*, c.name as contact_name 
                FROM messages m 
                LEFT JOIN contacts c ON m.phone = c.phone 
                ORDER BY m.timestamp DESC
            ''').fetchall()
            
            return jsonify([dict(message) for message in messages])
    except Exception as e:
        app.logger.error(f"Mesajları getirme hatası: {str(e)}")
        return jsonify([])

@app.route('/api/message-status/<message_id>', methods=['GET'])
def get_message_status(message_id):
    try:
        with get_db() as db:
            message = db.execute('''
                SELECT status 
                FROM messages 
                WHERE message_id = ?
            ''', (message_id,)).fetchone()
            
            if message:
                return jsonify({"status": message['status']})
            else:
                return jsonify({"error": "Mesaj bulunamadı"}), 404
    except Exception as e:
        app.logger.error(f"Mesaj durumu alınırken hata: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'JSON verisi gerekli'})
            
        phone = data.get('phone')
        message = data.get('message')
        message_type = data.get('type', 'text')
        customer_id = data.get('customer_id')
        
        if not phone:
            return jsonify({'success': False, 'message': 'Telefon numarası gerekli'})
        
        if not message and message_type == 'text':
            return jsonify({'success': False, 'message': 'Mesaj içeriği gerekli'})
        
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
                        message_id, phone, name, message, direction, status, timestamp, customer_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message_id,
                    phone,
                    name,
                    message,
                    'outgoing',
                    'sent',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    customer_id
                ))
                db.commit()
            
            # Başarılı mesajı sent_messages.json'a kaydet
            save_sent_message(phone, customer_id)
            
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

# Global kuyruk ve thread havuzu
message_queue = queue.Queue()
message_threads = []

def process_message_queue():
    retry_count = 0
    max_retries = 3
    retry_delay = 1  # saniye
    
    while True:
        try:
            data = message_queue.get()
            if data is None:  # Durdurma sinyali
                break
                
            phone = data['phone']
            name = data['name']
            db = get_db()
            
            try:
                # Daha önce gönderilmiş mi kontrol et
                result = db.execute('''
                    SELECT COUNT(*) as count 
                    FROM messages 
                    WHERE phone = ? AND direction = 'outgoing' AND status = 'sent'
                    AND DATE(timestamp) = DATE('now')
                ''', (phone,)).fetchone()
                
                if result and result['count'] > 0:
                    print(f"Bu numaraya bugün zaten mesaj gönderilmiş: {phone} ({name})")
                    continue

                # pro_transfer şablonunu gönder
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

                print(f"Mesaj gönderiliyor: {phone} ({name})")
                response = requests.post(f"{BASE_URL}/messages", json=payload, headers=headers)
                response_data = response.json()
                
                if response.status_code == 200:
                    message_id = response_data.get('messages', [{}])[0].get('id')
                    
                    # Mesajı veritabanına kaydet
                    db.execute('''
                        INSERT INTO messages (
                            message_id, phone, name, message, direction, status, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        message_id,
                        phone,
                        name,
                        "pro_transfer şablonu gönderildi",
                        'outgoing',
                        'sent',
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    db.commit()
                    
                    print(f"Başarılı: {phone} ({name})")
                    retry_count = 0  # Başarılı gönderimde retry sayacını sıfırla
                else:
                    error_msg = response_data.get('error', {}).get('message', 'Bilinmeyen hata')
                    error_code = response_data.get('error', {}).get('code')
                    
                    if error_code in [131026, 131048]:  # Message undeliverable veya Spam Rate limit
                        if retry_count < max_retries:
                            retry_count += 1
                            print(f"Hata ({error_code}): {error_msg} - Yeniden deneniyor ({retry_count}/{max_retries})")
                            time.sleep(retry_delay)
                            message_queue.put(data)  # Mesajı kuyruğa geri ekle
                            continue
                    
                    print(f"Başarısız: {phone} ({name}) - Hata: {error_msg}")
                
            except Exception as e:
                print(f"Hata: {phone} ({name}) - {str(e)}")
            finally:
                db.close()
                
            # API rate limit için bekle - saniyede 10 mesaj için 0.1 saniye bekle
            time.sleep(0.1)  # 1/10 saniye
            
        except Exception as e:
            print(f"Kuyruk işleme hatası: {str(e)}")
        finally:
            message_queue.task_done()

@app.route('/send_bulk_messages', methods=['POST'])
def send_bulk_messages():
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'Dosya yüklenmedi'
            })

        file = request.files['file']
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({
                'success': False,
                'message': 'Geçersiz dosya formatı. Lütfen Excel dosyası yükleyin.'
            })

        # Geçici dosya oluştur
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Excel dosyasını oku - engine parametresini belirterek
            if filename.endswith('.xlsx'):
                df = pd.read_excel(filepath, engine='openpyxl')
            else:
                df = pd.read_excel(filepath, engine='xlrd')
            
            if 'phone' not in df.columns:
                os.remove(filepath)
                return jsonify({
                    'success': False,
                    'message': 'Excel dosyasında "phone" sütunu bulunamadı'
                })

            # Boş satırları temizle
            df = df.dropna(subset=['phone'])
            
            # Telefon numaralarını string'e çevir ve formatla
            df['phone'] = df['phone'].astype(str).apply(lambda x: '+' + x.strip().replace(' ', '').replace('-', '') if not x.startswith('+') else x)
            
            # İsim sütunu varsa kullan, yoksa telefon numarasını kullan
            if 'name' not in df.columns:
                df['name'] = df['phone'].apply(lambda x: f"Müşteri {x[-4:]}")

            # Veritabanı bağlantısı
            db = get_db()
            
            # Her numara için contacts tablosuna ekle
            for index, row in df.iterrows():
                phone = row['phone']
                name = row['name']
                
                # Kişiyi contacts tablosuna ekle
                db.execute('''
                    INSERT OR IGNORE INTO contacts (phone, name, unread_count)
                    VALUES (?, ?, 0)
                ''', (phone, name))
            
            db.commit()

            # Yeni worker thread başlat
            worker_thread = threading.Thread(target=process_message_queue, daemon=True)
            worker_thread.start()
            message_threads.append(worker_thread)

            # Numaraları kuyruğa ekle
            for index, row in df.iterrows():
                message_queue.put({
                    'phone': row['phone'],
                    'name': row['name']
                })

            # Geçici dosyayı sil
            os.remove(filepath)

            return jsonify({
                'success': True,
                'message': f'Toplu mesaj gönderme başlatıldı. {len(df)} numara işleme alındı.',
                'total_numbers': len(df)
            })

        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({
                'success': False,
                'message': f'Excel dosyası işlenirken hata oluştu: {str(e)}'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Bir hata oluştu: {str(e)}'
        })

@app.route('/api/mark_as_read', methods=['POST'])
@cache_response(mark_read_cache, 'mark_read')
def mark_as_read():
    try:
        data = request.json
        phone = data.get('phone')
        
        if not phone:
            return jsonify({"status": "error", "message": "Phone number is required"})
            
        cache_key = f"mark_read:{phone}"
        if cache_key in mark_read_cache:
            return jsonify({"status": "success", "message": "Already marked as read"})
            
        with get_db() as db:
            # Mesajları okundu olarak işaretle
            db.execute('UPDATE messages SET is_read = 1 WHERE phone = ?', (phone,))
            # Okunmamış mesaj sayacını sıfırla
            db.execute('UPDATE contacts SET unread_count = 0 WHERE phone = ?', (phone,))
            db.commit()
            
        mark_read_cache[cache_key] = True
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error(f"Okundu işaretleme hatası: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

# Okunmamış mesaj sayısını getir
@app.route('/api/unread_count', methods=['GET'])
def get_unread_count():
    try:
        with get_db() as db:
            # Tüm kişilerin okunmamış mesaj sayılarını getir
            cursor = db.execute('''
                SELECT c.phone, c.name, c.unread_count 
                FROM contacts c 
                WHERE c.unread_count > 0 
                ORDER BY c.unread_count DESC
            ''')
            
            unread_counts = []
            for row in cursor.fetchall():
                unread_counts.append({
                    "phone": row['phone'],
                    "name": row['name'],
                    "unread_count": row['unread_count']
                })
            
            return jsonify({"status": "success", "data": unread_counts}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/send', methods=['POST'])
def send():
    try:
        numbers = load_numbers_from_excel()
        results = []
        for phone, customer_id in numbers:
            success = send_message(phone, customer_id)
            results.append({
                'phone': phone,
                'customer_id': customer_id,
                'status': 'success' if success else 'failed'
            })
        return jsonify({'status': 'success', 'results': results})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/load_excel', methods=['GET'])
def load_excel():
    try:
        # Excel dosyasını oku
        df = pd.read_excel('aktif2_1-3500.xlsx')
        
        # Her numara için veritabanına ekle
        for _, row in df.iterrows():
            number = str(row['Numara'])
            message = str(row['Mesaj'])  # aktif2 mesajı
            
            # Veritabanına ekle
            cursor = get_db().cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO messages 
                (phone, message, direction, timestamp, is_read, name, status)
                VALUES (?, ?, 'outgoing', datetime('now'), 1, ?, 'sent')
            ''', (number, message, f'Müşteri {number}'))
            
            # Kişiyi contacts tablosuna ekle
            cursor.execute('''
                INSERT OR IGNORE INTO contacts 
                (phone, name, unread_count)
                VALUES (?, ?, 0)
            ''', (number, f'Müşteri {number}'))
            
        get_db().commit()
        return jsonify({'status': 'success', 'message': 'Excel dosyası başarıyla yüklendi'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # templates klasörü yoksa oluştur
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(host='0.0.0.0', port=3000, debug=True)