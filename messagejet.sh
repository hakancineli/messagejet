#!/bin/bash

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Log dosyaları
FLASK_LOG="flask.log"
TUNNEL_LOG="tunnel.log"

# Fonksiyonlar
check_dependencies() {
    echo -e "${YELLOW}Bağımlılıklar kontrol ediliyor...${NC}"
    
    # Python kontrolü
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python3 bulunamadı. Lütfen Python3'ü yükleyin.${NC}"
        exit 1
    fi
    
    # pip kontrolü
    if ! command -v pip3 &> /dev/null; then
        echo -e "${RED}pip3 bulunamadı. Lütfen pip3'ü yükleyin.${NC}"
        exit 1
    fi
    
    # localtunnel kontrolü
    if ! command -v lt &> /dev/null; then
        echo -e "${YELLOW}Localtunnel bulunamadı. Yükleniyor...${NC}"
        npm install -g localtunnel
    fi
    
    # Python bağımlılıkları kontrolü
    if ! pip3 list | grep -q "Flask"; then
        echo -e "${YELLOW}Flask yükleniyor...${NC}"
        pip3 install Flask
    fi
    
    if ! pip3 list | grep -q "requests"; then
        echo -e "${YELLOW}Requests yükleniyor...${NC}"
        pip3 install requests
    fi
    
    if ! pip3 list | grep -q "cachetools"; then
        echo -e "${YELLOW}Cachetools yükleniyor...${NC}"
        pip3 install cachetools
    fi
}

stop_processes() {
    echo -e "${YELLOW}Mevcut süreçler durduruluyor...${NC}"
    
    # Flask süreçlerini durdur
    pkill -f "python3 app.py" || true
    
    # Localtunnel süreçlerini durdur
    pkill -f "lt --port 3000" || true
    
    # Port 3000'i kullanan tüm süreçleri durdur
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    
    echo -e "${GREEN}Tüm süreçler durduruldu.${NC}"
}

start_flask() {
    echo -e "${YELLOW}Flask uygulaması başlatılıyor...${NC}"
    python3 app.py > "$FLASK_LOG" 2>&1 &
    sleep 3
    
    if grep -q "Running on" "$FLASK_LOG"; then
        echo -e "${GREEN}Flask uygulaması başlatıldı.${NC}"
        return 0
    else
        echo -e "${RED}Flask uygulaması başlatılamadı. Logları kontrol edin: $FLASK_LOG${NC}"
        return 1
    fi
}

start_tunnel() {
    echo -e "${YELLOW}Localtunnel başlatılıyor...${NC}"
    lt --port 3000 > "$TUNNEL_LOG" 2>&1 &
    sleep 3
    
    # Tunnel URL'ini al
    TUNNEL_URL=$(grep -o "https://.*\.loca\.lt" "$TUNNEL_LOG" | head -n 1)
    
    if [ -n "$TUNNEL_URL" ]; then
        echo -e "${GREEN}Localtunnel başlatıldı: $TUNNEL_URL${NC}"
        update_webhook "$TUNNEL_URL/webhook"
        return 0
    else
        echo -e "${RED}Localtunnel başlatılamadı. Logları kontrol edin: $TUNNEL_LOG${NC}"
        return 1
    fi
}

update_webhook() {
    local webhook_url=$1
    echo -e "${YELLOW}Webhook URL güncelleniyor: $webhook_url${NC}"
    
    # API anahtarını app.py'den al
    API_KEY=$(grep -o 'API_KEY = "[^"]*"' app.py | cut -d'"' -f2)
    
    if [ -z "$API_KEY" ]; then
        echo -e "${RED}API anahtarı bulunamadı!${NC}"
        return 1
    fi
    
    # Webhook URL'ini güncelle
    curl -X POST "https://waba-v2.360dialog.io/v1/configs/webhook" \
        -H "D360-API-KEY: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"url\":\"$webhook_url\"}"
    
    echo -e "${GREEN}Webhook URL güncellendi.${NC}"
}

start() {
    echo -e "${YELLOW}MessageJet başlatılıyor...${NC}"
    
    check_dependencies
    stop_processes
    
    start_flask
    if [ $? -ne 0 ]; then
        echo -e "${RED}MessageJet başlatılamadı.${NC}"
        exit 1
    fi
    
    start_tunnel
    if [ $? -ne 0 ]; then
        echo -e "${RED}MessageJet başlatılamadı.${NC}"
        stop_processes
        exit 1
    fi
    
    echo -e "${GREEN}MessageJet başarıyla başlatıldı!${NC}"
    echo -e "${YELLOW}Arayüz: ${NC}http://localhost:3000"
    echo -e "${YELLOW}Flask log: ${NC}$FLASK_LOG"
    echo -e "${YELLOW}Tunnel log: ${NC}$TUNNEL_LOG"
}

stop() {
    echo -e "${YELLOW}MessageJet durduruluyor...${NC}"
    stop_processes
    echo -e "${GREEN}MessageJet durduruldu.${NC}"
}

restart() {
    echo -e "${YELLOW}MessageJet yeniden başlatılıyor...${NC}"
    stop
    sleep 2
    start
}

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