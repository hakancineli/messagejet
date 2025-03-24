#!/bin/bash

# Webhook URL'sini güncelle
update_webhook() {
    local webhook_url="$1"
    
    echo "Webhook URL güncelleniyor: $webhook_url"
    
    curl -s -X POST -H "D360-API-KEY: MISyrZTxjZFZTH52tF8M7hwSAK" \
        -H "Content-Type: application/json" \
        -d "{\"url\":\"$webhook_url\"}" \
        https://waba-v2.360dialog.io/configs/webhook
}

# MessageJet'i başlat
start() {
    echo "MessageJet başlatılıyor..."
    
    # Önce tüm işlemleri durdur
    pkill -f "python3 app.py"
    pkill ngrok
    pkill -f "lt --port"
    sleep 2
    
    # Flask uygulamasını başlat
    python3 app.py > flask.log 2>&1 &
    sleep 2
    
    # Localtunnel'ı başlat
    lt --port 3000 > tunnel.log 2>&1 &
    sleep 5
    
    # Localtunnel URL'sini al
    tunnel_url=$(grep -o 'https://.*\.loca\.lt' tunnel.log | head -n 1)
    
    if [ -n "$tunnel_url" ]; then
        # Webhook URL'sini güncelle
        webhook_url="${tunnel_url}/webhook"
        update_webhook "$webhook_url"
        echo "MessageJet başlatıldı!"
        echo "Tunnel URL: $tunnel_url"
        echo "Webhook URL: $webhook_url"
    else
        echo "Hata: Tunnel URL alınamadı!"
        stop
        exit 1
    fi
}

# MessageJet'i durdur
stop() {
    echo "MessageJet durduruluyor..."
    pkill -f "python3 app.py"
    pkill ngrok
    pkill -f "lt --port"
    echo "MessageJet durduruldu!"
}

# MessageJet'i yeniden başlat
restart() {
    stop
    sleep 2
    start
}

# Komut satırı parametrelerini kontrol et
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart}"
        exit 1
        ;;
esac

exit 0 