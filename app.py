from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, DateTime, MetaData, Table
from sqlalchemy.sql import select
from sqlalchemy.orm import sessionmaker
import logging

# Logging yapılandırması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# PostgreSQL bağlantı URL'i
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set!")
    DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/messagejet'
elif DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

logger.info(f"Using database URL: {DATABASE_URL.split('@')[1]}")  # URL'in hassas olmayan kısmını logla

try:
    # SQLAlchemy engine
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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

    # Test connection
    with engine.connect() as conn:
        conn.execute(select(1))
        logger.info("Database connection successful")
except Exception as e:
    logger.error(f"Database connection error: {str(e)}")
    raise

# Veritabanı tablolarını oluştur
def init_db():
    logger.info("Creating database tables...")
    try:
        metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database creation error: {str(e)}")
        raise

# Uygulama başlangıcında gerekli dizinleri oluştur
for directory in ['templates', 'uploads', 'data']:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

# Veritabanını başlat
init_db()

@app.route('/')
def index():
    try:
        with engine.connect() as conn:
            result = conn.execute(select(messages).order_by(messages.c.timestamp.desc()))
            message_list = [dict(row) for row in result]
            logger.info(f"Retrieved {len(message_list)} messages")
            return render_template('index.html', messages=message_list)
    except Exception as e:
        logger.error(f"Database read error: {str(e)}")
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
            logger.info(f"Retrieved {len(message_list)} messages for API")
            return jsonify(message_list)
    except Exception as e:
        logger.error(f"Database read error: {str(e)}")
        return jsonify([])

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    return jsonify({"status": "ok"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Log request headers
        logger.info(f"Received webhook request from: {request.headers.get('X-Forwarded-For', 'Unknown')}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        data = request.get_json()
        logger.info(f"Webhook data received: {json.dumps(data, indent=2)}")
        
        # WhatsApp API'den gelen veriyi işle
        if 'messages' in data and len(data['messages']) > 0:
            message = data['messages'][0]
            phone = message.get('from', '')
            text = message.get('text', {}).get('body', '')
            
            logger.info(f"Message received - Phone: {phone}, Message: {text}")
            
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
                logger.info("Message saved to database")
                return jsonify({"success": True, "message": "Message saved"})
            except Exception as e:
                logger.error(f"Database write error: {str(e)}")
                return jsonify({"success": False, "error": f"Database error: {str(e)}"}), 500
        
        return jsonify({"success": True, "message": "No message data"})
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)