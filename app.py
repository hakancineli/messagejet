from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, DateTime, MetaData, Table
from sqlalchemy.sql import select
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)

# PostgreSQL bağlantı URL'i
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/messagejet')

# SQLAlchemy engine
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Mesajlar tablosu tanımı
messages = Table(
    'messages', 
    metadata,
    Column('id', Integer, primary_key=True),
    Column('phone', String, nullable=False),
    Column('message', String, nullable=False),
    Column('timestamp', DateTime, default=datetime.utcnow),
    Column('message_type', String),
    Column('status', String)
)

# Veritabanı tablolarını oluştur
def init_db():
    print("Veritabanı tabloları oluşturuluyor...")
    try:
        metadata.create_all(engine)
        print("Veritabanı tabloları başarıyla oluşturuldu.")
    except Exception as e:
        print(f"Veritabanı oluşturma hatası: {str(e)}")

# Uygulama başlangıcında gerekli dizinleri oluştur
for directory in ['templates', 'uploads', 'data']:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Veritabanını başlat
init_db()

@app.route('/')
def index():
    try:
        with engine.connect() as conn:
            result = conn.execute(select(messages).order_by(messages.c.timestamp.desc()))
            message_list = [dict(row) for row in result]
            return render_template('index.html', messages=message_list)
    except Exception as e:
        print(f"Veritabanı okuma hatası: {str(e)}")
        return render_template('index.html', messages=[])

@app.route('/messages')
def get_messages():
    try:
        with engine.connect() as conn:
            result = conn.execute(select(messages).order_by(messages.c.timestamp.desc()))
            message_list = [dict(row) for row in result]
            # datetime objelerini string'e çevir
            for msg in message_list:
                msg['timestamp'] = msg['timestamp'].isoformat() if msg['timestamp'] else None
            return jsonify(message_list)
    except Exception as e:
        print(f"Veritabanı okuma hatası: {str(e)}")
        return jsonify([])

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
            try:
                with engine.connect() as conn:
                    conn.execute(
                        messages.insert().values(
                            phone=phone,
                            message=text,
                            message_type='incoming',
                            status='received',
                            timestamp=datetime.utcnow()
                        )
                    )
                    conn.commit()
                print("Mesaj veritabanına kaydedildi")
                return jsonify({"success": True, "message": "Message saved"})
            except Exception as e:
                print(f"Veritabanı yazma hatası: {str(e)}")
                return jsonify({"success": False, "error": f"Database error: {str(e)}"}), 500
        
        return jsonify({"success": True, "message": "No message data"})
    except Exception as e:
        print(f"Webhook hatası: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)