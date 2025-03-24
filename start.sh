#!/bin/bash

# Eski ngrok işlemlerini sonlandır
pkill -f ngrok

# PM2 ile uygulamayı başlat
pm2 start server.js --name messagejet

# Sunucunun başlaması için 5 saniye bekle
sleep 5

# Ngrok ile 3000 portunu public yap ve URL'yi al
NGROK_URL=$(ngrok http 3000 --log=stdout > /dev/null 2>&1 & sleep 5 && curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

# Webhook URL'sini oluştur
WEBHOOK_URL="${NGROK_URL}/webhook"

# Webhook URL'sini güncelle
curl -X POST http://localhost:3000/api/update-webhook \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$WEBHOOK_URL\"}"

echo "Webhook URL: $WEBHOOK_URL"
echo "Uygulama başlatıldı!" 