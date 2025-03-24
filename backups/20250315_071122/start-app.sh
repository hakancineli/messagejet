#!/bin/bash

# Ngrok'u başlat
ngrok http 3000 > /dev/null 2>&1 &

# 5 saniye bekle (ngrok'un başlaması için)
sleep 5

# Ngrok URL'sini al
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o "https://[^\"]*")

# Webhook URL'sini ayarla
export WEBHOOK_BASE_URL=$NGROK_URL

# Uygulamayı PM2 ile başlat
pm2 delete messagejet 2>/dev/null || true
pm2 start server.js --name messagejet

# Tarayıcıyı aç
open http://localhost:3000 