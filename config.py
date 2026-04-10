# config.py
# ============================================================
#  EDIT THIS FILE BEFORE RUNNING
# ============================================================
#
#  Step 1: Find the server laptop's local IP address
#          Windows  →  run: ipconfig       (look for IPv4 Address)
#          Mac/Linux → run: ifconfig / ip a (look for inet under your Wi-Fi)
#
#  Step 2: Paste that IP below as SERVER_IP
#
#  Step 3: Copy this ENTIRE project folder to both client laptops
#          (or just share cert.pem + config.py after generating cert)
#
# ============================================================

SERVER_IP   = "192.168.1.100"   # <-- Change to your server laptop's IP
SERVER_PORT = 8080

CERTFILE = "cert.pem"
KEYFILE  = "key.pem"
