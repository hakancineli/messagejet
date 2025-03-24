const express = require("express");
const app = express();
const axios = require("axios");
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const multer = require('multer');
const fs = require('fs');

// Environment variables
const PORT = process.env.PORT || 3000;
const API_KEY = process.env.API_KEY || 'MISyrZTxjZFZTH52tF8M7hwSAK';
const API_BASE_URL = process.env.API_BASE_URL || 'https://waba-v2.360dialog.io';
let WEBHOOK_BASE_URL = process.env.WEBHOOK_BASE_URL;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// SQLite veritabanı bağlantısı
const db = new sqlite3.Database('./messages.db', (err) => {
  if (err) {
    console.error('Veritabanı bağlantı hatası:', err.message);
  } else {
    console.log('Veritabanına bağlandı');
    
    // Mesajlar tablosunu kontrol et ve güncelle
    db.run(`CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      phone TEXT,
      message TEXT,
      direction TEXT,
      timestamp DATETIME DEFAULT (datetime('now', '+3 hours')),
      status TEXT DEFAULT 'sent',
      whatsapp_message_id TEXT,
      media_type TEXT,
      media_url TEXT,
      media_filename TEXT,
      media_filesize TEXT
    )`, [], (err) => {
      if (err) {
        console.error('Tablo oluşturma hatası:', err);
        return;
      }
    });
    
    // Kişiler tablosunu oluştur
    db.run(`CREATE TABLE IF NOT EXISTS contacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      phone TEXT UNIQUE,
      name TEXT,
      profile_name TEXT,
      is_greeted INTEGER DEFAULT 0,
      timestamp TEXT DEFAULT (datetime('now', '+3 hours')),
      last_message_timestamp TEXT DEFAULT (datetime('now', '+3 hours'))
    )`);
  }
});

// Medya dosyaları için klasör oluştur
const uploadDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir);
}

// Multer yapılandırması
const storage = multer.diskStorage({
    destination: function(req, file, cb) {
        cb(null, uploadDir);
    },
    filename: function(req, file, cb) {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + path.extname(file.originalname));
    }
});

const upload = multer({
    storage: storage,
    limits: {
        fileSize: 10 * 1024 * 1024 // 10MB
    }
});

// Webhook URL'sini ayarla
async function setupWebhook() {
  if (!WEBHOOK_BASE_URL) {
    console.log('WEBHOOK_BASE_URL environment variable not set. Skipping webhook setup.');
    return;
  }

  const webhookUrl = `${WEBHOOK_BASE_URL}/webhook`;
  
  try {
    const response = await axios({
      method: 'POST',
      url: `${API_BASE_URL}/configs/webhook`,
      headers: {
        'Content-Type': 'application/json',
        'D360-API-KEY': API_KEY
      },
      data: {
        url: webhookUrl,
        headers: {}
      }
    });
    
    console.log('Webhook URL başarıyla kaydedildi:', webhookUrl);
    console.log('API yanıtı:', response.data);
  } catch (error) {
    console.error('Webhook URL kaydı başarısız:', error.message);
  }
}

// Webhook URL'sini al
app.get('/api/webhook-url', (req, res) => {
  res.json({ url: WEBHOOK_BASE_URL });
});

// Webhook URL'sini güncelle
app.post('/api/update-webhook', async (req, res) => {
  try {
    const { url } = req.body;
    
    if (!url) {
      return res.status(400).json({ success: false, error: 'URL gerekli' });
    }
    
    // 360dialog API'sine webhook URL'sini güncelle
    const response = await axios({
      method: 'POST',
      url: `${API_BASE_URL}/configs/webhook`,
      headers: {
        'Content-Type': 'application/json',
        'D360-API-KEY': API_KEY
      },
      data: {
        url: url,
        headers: {}
      }
    });
    
    // Başarılı olursa URL'yi sakla
    WEBHOOK_BASE_URL = url;
    
    console.log('Webhook URL güncellendi:', url);
    console.log('API yanıtı:', response.data);
    
    res.json({ success: true, response: response.data });
  } catch (error) {
    console.error('Webhook güncelleme hatası:', error.response ? error.response.data : error.message);
    res.status(500).json({ 
      success: false, 
      error: error.response ? JSON.stringify(error.response.data) : error.message 
    });
  }
});

// Ana sayfa
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Tüm mesajları getir
app.get('/api/messages', (req, res) => {
  const phone = req.query.phone;
  let query = `
    SELECT 
      id,
      phone,
      message,
      direction,
      datetime(timestamp, '+3 hours') as timestamp,
      status,
      whatsapp_message_id,
      media_type,
      media_url,
      media_filename,
      media_filesize
    FROM messages
  `;
  let params = [];

  if (phone) {
    const standardizedPhone = standardizePhoneNumber(phone);
    query += ' WHERE phone = ?';
    params.push(standardizedPhone);
  }

  query += ' ORDER BY timestamp ASC'; // Eskiden yeniye sıralama

  db.all(query, params, (err, messages) => {
    if (err) {
      console.error('Mesajları getirme hatası:', err);
      return res.status(500).json({ error: 'Mesajlar alınırken hata oluştu' });
    }
    res.json(messages);
  });
});

// Tek bir kişiyi getir
app.get('/api/contacts/:phone', (req, res) => {
    const phone = standardizePhoneNumber(req.params.phone);
    
    db.get(
        'SELECT phone, name, last_message_timestamp FROM contacts WHERE phone = ?',
        [phone],
        (err, contact) => {
            if (err) {
                console.error('Kişi getirme hatası:', err);
                return res.status(500).json({ error: 'Kişi alınırken hata oluştu' });
            }
            
            if (!contact) {
                // Kişi bulunamadıysa sadece telefon numarasını döndür
                return res.json({ phone: phone, name: null });
            }
            
            res.json(contact);
        }
    );
});

// Kişileri getir
app.get('/api/contacts', (req, res) => {
  db.all(`
    SELECT 
      phone,
      name,
      profile_name,
      COALESCE(last_message_timestamp, timestamp) as last_message_timestamp
    FROM contacts
    ORDER BY last_message_timestamp DESC
  `, [], (err, contacts) => {
      if (err) {
      console.error('Kişileri getirme hatası:', err);
      return res.status(500).json({ error: 'Kişiler alınırken hata oluştu' });
    }

    // Tüm telefon numaralarını standart formata çevir
    contacts = contacts.map(contact => ({
      ...contact,
      phone: standardizePhoneNumber(contact.phone)
    }));

    console.log('Bulunan kişiler:', contacts); // Debug için log ekledim
    res.json(contacts);
  });
});

// Telefon numarasını standart formata çeviren yardımcı fonksiyon
function standardizePhoneNumber(phone) {
    // Boşlukları ve tire işaretlerini kaldır
    phone = phone.replace(/[\s-]/g, '');
    
    // Eğer + ile başlamıyorsa ekle
    if (!phone.startsWith('+')) {
        phone = '+' + phone;
    }
    
    return phone;
}

// Kişi ekle/düzenle
app.post('/api/contacts', (req, res) => {
  const { phone, name } = req.body;
  if (!phone) {
    return res.status(400).json({ error: 'Telefon numarası gerekli' });
  }

  const standardizedPhone = standardizePhoneNumber(phone);
  
  // Önce kişinin var olup olmadığını kontrol et
  db.get('SELECT * FROM contacts WHERE phone = ?', [standardizedPhone], (err, row) => {
      if (err) {
        console.error('Kişi kontrol hatası:', err);
      return res.status(500).json({ error: 'Kişi kontrol edilirken hata oluştu' });
    }

    const query = row 
      ? 'UPDATE contacts SET name = ? WHERE phone = ?' 
      : 'INSERT INTO contacts (phone, name) VALUES (?, ?)';
    
    const params = row ? [name, standardizedPhone] : [standardizedPhone, name];

    db.run(query, params, function(err) {
            if (err) {
        console.error('Kişi ekleme/güncelleme hatası:', err);
        return res.status(500).json({ error: 'Kişi eklenirken/güncellenirken hata oluştu' });
      }
      res.json({ 
        success: true,
        id: this.lastID || row?.id, 
        phone: standardizedPhone, 
        name 
      });
    });
  });
});

// Kişi sil (sadece kullanıcının verdiği ismi sil)
app.delete('/api/contacts/:phone', (req, res) => {
  const phone = req.params.phone;
  
  // Kişinin ismini sil, diğer bilgileri koru
  db.run(
    `UPDATE contacts SET name = NULL WHERE phone = ?`,
    [phone],
    function(err) {
      if (err) {
        console.error('Kişi silme hatası:', err);
        return res.status(500).json({ success: false, error: err.message });
      }
      res.json({ success: true });
    }
  );
});

// Mesaj durumunu kontrol et
app.get('/api/message-status/:messageId', (req, res) => {
    const messageId = req.params.messageId;
    
        db.get(
        `SELECT m.id, m.whatsapp_message_id, m.status, m.timestamp,
         datetime(m.timestamp, '+3 hours') as formatted_timestamp
         FROM messages m
         WHERE m.id = ? OR m.whatsapp_message_id = ?`,
        [messageId, messageId],
        (err, row) => {
            if (err) {
                console.error('Mesaj durumu kontrol hatası:', err);
                return res.status(500).json({ error: err.message });
            }
            
            if (!row) {
                return res.status(404).json({ error: 'Mesaj bulunamadı' });
            }
            
            // Durumu kontrol et ve yanıtı hazırla
            const response = {
                id: row.id,
                whatsapp_message_id: row.whatsapp_message_id,
                status: row.status,
                timestamp: row.formatted_timestamp,
                statusInfo: {
                    code: row.status,
                    description: getStatusDescription(row.status)
                }
            };
            
            res.json(response);
        }
    );
});

// Mesaj durumu açıklamalarını getir
function getStatusDescription(status) {
    switch (status) {
        case 'sent':
            return 'Mesaj gönderildi';
        case 'delivered':
            return 'Mesaj iletildi';
        case 'seen':
            return 'Mesaj okundu';
        case 'failed':
            return 'Mesaj gönderilemedi';
        default:
            return 'Bilinmeyen durum';
    }
}

// Mesaj durumunu güncelle
app.post('/api/update-message-status', (req, res) => {
    const { messageId, status } = req.body;
    
    if (!messageId || !status) {
        return res.status(400).json({ error: 'messageId ve status gerekli' });
    }
    
              db.run(
        `UPDATE messages SET status = ? WHERE id = ?`,
        [status, messageId],
                function(err) {
                  if (err) {
                console.error('Mesaj durumu güncelleme hatası:', err);
                return res.status(500).json({ error: err.message });
            }
            res.json({ success: true });
        }
    );
});

// Medya gönderme endpoint'i
app.post('/api/send-media', upload.single('file'), async (req, res) => {
    try {
        const { phone, type, caption } = req.body;
        const file = req.file;
        
        if (!file) {
            return res.status(400).json({ success: false, error: 'Dosya bulunamadı' });
        }

        // Dosya boyutu kontrolü
        const maxSizes = {
            'audio': 16 * 1024 * 1024,    // 16MB
            'document': 100 * 1024 * 1024, // 100MB
            'image': 5 * 1024 * 1024,      // 5MB
            'video': 16 * 1024 * 1024     // 16MB
        };

        if (file.size > maxSizes[type]) {
            return res.status(400).json({ 
                success: false, 
                error: `Dosya boyutu ${formatFileSize(maxSizes[type])} boyutundan küçük olmalıdır` 
            });
        }
        
        // Telefon numarasını standartlaştır
        const formattedPhone = standardizePhoneNumber(phone);

        // MIME type kontrolü ve ayarlaması
        const mimeTypes = {
            'audio': ['audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg', 'audio/opus'],
            'document': ['application/pdf', 'application/msword', 'application/vnd.ms-powerpoint', 
                        'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/plain'],
            'image': ['image/jpeg', 'image/png'],
            'video': ['video/mp4', 'video/3gpp']
        };

        // Dosya uzantısına göre MIME type belirle
        const ext = path.extname(file.originalname).toLowerCase();
        let contentType;
        switch(ext) {
            case '.pdf': contentType = 'application/pdf'; break;
            case '.doc': contentType = 'application/msword'; break;
            case '.docx': contentType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'; break;
            case '.xls': contentType = 'application/vnd.ms-excel'; break;
            case '.xlsx': contentType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'; break;
            case '.ppt': contentType = 'application/vnd.ms-powerpoint'; break;
            case '.pptx': contentType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'; break;
            case '.txt': contentType = 'text/plain'; break;
            case '.jpg':
            case '.jpeg': contentType = 'image/jpeg'; break;
            case '.png': contentType = 'image/png'; break;
            case '.mp4': contentType = 'video/mp4'; break;
            case '.3gp': contentType = 'video/3gpp'; break;
            case '.mp3': contentType = 'audio/mpeg'; break;
            case '.m4a': contentType = 'audio/mp4'; break;
            case '.aac': contentType = 'audio/aac'; break;
            case '.amr': contentType = 'audio/amr'; break;
            case '.ogg': contentType = 'audio/ogg'; break;
            default: contentType = file.mimetype;
        }

        if (!mimeTypes[type].includes(contentType)) {
            return res.status(400).json({ 
                success: false, 
                error: `Desteklenmeyen dosya türü. ${type} için desteklenen türler: ${mimeTypes[type].join(', ')}` 
            });
        }

        // WhatsApp API'ye medya yükle
        const formData = new FormData();
        const fileStream = fs.createReadStream(file.path);
        formData.append('file', fileStream, {
            filename: file.originalname,
            contentType: contentType
        });
        formData.append('messaging_product', 'whatsapp');
        formData.append('type', type);

        console.log('Medya yükleme isteği:', {
            type: type,
            contentType: contentType,
            filename: file.originalname,
            size: formatFileSize(file.size)
        });

        const uploadResponse = await axios({
            method: 'POST',
            url: `${API_BASE_URL}/v1/media`,
            headers: {
                ...formData.getHeaders(),
                'D360-API-KEY': API_KEY
            },
            data: formData,
            maxContentLength: 100 * 1024 * 1024, // 100MB max
            maxBodyLength: 100 * 1024 * 1024 // 100MB max
        });

        console.log('Medya yükleme yanıtı:', uploadResponse.data);

        if (!uploadResponse.data || !uploadResponse.data.id) {
            throw new Error('Medya yükleme hatası: Geçersiz API yanıtı');
        }

        // Medya ID'sini kullanarak mesaj gönder
        const mediaMessage = {
            messaging_product: "whatsapp",
            recipient_type: "individual",
            to: formattedPhone,
            type: type
        };

        // Medya türüne göre mesaj nesnesini oluştur
        const mediaObject = {
            id: uploadResponse.data.id
        };

        if (caption) {
            mediaObject.caption = caption;
        }

        if (type === 'document') {
            mediaObject.filename = file.originalname;
        }

        mediaMessage[type] = mediaObject;

        console.log('Mesaj gönderme isteği:', mediaMessage);

        const response = await axios({
            method: 'POST',
            url: `${API_BASE_URL}/messages`,
            headers: {
                'Content-Type': 'application/json',
                'D360-API-KEY': API_KEY
            },
            data: mediaMessage
        });

        console.log('Mesaj gönderme yanıtı:', response.data);

        if (!response.data || !response.data.messages || !response.data.messages[0]) {
            throw new Error('Geçersiz API yanıtı: ' + JSON.stringify(response.data));
            }
            
            // Mesajı veritabanına kaydet
        const query = `
            INSERT INTO messages (phone, message, direction, whatsapp_message_id, media_type, media_url, media_filename, media_filesize)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        `;
        
        db.run(query, [
            formattedPhone,
            caption || '',
            'outgoing',
            response.data.messages[0].id,
            type,
            file.path,
            file.originalname,
            formatFileSize(file.size)
        ], function(err) {
                if (err) {
                console.error('Veritabanı kayıt hatası:', err);
                throw err;
            }
        });

        res.json({ 
            success: true, 
            messageId: response.data.messages[0].id,
            mediaUrl: file.path
        });
        
    } catch (error) {
        console.error('Medya gönderme hatası:', {
            message: error.message,
            code: error.code,
            response: error.response ? {
                status: error.response.status,
                statusText: error.response.statusText,
                data: error.response.data
            } : undefined
        });
        
        res.status(500).json({ 
            success: false, 
            error: error.response?.data?.error?.message || error.response?.data?.error || error.message,
            details: error.response?.data
        });
    }
});

// Medya dosyalarını sunmak için statik klasör
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// Dosya boyutu formatlama fonksiyonu
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Webhook güncelleme
app.post('/webhook', async (req, res) => {
    try {
        const data = req.body;
        
        if (data.object && data.entry && data.entry.length > 0) {
            for (const entry of data.entry) {
                for (const change of entry.changes) {
                    if (change.value.messages) {
                        for (const message of change.value.messages) {
                            const phone = standardizePhoneNumber(message.from);
                            let messageText = '';
                            let mediaType = null;
                            let mediaUrl = null;
                            let mediaFilename = null;
                            
                            // Medya mesajlarını işle
                            if (message.type === 'image' || message.type === 'video' || message.type === 'document' || message.type === 'audio') {
                                mediaType = message.type;
                                
                                try {
                                    // Medya ID'sini al
                                    const mediaId = message[message.type].id;
                                    
                                    // Medyayı doğrudan indir
                                    const downloadResponse = await axios({
                                        method: 'GET',
                                        url: `${API_BASE_URL}/v1/media/${mediaId}`,
                                        headers: {
                                            'D360-API-KEY': API_KEY
                                        },
                                        responseType: 'arraybuffer',
                                        maxContentLength: 100 * 1024 * 1024 // 100MB max
                                    });

                                    // Content-Type'ı al
                                    const contentType = downloadResponse.headers['content-type'];
                                    
                                    // Dosya uzantısını Content-Type'a göre belirle
                                    const ext = contentType ? `.${contentType.split('/')[1]}` : getFileExtension(mediaType);
                                    
                                    // Dosya adını belirle
                                    mediaFilename = message[message.type].filename || 
                                        `${message.type}_${Date.now()}${ext}`;
                                    
                                    // Dosyayı kaydet
                                    const filePath = path.join(__dirname, 'uploads', mediaFilename);
                                    fs.writeFileSync(filePath, downloadResponse.data);
                                    
                                    // Yerel URL'yi oluştur
                                    mediaUrl = `/uploads/${mediaFilename}`;
                                    
                                    messageText = message[message.type].caption || '';
                                    
                                    console.log('Medya indirildi:', {
                                        type: mediaType,
                                        contentType: contentType,
                                        url: mediaUrl,
                                        filename: mediaFilename,
                                        size: formatFileSize(downloadResponse.data.length)
                                    });

                                    // 14 gün sonra medyayı otomatik sil
                                    setTimeout(async () => {
                                        try {
                                            if (fs.existsSync(filePath)) {
                                                fs.unlinkSync(filePath);
                                                console.log(`Medya silindi: ${mediaFilename}`);
                                            }
                                        } catch (error) {
                                            console.error('Medya silme hatası:', error);
                                        }
                                    }, 14 * 24 * 60 * 60 * 1000); // 14 gün

                                } catch (error) {
                                    console.error('Medya indirme hatası:', error);
                                    // Hata durumunda orijinal URL'yi kullan
                                    mediaUrl = message[message.type].link || null;
                                    mediaFilename = message[message.type].filename || `${message.type}_${Date.now()}`;
                                }
                            } else if (message.text) {
                                messageText = message.text.body;
                            }
                            
                            // Mesajı veritabanına kaydet
                            const query = `
                                INSERT INTO messages (phone, message, direction, whatsapp_message_id, media_type, media_url, media_filename)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            `;
                            
                            db.run(query, [
                                phone,
                                messageText,
                                'incoming',
                                message.id,
                                mediaType,
                                mediaUrl,
                                mediaFilename
                            ]);
                        }
                    }
                    
                    // Mesaj durumu güncellemelerini işle
                    if (change.value.statuses) {
                        console.log('Durum güncellemeleri alındı:', JSON.stringify(change.value.statuses, null, 2));
                        
                        for (const status of change.value.statuses) {
                            const messageId = status.id;
                            let newStatus = 'sent';
                            
                            console.log('İşlenen durum güncelleme:', {
                                messageId: messageId,
                                status: status.status,
                                timestamp: status.timestamp,
                                conversation: status.conversation,
                                pricing: status.pricing,
                                errors: status.errors
                            });
                            
                            switch (status.status) {
                                case 'sent':
                                    newStatus = 'sent';
                                    console.log('Mesaj gönderildi (tek tik)');
                                    break;
                                case 'delivered':
                                    newStatus = 'delivered';
                                    console.log('Mesaj iletildi (çift tik)');
                                    break;
                                case 'read':
                                    newStatus = 'seen';
                                    console.log('Mesaj okundu (mavi tik)');
                                    break;
                                case 'failed':
                                    newStatus = 'failed';
                                    console.log('Mesaj gönderilemedi (hata):', status.errors);
                                    break;
                                default:
                                    newStatus = status.status;
                                    console.log('Bilinmeyen durum:', status.status);
                            }
                            
                            // Mesaj durumunu güncelle
              db.run(
                                'UPDATE messages SET status = ? WHERE whatsapp_message_id = ?',
                                [newStatus, messageId],
                function(err) {
                  if (err) {
                                        console.error('Mesaj durumu güncelleme hatası:', {
                                            error: err,
                                            messageId: messageId,
                                            status: newStatus
                                        });
                                    } else {
                                        if (this.changes > 0) {
                                            console.log('Mesaj durumu güncellendi:', {
                                                messageId: messageId,
                                                newStatus: newStatus,
                                                changes: this.changes
                                            });
                                        } else {
                                            console.warn('Mesaj bulunamadı:', {
                                                messageId: messageId,
                                                newStatus: newStatus
                                            });
                                        }
                                    }
                                }
                            );
                        }
                    }
                }
            }
        }
        
        res.sendStatus(200);
    } catch (error) {
        console.error('Webhook hatası:', error);
        res.sendStatus(500);
    }
});

// Dosya uzantısını belirle
function getFileExtension(mediaType) {
    switch(mediaType) {
        case 'image':
            return '.jpg';
        case 'video':
            return '.mp4';
        case 'document':
            return '.pdf';
        default:
            return '';
    }
}

// Toplu mesaj gönderme endpoint'i
app.post('/api/send-bulk', async (req, res) => {
  try {
    const { phones, message } = req.body;
    
    if (!phones || !phones.length || !message) {
      return res.status(400).json({ success: false, error: 'Telefon numaraları ve mesaj gerekli' });
    }
    
    const results = [];
    const errors = [];
    
    // Her numara için mesaj gönder
    for (const phone of phones) {
      try {
        // Telefon numarasını standartlaştır
        const formattedPhone = standardizePhoneNumber(phone);
        
        // WhatsApp API isteği
        const response = await axios({
          method: 'POST',
          url: `${API_BASE_URL}/messages`,
          headers: {
            'Content-Type': 'application/json',
            'D360-API-KEY': API_KEY
          },
          data: {
            messaging_product: "whatsapp",
            recipient_type: "individual",
            to: formattedPhone,
            type: "text",
            text: {
              body: message
            }
          }
        });
        
        if (!response.data || !response.data.messages || !response.data.messages[0]) {
          throw new Error('Geçersiz API yanıtı');
        }
        
        // Mesajı veritabanına kaydet
        const messageQuery = `
          INSERT INTO messages (phone, message, direction, whatsapp_message_id)
          VALUES (?, ?, ?, ?)
        `;
        
        await new Promise((resolve, reject) => {
          db.run(messageQuery, [
            formattedPhone,
            message,
            'outgoing',
            response.data.messages[0].id
          ], function(err) {
            if (err) reject(err);
            else resolve();
          });
        });

        // Kişinin son mesaj zamanını güncelle
        const contactQuery = `
          UPDATE contacts 
          SET last_message_timestamp = datetime('now', '+3 hours')
          WHERE phone = ?
        `;

        await new Promise((resolve, reject) => {
          db.run(contactQuery, [formattedPhone], function(err) {
            if (err) reject(err);
            else resolve();
          });
        });
        
        results.push({
          phone: formattedPhone,
          success: true,
          messageId: response.data.messages[0].id
        });
        
      } catch (error) {
        console.error(`${phone} numarasına mesaj gönderme hatası:`, error);
        errors.push({
          phone,
          error: error.response?.data?.error?.message || error.message
        });
      }
    }
    
    res.json({
      success: true,
      results,
      errors
    });
    
  } catch (error) {
    console.error('Toplu mesaj gönderme hatası:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Mesaj gönderme endpoint'i
app.post('/api/send-message', async (req, res) => {
  try {
    const { phone, message } = req.body;
    
    if (!phone || !message) {
      return res.status(400).json({ error: 'Telefon numarası ve mesaj gerekli' });
    }
    
    // Telefon numarasını standartlaştır
    const formattedPhone = standardizePhoneNumber(phone);
    
    // WhatsApp API isteği
    const response = await axios({
      method: 'POST',
      url: `${API_BASE_URL}/messages`,
      headers: {
        'Content-Type': 'application/json',
        'D360-API-KEY': API_KEY
      },
      data: {
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to: formattedPhone,
        type: "text",
        text: {
          body: message
        }
      }
    });
    
    if (!response.data || !response.data.messages || !response.data.messages[0]) {
      throw new Error('Geçersiz API yanıtı: ' + JSON.stringify(response.data));
    }
    
    // Mesajı veritabanına kaydet
    const messageQuery = `
      INSERT INTO messages (phone, message, direction, whatsapp_message_id)
      VALUES (?, ?, ?, ?)
    `;
    
    await new Promise((resolve, reject) => {
      db.run(messageQuery, [
        formattedPhone,
        message,
        'outgoing',
        response.data.messages[0].id
      ], function(err) {
        if (err) reject(err);
        else resolve();
      });
    });

    // Kişinin son mesaj zamanını güncelle
    const contactQuery = `
      UPDATE contacts 
      SET last_message_timestamp = datetime('now', '+3 hours')
      WHERE phone = ?
    `;

    await new Promise((resolve, reject) => {
      db.run(contactQuery, [formattedPhone], function(err) {
        if (err) reject(err);
        else resolve();
      });
    });
    
    res.json({ 
      success: true, 
      messageId: response.data.messages[0].id
    });
    
  } catch (error) {
    console.error('Mesaj gönderme hatası:', error);
    res.status(500).json({
      success: false,
      error: error.response?.data?.error?.message || error.message
    });
  }
});

// Port ayarı ve sunucuyu başlat
app.listen(PORT, async () => {
  console.log(`${PORT} numaralı bağlantı noktasında çalışan sunucu`);
  await setupWebhook();
});