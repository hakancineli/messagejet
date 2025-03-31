from flask import Flask, render_template, request, jsonify
import os
import sqlite3
from datetime import datetime
import json

app = Flask(__name__)

# Veritabanı dizini ve dosya yolu
DB_DIR = 'data'
DB_FILE = os.path.join(DB_DIR, 'messagejet.db')

# Veritabanı bağlantısı
def get_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    return db

# Veritabanı tablolarını oluştur
def init_db():
    print("Veritabanı tabloları oluşturuluyor...")
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT,
                status TEXT
            )
        ''')
        db.commit()
    print("Veritabanı tabloları başarıyla oluşturuldu.")
    print(f"Veritabanı dosyası: {DB_FILE}")

# Uygulama başlangıcında gerekli dizinleri ve veritabanını oluştur
for directory in ['templates', 'uploads', 'data']:
    if not os.path.exists(directory):
        os.makedirs(directory)
init_db()

@app.route('/')
def index():
    db = get_db()
    messages = db.execute('SELECT * FROM messages ORDER BY timestamp DESC').fetchall()
    return render_template('index.html', messages=messages)

@app.route('/messages')
def get_messages():
    db = get_db()
    messages = db.execute('SELECT * FROM messages ORDER BY timestamp DESC').fetchall()
    return jsonify([dict(msg) for msg in messages])

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    return jsonify({"status": "ok"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        print(f"Gelen webhook verisi: {json.dumps(data, indent=2)}")
        
        # WhatsApp API'den gelen veriyi işle
        if 'messages' in data and len(data['messages']) > 0:
            message = data['messages'][0]
            phone = message.get('from', '')
            text = message.get('text', {}).get('body', '')
            
            print(f"Mesaj alındı - Telefon: {phone}, Mesaj: {text}")
            
            # Mesajı veritabanına kaydet
            db = get_db()
            db.execute(
                'INSERT INTO messages (phone, message, message_type, status) VALUES (?, ?, ?, ?)',
                (phone, text, 'incoming', 'received')
            )
            db.commit()
            
            print("Mesaj veritabanına kaydedildi")
            return jsonify({"success": True, "message": "Message saved"})
        
        return jsonify({"success": True, "message": "No message data"})
    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))  # Varsayılan portu 8080 olarak değiştirdim
    app.run(host='0.0.0.0', port=port, debug=True)  # Debug modunu aktif ettim