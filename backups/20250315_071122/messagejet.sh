#!/bin/bash

start() {
    echo "MessageJet başlatılıyor..."
    pkill -f "python3 app.py"
    pkill -f "ngrok http 3002"
    sleep 2
    cd /Users/hakancineli/Desktop/messagejet_gider-gelen
    python3 app.py > output.log 2> error.log &
    sleep 2
    ngrok http 3002 > ngrok.log 2>&1 &
    sleep 5
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o "https://[^\"]*\.ngrok-free\.app")
    curl -X POST -H "D360-API-KEY: MISyrZTxjZFZTH52tF8M7hwSAK" -H "Content-Type: application/json" -d "{\"url\":\"$NGROK_URL/webhook\"}" https://waba-v2.360dialog.io/configs/webhook
    echo "MessageJet başlatıldı!"
    echo "Ngrok URL: $NGROK_URL"
}

stop() {
    echo "MessageJet durduruluyor..."
    pkill -f "python3 app.py"
    pkill -f "ngrok http 3002"
    echo "MessageJet durduruldu!"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart}"
        exit 1
        ;;
esac
