from flask import Flask, render_template, jsonify, request
import os

app = Flask(__name__)

# Dizinleri oluştur
os.makedirs('templates', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('data', exist_ok=True)

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
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)