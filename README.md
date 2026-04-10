# Online Auction Engine — 3-Laptop Network Setup

## Overview

A real-time TCP auction system using Python sockets with SSL/TLS encryption.
Designed to run across **3 laptops on the same Wi-Fi network**:

```
Laptop 1 (Server)          Laptop 2 (Client — Bidder A)
  python main.py server  ←→   python main.py client

                         ←→ Laptop 3 (Client — Bidder B)
                               python main.py client
```

---

## Prerequisites

All three laptops need Python 3.8+ and one library:

```bash
pip install cryptography
```

---

## Setup (Follow in Order)

### Step 1 — Find the server laptop's IP address

On the **server laptop**, run:
```
Windows:   ipconfig
Mac/Linux: ifconfig   or   ip a
```
Look for the **IPv4 address** on your Wi-Fi adapter. It looks like `192.168.x.x`.

---

### Step 2 — Edit config.py on ALL three laptops

Open `config.py` and set `SERVER_IP` to the server laptop's IP:

```python
SERVER_IP   = "192.168.1.100"   # ← replace with actual server IP
SERVER_PORT = 8080
```

Do this on **all three laptops** (same IP, same port).

---

### Step 3 — Generate SSL certificate (server laptop only)

Run this **once, on the server laptop**:

```bash
python gen_cert.py
```

This creates `cert.pem` and `key.pem`.

---

### Step 4 — Copy cert.pem to client laptops

Copy **only `cert.pem`** (NOT `key.pem`) to both client laptops.
Place it in the same folder as `main.py`.

```
Methods: USB drive / AirDrop / email / shared folder / scp
```

`key.pem` stays on the server only — never share it.

---

### Step 5 — Start the server

On **Laptop 1 (server)**:

```bash
python main.py server
```

You should see:
```
Binding to 0.0.0.0:8080
Clients should connect to: 192.168.1.100:8080
Server is ready and secure. Waiting for clients...
```

---

### Step 6 — Connect clients

On **Laptop 2** and **Laptop 3**:

```bash
python main.py client
```

You should see:
```
SSL Handshake : OK ✓
Cipher in use : TLS_AES_256_GCM_SHA384
Connection    : Encrypted ✓
```

---

## Commands

| Command | Description |
|---|---|
| `REGISTER <username>` | Join the auction (do this first!) |
| `LIST_ITEMS` | See all active auctions |
| `BID <itemId> <amount>` | Place a bid |
| `VIEW_ITEM <itemId>` | View item + full bid history |
| `MY_BIDS` | See all your bids |
| `BID_HISTORY <itemId>` | All bids on an item |
| `ADD_ITEM <id> <n> <desc> <start> <reserve> <secs>` | Add a new item |
| `PING` | Check connection |
| `HELP` | Show all commands |
| `QUIT` | Disconnect |

---

## Sample Demo

```
Server (Laptop 1):
  python main.py server
  → 3 items loaded: MacBook_Pro, iPhone_15_Pro, Sony_WH1000XM5

Client Alice (Laptop 2):          Client Bob (Laptop 3):
  REGISTER Alice                    REGISTER Bob
  LIST_ITEMS                        LIST_ITEMS
  BID I001 550                      BID I001 600
  → [SERVER] BID_UPDATE: Bob        BID I001 750
  BID I001 800                      → [SERVER] BID_UPDATE: Alice
                                    BID I001 850
  → Auction closes...
  → AUCTION WON: Bob @ 850.00
```

---

## Architecture

```
Clients (Bidders on laptops 2 & 3)
        |
   [TCP + TLS 1.3 — Port 8080]
        |
   [AuctionServer — laptop 1]
   ├── ClientHandler     one thread per connected client
   ├── AuctionEngine     bid logic, locking, validation
   ├── TimerService      auto-closes auctions on expiry
   ├── StateManager      saves/restores state to disk
   └── Protocol          all message formats
```

---

## Features

| Feature | Detail |
|---|---|
| SSL/TLS encryption | TLS 1.3, AES-256-GCM, RSA-2048 cert |
| Concurrent bids | Per-item `threading.Lock()` with timeout |
| Anti-sniping | Auction extended 30s if bid in last 10s |
| Reserve price | Auction only completes if reserve met |
| Crash recovery | State saved after every bid |
| Duplicate detection | Fingerprint-based deduplication |
| Real-time broadcast | All clients notified of every bid |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused` | Make sure server is running; check SERVER_IP in config.py |
| `SSL cert verification failed` | Copy cert.pem from the server laptop |
| `cert.pem not found` | Run `python gen_cert.py` on server laptop |
| Clients can't reach server | Check all laptops are on the same Wi-Fi; check firewall |
| Fresh start | Delete `auction_state.txt` then restart server |

### Firewall (if clients can't connect)

**Windows:** Control Panel → Windows Defender Firewall → Allow port 8080  
**Mac:** System Settings → Network → Firewall → Allow incoming on port 8080  
**Linux:** `sudo ufw allow 8080`

---

## File Structure

```
auction_system/
├── config.py              ← EDIT THIS: set SERVER_IP
├── main.py                ← Entry point
├── gen_cert.py            ← Run once on server to generate SSL cert
├── cert.pem               ← Copy to client laptops
├── key.pem                ← Server only, never share
├── auction_state.txt      ← Auto-generated; delete for fresh start
├── model/
│   ├── item.py
│   ├── bid.py
│   └── bidder.py
├── engine/
│   ├── protocol.py
│   ├── auction_engine.py
│   ├── timer_service.py
│   └── state_manager.py
├── server/
│   └── auction_server.py
└── client/
    └── auction_client.py
```
