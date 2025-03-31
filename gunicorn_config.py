import os

# Port ayarı
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Worker ayarları
workers = 4
threads = 2
worker_class = 'sync'

# Timeout ayarları
timeout = 120
keepalive = 5

# Logging ayarları
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Diğer ayarlar
capture_output = True
enable_stdio_inheritance = True
preload_app = True
reload = True 