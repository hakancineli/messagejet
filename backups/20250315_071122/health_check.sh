#!/bin/bash

check_process() {
    if pgrep -f "$1" > /dev/null; then
        echo "✅ $2 çalışıyor"
        return 0
    else
        echo "❌ $2 çalışmıyor!"
        return 1
    fi
}

check_port() {
    if lsof -i :$1 > /dev/null; then
        echo "✅ Port $1 aktif"
        return 0
    else
        echo "❌ Port $1 kapalı!"
        return 1
    fi
}

check_ngrok_url() {
    if curl -s http://localhost:4040/api/tunnels | grep -q "ngrok-free.app"; then
        echo "✅ Ngrok URL aktif"
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o "https://[^\"]*\.ngrok-free\.app")
        echo "   URL: $NGROK_URL"
        return 0
    else
        echo "❌ Ngrok URL bulunamadı!"
        return 1
    fi
}

check_webhook() {
    WEBHOOK_RESPONSE=$(curl -s -H "D360-API-KEY: MISyrZTxjZFZTH52tF8M7hwSAK" https://waba-v2.360dialog.io/configs/webhook)
    if echo "$WEBHOOK_RESPONSE" | grep -q "url"; then
        echo "✅ Webhook yapılandırması aktif"
        echo "   $WEBHOOK_RESPONSE"
        return 0
    else
        echo "❌ Webhook yapılandırması hatalı!"
        return 1
    fi
}

echo "=== MessageJet Sistem Kontrolü ==="
echo "Tarih: $(date)"
echo "------------------------"

ERRORS=0

check_process "python3 app.py" "Flask uygulaması" || ((ERRORS++))
check_port "3002" || ((ERRORS++))
check_process "ngrok http 3002" "Ngrok" || ((ERRORS++))
check_ngrok_url || ((ERRORS++))
check_webhook || ((ERRORS++))

echo "------------------------"
if [ $ERRORS -eq 0 ]; then
    echo "✅ Tüm sistemler normal çalışıyor!"
else
    echo "❌ $ERRORS adet sorun tespit edildi!"
    echo "Sistemi yeniden başlatmak için: ./messagejet.sh restart"
fi 