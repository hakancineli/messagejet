import os

port = os.environ.get('PORT', '3000')
bind = f"0.0.0.0:{port}"
workers = 1
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
capture_output = True
enable_stdio_inheritance = True 