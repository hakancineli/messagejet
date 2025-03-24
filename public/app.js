document.addEventListener('DOMContentLoaded', function() {
    let currentContact = null;
    let currentContactName = null;
    const contactsList = document.getElementById('contacts-list');
    const messagesContainer = document.getElementById('messages-container');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const currentContactHeader = document.getElementById('current-contact');
    const contactSearch = document.getElementById('contact-search');
    
    // Modal elemanları
    const addContactBtn = document.getElementById('add-contact-btn');
    const editContactBtn = document.getElementById('edit-contact-btn');
    const deleteContactBtn = document.getElementById('delete-contact-btn');
    const contactModal = document.getElementById('contact-modal');
    const deleteModal = document.getElementById('delete-modal');
    const contactForm = document.getElementById('contact-form');
    const contactPhone = document.getElementById('contact-phone');
    const contactName = document.getElementById('contact-name');
    const modalTitle = document.getElementById('modal-title');
    const confirmDeleteBtn = document.getElementById('confirm-delete');
    const cancelDeleteBtn = document.getElementById('cancel-delete');
    const closeButtons = document.querySelectorAll('.close');
    
    // Ayarlar modalı için elemanlar
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const webhookUrlInput = document.getElementById('webhook-url');
    const updateWebhookBtn = document.getElementById('update-webhook');
    const webhookStatus = document.getElementById('webhook-status');
    const tabs = document.querySelectorAll('.tab');
    
    // Son mesaj ve kişi verilerini saklamak için değişkenler
    let lastMessagesData = null;
    let lastContactsData = null;
    
    // Tüm mesajları ve kişileri getir
    fetchMessages();
    fetchContacts();
    
    // Mesaj gönderme olayları
    sendButton.addEventListener('click', () => {
        sendMessage();
    });

    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Form gönderimini engelle
            sendMessage();
        }
    });
    
    // Ayarlar modalını aç
    settingsBtn.addEventListener('click', function() {
        // Mevcut webhook URL'sini getir
        fetch('/api/webhook-url')
            .then(response => response.json())
            .then(data => {
                if (data.url) {
                    // URL'den /webhook kısmını çıkar
                    const baseUrl = data.url.replace('/webhook', '');
                    webhookUrlInput.value = baseUrl;
                }
            })
            .catch(error => console.error('Webhook URL getirme hatası:', error));
        
        settingsModal.style.display = 'block';
    });
    
    // Tüm modalları kapatma işlemi
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            contactModal.style.display = 'none';
            deleteModal.style.display = 'none';
            settingsModal.style.display = 'none'; // Ayarlar modalını da kapat
        });
    });
    
    // Modalların dışına tıklandığında kapatma
    window.addEventListener('click', function(event) {
        if (event.target === contactModal) {
            contactModal.style.display = 'none';
        }
        if (event.target === deleteModal) {
            deleteModal.style.display = 'none';
        }
        if (event.target === settingsModal) {
            settingsModal.style.display = 'none'; // Ayarlar modalını da kapat
        }
    });
    
    // Tab değiştirme
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Aktif tabı değiştir
            document.querySelector('.tab.active').classList.remove('active');
            this.classList.add('active');
            
            // Tab içeriğini göster
            const tabName = this.dataset.tab;
            document.querySelector('.tab-pane.active').classList.remove('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
    
    // Webhook URL'sini güncelle
    updateWebhookBtn.addEventListener('click', function() {
        const baseUrl = webhookUrlInput.value.trim();
        
        if (!baseUrl) {
            showWebhookStatus('Lütfen geçerli bir URL girin', false);
            return;
        }
        
        // URL'nin sonunda / varsa kaldır
        const cleanUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
        // Webhook URL'sini oluştur
        const webhookUrl = `${cleanUrl}/webhook`;
        
        // Webhook URL'sini güncelle
        fetch('/api/update-webhook', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: webhookUrl })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showWebhookStatus('Webhook URL başarıyla güncellendi', true);
            } else {
                showWebhookStatus(`Hata: ${data.error}`, false);
            }
        })
        .catch(error => {
            console.error('Webhook güncelleme hatası:', error);
            showWebhookStatus(`Hata: ${error.message}`, false);
        });
    });
    
    // Webhook durum mesajını göster
    function showWebhookStatus(message, isSuccess) {
        webhookStatus.textContent = message;
        webhookStatus.className = 'status-message';
        webhookStatus.classList.add(isSuccess ? 'status-success' : 'status-error');
        
        // 5 saniye sonra mesajı gizle
        setTimeout(() => {
            webhookStatus.style.display = 'none';
        }, 5000);
    }
    
    // Kişi arama
    contactSearch.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const contacts = contactsList.querySelectorAll('.contact');
        
        contacts.forEach(contact => {
            const name = contact.querySelector('h4').textContent.toLowerCase();
            const phone = contact.dataset.phone.toLowerCase();
            const lastMessage = contact.querySelector('.last-message').textContent.toLowerCase();
            
            if (name.includes(searchTerm) || 
                phone.includes(searchTerm) || 
                lastMessage.includes(searchTerm)) {
                contact.style.display = 'block';
            } else {
                contact.style.display = 'none';
            }
        });
    });
    
    // Kişi ekleme modalını aç
    addContactBtn.addEventListener('click', function() {
        modalTitle.textContent = 'Kişi Ekle';
        contactPhone.value = '';
        contactName.value = '';
        contactPhone.disabled = false;
        contactModal.style.display = 'block';
    });
    
    // Kişi düzenleme modalını aç
    editContactBtn.addEventListener('click', function() {
        if (!currentContact) return;
        
        modalTitle.textContent = 'Kişiyi Düzenle';
        contactPhone.value = currentContact;
        contactName.value = currentContactName;
        contactPhone.disabled = true; // Telefon numarası düzenlenemez
        contactModal.style.display = 'block';
    });
    
    // Kişi silme modalını aç
    deleteContactBtn.addEventListener('click', function() {
        if (!currentContact) return;
        deleteModal.style.display = 'block';
    });
    
    // Kişi silme işlemini iptal et
    cancelDeleteBtn.addEventListener('click', function() {
        deleteModal.style.display = 'none';
    });
    
    // Kişi silme işlemini onayla
    confirmDeleteBtn.addEventListener('click', function() {
        if (!currentContact) return;
        
        const standardizedPhone = standardizePhoneNumber(currentContact);
        
        fetch(`/api/contacts/${standardizedPhone}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Kişi silindi, kişileri yenile
                fetchContacts();
                // Mesaj alanını temizle
                messagesContainer.innerHTML = '';
                currentContact = null;
                currentContactName = null;
                currentContactHeader.textContent = 'Seçili kişi yok';
                editContactBtn.disabled = true;
                deleteContactBtn.disabled = true;
                messageInput.disabled = true;
                sendButton.disabled = true;
            } else {
                alert('Kişi silme hatası: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Kişi silme hatası:', error);
            alert('Kişi silme hatası: ' + error.message);
        })
        .finally(() => {
            deleteModal.style.display = 'none';
        });
    });
    
    // Kişi ekleme/düzenleme formunu gönder
    contactForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const phone = standardizePhoneNumber(contactPhone.value.trim());
        const name = contactName.value.trim();
        const isEdit = contactForm.dataset.mode === 'edit';
        
        if (!phone) {
            alert('Lütfen telefon numarası girin');
            return;
        }
        
        // Kişiyi ekle/düzenle
        fetch('/api/contacts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                phone: phone,
                name: name,
                isEdit: isEdit
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Kişi listesini güncelle
                fetchContacts();
                
                // Modalı kapat
                contactModal.style.display = 'none';
                
                // Formu temizle
                contactForm.reset();
            } else {
                alert('Kişi ekleme/düzenleme hatası: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Kişi ekleme/düzenleme hatası:', error);
            alert('Kişi ekleme/düzenleme hatası: ' + error.message);
        });
    });
    
    // Tüm mesajları getir
    async function fetchMessages() {
        try {
            const response = await fetch('/api/messages');
            const data = await response.json();
            
            // Veriyi sakla
            lastMessagesData = data;
            
            // Eğer bir kişi seçiliyse, o kişinin mesajlarını göster
            if (currentContact) {
                displayMessages(currentContact);
                scrollToBottom();
            }
        } catch (error) {
            console.error('Mesaj getirme hatası:', error);
        }
    }
    
    // Tüm kişileri getir
    async function fetchContacts() {
        try {
            // Kişileri al
            const contactsResponse = await fetch('/api/contacts');
            const contacts = await contactsResponse.json();
            
            // Mesajları al
            const messagesResponse = await fetch('/api/messages');
            const messages = await messagesResponse.json();
            
            // Her kişi için son mesajı bul
            const contactsWithLastMessage = contacts.map(contact => {
                const contactMessages = messages.filter(m => 
                    standardizePhoneNumber(m.phone) === standardizePhoneNumber(contact.phone)
                );
                const lastMessage = contactMessages.length > 0 
                    ? contactMessages.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0]
                    : null;
                
                return {
                    ...contact,
                    lastMessage: lastMessage
                };
            });
            
            // Son mesaj tarihine göre sırala
            contactsWithLastMessage.sort((a, b) => {
                const timeA = a.lastMessage ? new Date(a.lastMessage.timestamp) : new Date(a.last_message_timestamp || 0);
                const timeB = b.lastMessage ? new Date(b.lastMessage.timestamp) : new Date(b.last_message_timestamp || 0);
                return timeB - timeA;
            });
            
            // Kişi listesini güncelle
            updateContactsList(contactsWithLastMessage);
        } catch (error) {
            console.error('Kişileri getirme hatası:', error);
        }
    }
    
    // Kişi listesini güncelle
    async function updateContactsList(contacts) {
        // Mevcut seçili kişiyi kaydet
        const activePhone = currentContact;
        
        // Kişi listesini temizle
        contactsList.innerHTML = '';

        // Her kişi için bir öğe oluştur
        for (const contact of contacts) {
            const contactDiv = document.createElement('div');
            contactDiv.className = 'contact';
            contactDiv.dataset.phone = contact.phone;

            const name = contact.name || contact.phone;
            const lastMessage = contact.lastMessage 
                ? `<div class="last-message">${contact.lastMessage.message || (contact.lastMessage.media_type ? 'Medya mesajı' : '')}</div>
                   <div class="message-time">${formatDate(contact.lastMessage.timestamp)}</div>
                   <div class="message-direction">${contact.lastMessage.direction === 'outgoing' ? 'Giden' : 'Gelen'}</div>`
                : '';
            
            contactDiv.innerHTML = `
                <div class="contact-info">
                    <h4>${name}</h4>
                    <span class="contact-phone">${contact.phone}</span>
                    ${lastMessage}
                </div>
            `;

            // Aktif kişiyi seç
            if (standardizePhoneNumber(contact.phone) === standardizePhoneNumber(activePhone)) {
                contactDiv.classList.add('active');
            }

            // Kişiye tıklama olayı
            contactDiv.addEventListener('click', function() {
                handleContactClick(this, contact.phone, name);
            });

            contactsList.appendChild(contactDiv);
        }
    }

    // Kişiye tıklama işleyicisi
    function handleContactClick(contactDiv, phone, name) {
        // Önceki aktif kişiyi kaldır
        const activeContact = contactsList.querySelector('.contact.active');
        if (activeContact) {
            activeContact.classList.remove('active');
        }

        // Yeni kişiyi aktif yap
        contactDiv.classList.add('active');
        currentContact = phone;
        currentContactName = name;
        currentContactHeader.textContent = name;
        
        // Butonları aktif et
        if (editContactBtn) editContactBtn.disabled = false;
        if (deleteContactBtn) deleteContactBtn.disabled = false;
        if (messageInput) messageInput.disabled = false;
        if (sendButton) sendButton.disabled = false;

        // Mesajları göster
        displayMessages(phone);
    }
    
    // Mesajları görüntüle
    function displayMessages(phone) {
        if (!lastMessagesData) return;
        
        const messages = lastMessagesData.filter(m => standardizePhoneNumber(m.phone) === standardizePhoneNumber(phone));
        messagesContainer.innerHTML = '';
        
        messages.forEach(message => {
            addMessageToChat(message, message.direction === 'incoming');
        });
        
        // Mesajları en alta kaydır
        scrollToBottom();
    }
    
    // En alta kaydırma fonksiyonu
    function scrollToBottom() {
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
    
    // Mesaj eklendiğinde otomatik kaydırma
    function addMessageToChat(message, isIncoming = false) {
        const messagesContainer = document.getElementById('messages-container');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isIncoming ? 'incoming' : 'outgoing'}`;
        
        let messageContent = '';
        
        // Medya içeriği varsa
        if (message.media_type) {
            switch(message.media_type) {
                case 'image':
                    messageContent = `
                        <div class="media-container">
                            <img src="${message.media_url}" alt="Resim" class="media-content" onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0yNCAyNGgtMjR2LTI0aDI0djI0em0tMi0ydi0yMGgtMjB2MjBoMjB6bS00LjExOC04LjI0N2wtMy4yNDEgNC4yNDQtMi4wMDEtMi4wMDEtNC4yNDQgNS4wMDRoLTIuMzk2di0xNGgyMHYxNGgtMi4xMThsLTQuMjQ0LTUuMjQ3LTMuNzU2IDMuOTk2em0tNy44ODItMy4yNTNjMS4wNjUgMCAxLjkzLS44NjYgMS45My0xLjkzIDAtMS4wNjUtLjg2NS0xLjkzLTEuOTMtMS45My0xLjA2NCAwLTEuOTI5Ljg2NS0xLjkyOSAxLjkzIDAgMS4wNjQuODY1IDEuOTMgMS45MjkgMS45M3oiLz48L3N2Zz4=';">
                            ${message.message ? `<p class="media-caption">${message.message}</p>` : ''}
                        </div>`;
                    break;
                case 'video':
                    messageContent = `
                        <div class="media-container">
                            <video src="${message.media_url}" controls class="media-content"></video>
                            ${message.message ? `<p class="media-caption">${message.message}</p>` : ''}
                        </div>`;
                    break;
                case 'audio':
                    messageContent = `
                        <div class="media-container">
                            <audio src="${message.media_url}" controls class="media-content"></audio>
                            ${message.message ? `<p class="media-caption">${message.message}</p>` : ''}
                        </div>`;
                    break;
                case 'document':
                    messageContent = `
                        <div class="media-container">
                            <div class="document-preview">
                                <i class="fas fa-file-alt"></i>
                                <a href="${message.media_url}" target="_blank" class="document-link">
                                    ${message.media_filename || 'Dosya'}
                                    ${message.media_filesize ? `<span class="file-size">(${message.media_filesize})</span>` : ''}
                                </a>
                            </div>
                            ${message.message ? `<p class="media-caption">${message.message}</p>` : ''}
                        </div>`;
                    break;
            }
        } else {
            messageContent = `<p>${message.message}</p>`;
        }
        
        messageDiv.innerHTML = `
            ${messageContent}
            <div class="message-info">
                <span class="message-time">${formatTimestamp(message.timestamp)}</span>
                ${!isIncoming ? `<span class="message-status" data-id="${message.id}">${getStatusIcon(message.status)}</span>` : ''}
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        
        // Yeni mesaj eklendiğinde en alta kaydır
        scrollToBottom();
    }
    
    // Mesaj durumu ikonu
    function getStatusIcon(status) {
        switch(status) {
            case 'sent':
                return '<i class="fas fa-check"></i>';
            case 'delivered':
                return '<i class="fas fa-check-double"></i>';
            case 'seen':
                return '<i class="fas fa-check-double seen"></i>';
            default:
                return '<i class="fas fa-clock"></i>';
        }
    }
    
    // Timestamp'i formatla
    function formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    }
    
    // Mesaj durumu kontrolü için fonksiyon
    function checkMessageStatus(messageId) {
        fetch(`/api/message-status/${messageId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status) {
                    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                    if (messageElement) {
                        const statusIcon = messageElement.querySelector('.status');
                        if (statusIcon) {
                            statusIcon.className = `fas fa-check${data.status === 'delivered' || data.status === 'seen' ? '-double' : ''} message-status ${data.status}`;
                        }
                    }
                }
            })
            .catch(error => console.error('Mesaj durumu kontrolü hatası:', error));
    }
    
    // Medya yükleme elementleri
    const imageUpload = document.getElementById('image-upload');
    const videoUpload = document.getElementById('video-upload');
    const audioUpload = document.getElementById('audio-upload');
    const documentUpload = document.getElementById('document-upload');
    const messageInputContainer = document.querySelector('.message-input');
    
    let currentMedia = null;
    
    // Medya yükleme işleyicileri
    imageUpload.addEventListener('change', handleMediaUpload);
    videoUpload.addEventListener('change', handleMediaUpload);
    audioUpload.addEventListener('change', handleMediaUpload);
    documentUpload.addEventListener('change', handleMediaUpload);
    
    // Medya yükleme fonksiyonu
    function handleMediaUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!currentContact) {
            alert('Lütfen önce bir kişi seçin');
            return;
        }
        
        // Dosya boyutu kontrolü (10MB)
        if (file.size > 10 * 1024 * 1024) {
            alert('Dosya boyutu 10MB\'dan küçük olmalıdır');
            return;
        }
        
        currentMedia = {
            file: file,
            type: event.target.id.split('-')[0] // image, video, audio veya document
        };
        
        // Önizleme oluştur
        showMediaPreview(file, currentMedia.type);
    }
    
    // Medya önizleme fonksiyonu
    function showMediaPreview(file, type) {
        const previewContainer = document.createElement('div');
        previewContainer.className = 'media-preview-container';
        
        const preview = document.createElement('div');
        preview.className = 'media-preview';
        
        const removeButton = document.createElement('span');
        removeButton.className = 'remove-media';
        removeButton.innerHTML = '×';
        removeButton.onclick = removeMediaPreview;
        
        switch(type) {
            case 'image':
                const img = document.createElement('img');
                img.style.maxHeight = '100px';
                img.src = URL.createObjectURL(file);
                preview.appendChild(img);
                break;
                
            case 'video':
                const video = document.createElement('video');
                video.style.maxHeight = '100px';
                video.src = URL.createObjectURL(file);
                video.controls = true;
                preview.appendChild(video);
                break;
                
            case 'audio':
                const audio = document.createElement('audio');
                audio.src = URL.createObjectURL(file);
                audio.controls = true;
                preview.appendChild(audio);
                break;
                
            case 'document':
                const docPreview = document.createElement('div');
                docPreview.className = 'document';
                docPreview.innerHTML = `
                    <i class="fas fa-file"></i>
                    <div class="info">
                        <div class="filename">${file.name}</div>
                        <div class="filesize">${formatFileSize(file.size)}</div>
                    </div>
                `;
                preview.appendChild(docPreview);
                break;
        }
        
        preview.appendChild(removeButton);
        previewContainer.appendChild(preview);
        messageInputContainer.classList.add('with-preview');
        messageInputContainer.insertBefore(previewContainer, messageInput);
    }
    
    // Medya önizlemeyi kaldır
    function removeMediaPreview() {
        const previewContainer = document.querySelector('.media-preview-container');
        if (previewContainer) {
            previewContainer.remove();
            messageInputContainer.classList.remove('with-preview');
        }
        currentMedia = null;
    }
    
    // Dosya boyutunu formatla
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Telefon numarasını standart formata çeviren yardımcı fonksiyon
    function standardizePhoneNumber(phone) {
        if (!phone) return phone;
        
        // Boşlukları ve tire işaretlerini kaldır
        phone = phone.replace(/[\s-]/g, '');
        
        // Eğer + ile başlamıyorsa ekle
        if (!phone.startsWith('+')) {
            phone = '+' + phone;
        }
        
        return phone;
    }

    // Daha sık güncelleme için interval'ları ayarla
    setInterval(fetchMessages, 2000);  // Her 2 saniyede bir mesajları güncelle
    setInterval(fetchContacts, 5000);  // Her 5 saniyede bir kişi listesini güncelle

    // Excel işleme için XLSX kütüphanesini ekleyelim
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
    document.head.appendChild(script);

    // Toplu mesaj modal işlemleri
    const bulkMessageBtn = document.getElementById('bulk-message-btn');
    const bulkMessageModal = document.getElementById('bulk-message-modal');
    const bulkMessageForm = document.getElementById('bulk-message-form');
    const progressContainer = document.querySelector('.progress-container');
    const progressBar = document.querySelector('.progress-bar');
    const progressText = document.querySelector('.progress-text');

    // Toplu mesaj modalı varsa event listener'ları ekle
    if (bulkMessageBtn && bulkMessageModal) {
        bulkMessageBtn.addEventListener('click', () => {
            bulkMessageModal.style.display = 'block';
        });

        const closeButton = bulkMessageModal.querySelector('.close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                bulkMessageModal.style.display = 'none';
            });
        }

        if (bulkMessageForm) {
            bulkMessageForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const excelFile = document.getElementById('excel-file').files[0];
                const message = document.getElementById('bulk-message').value;
                
                if (!excelFile || !message) {
                    alert('Lütfen Excel dosyası ve mesaj metnini giriniz.');
                    return;
                }

                const reader = new FileReader();
                reader.onload = async function(e) {
                    const data = new Uint8Array(e.target.result);
                    const workbook = XLSX.read(data, {type: 'array'});
                    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                    const contacts = XLSX.utils.sheet_to_json(firstSheet);

                    if (!contacts.length || !contacts[0].phone) {
                        alert('Excel dosyasında "phone" sütunu bulunamadı.');
                        return;
                    }

                    progressContainer.style.display = 'block';
                    const total = contacts.length;
                    let sent = 0;

                    for (const contact of contacts) {
                        try {
                            const phone = contact.phone.toString();
                            const name = contact.name || '';

                            // Önce kişiyi kaydet
                            await fetch('/api/contacts', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    phone: phone,
                                    name: name,
                                    isEdit: false
                                })
                            });

                            // Sonra mesajı gönder
                            const response = await fetch('/api/send-message', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    phone: phone,
                                    message: message,
                                    name: name
                                })
                            });

                            if (response.ok) sent++;
                            
                            // Progress güncelleme
                            const progress = (sent / total) * 100;
                            progressBar.style.width = `${progress}%`;
                            progressText.textContent = `${sent}/${total} mesaj gönderildi`;

                            // Her mesaj arasında 1 saniye bekleyelim
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        } catch (error) {
                            console.error('Mesaj gönderme hatası:', error);
                        }
                    }

                    alert(`Toplu mesaj gönderimi tamamlandı. ${sent}/${total} mesaj başarıyla gönderildi.`);
                    bulkMessageForm.reset();
                    progressContainer.style.display = 'none';
                    progressBar.style.width = '0%';
                    bulkMessageModal.style.display = 'none';
                    
                    // Kişi listesini güncelle
                    fetchContacts();
                };

                reader.readAsArrayBuffer(excelFile);
            });
        }
    }
});