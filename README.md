# WhatsApp Template Message Sender

Bu proje, WhatsApp üzerinden toplu template mesaj gönderimi yapmak için geliştirilmiş bir Python uygulamasıdır.

## Özellikler

- Excel dosyasından toplu numara okuma
- WhatsApp template mesajları gönderme
- Başarılı/başarısız mesajları takip etme
- Veritabanına kayıt
- Detaylı raporlama

## Gereksinimler

- Python 3.x
- pandas
- requests
- openpyxl

## Kurulum

1. Projeyi klonlayın:
```bash
git clone https://github.com/kullaniciadi/whatsapp-template-sender.git
cd whatsapp-template-sender
```

2. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

3. API anahtarınızı ayarlayın:
- `send_template_message.py` dosyasında `API_KEY` değişkenini güncelleyin

## Kullanım

1. Excel dosyanızı hazırlayın:
   - İki sütun olmalı: `number` ve `name`
   - Numara formatı: 20101XXXXXX şeklinde olmalı

2. Scripti çalıştırın:
```bash
python3 send_template_message.py
```

## Sonuçlar

- Başarılı mesajlar: `template_results.json`
- Başarısız mesajlar: `failed_messages.xlsx`

## Lisans

MIT 