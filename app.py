from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

# Gerekli dizinleri oluştur
for directory in ['templates', 'uploads', 'data']:
    if not os.path.exists(directory):
        os.makedirs(directory)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    return jsonify({"status": "ok"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        return jsonify({"success": True, "message": "Data received"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)