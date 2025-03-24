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

check_database() {
    if [ -f "messagejet.db" ]; then
        DB_SIZE=$(ls -lh messagejet.db | awk '{print $5}')
        echo "✅ Veritabanı mevcut (Boyut: $DB_SIZE)"
        echo "   Son mesajlar:"
        sqlite3 messagejet.db "SELECT datetime(timestamp, 'localtime') as time, direction, status FROM messages ORDER BY timestamp DESC LIMIT 3;"
        return 0
    else
        echo "❌ Veritabanı dosyası bulunamadı!"
        return 1
    fi
}

check_logs() {
    for log in output.log error.log ngrok.log; do
        if [ -f "$log" ] && [ -w "$log" ]; then
            echo "✅ $log dosyası yazılabilir"
        else
            echo "❌ $log dosyası yazılamıyor!"
            return 1
        fi
    done
    return 0
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
check_database || ((ERRORS++))
check_logs || ((ERRORS++))

echo "------------------------"
if [ $ERRORS -eq 0 ]; then
    echo "✅ Tüm sistemler normal çalışıyor!"
else
    echo "❌ $ERRORS adet sorun tespit edildi!"
    echo "Sistemi yeniden başlatmak için: ./messagejet.sh restart"
fi 