from flask import Flask, render_template, request, jsonify
import os
import sqlite3
from datetime import datetime
import json

app = Flask(__name__)

# Veritabanı bağlantısı
def get_db():
    db = sqlite3.connect('messagejet.db')
    db.row_factory = sqlite3.Row
    return db

# Veritabanı tablolarını oluştur
def init_db():
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
        
        # WhatsApp API'den gelen veriyi işle
        if 'messages' in data and len(data['messages']) > 0:
            message = data['messages'][0]
            phone = message.get('from', '')
            text = message.get('text', {}).get('body', '')
            
            # Mesajı veritabanına kaydet
            db = get_db()
            db.execute(
                'INSERT INTO messages (phone, message, message_type, status) VALUES (?, ?, ?, ?)',
                (phone, text, 'incoming', 'received')
            )
            db.commit()
            
            return jsonify({"success": True, "message": "Message saved"})
        
        return jsonify({"success": True, "message": "No message data"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)