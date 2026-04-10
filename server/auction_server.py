# server/auction_server.py
import socket
import ssl
import threading

from config                import SERVER_PORT, CERTFILE, KEYFILE
from engine.auction_engine import AuctionEngine
from engine.protocol       import Protocol

# ─────────────────────────────────────────────────────────────
#  Shared server state
# ─────────────────────────────────────────────────────────────
auction_engine    = AuctionEngine()
connected_clients = []
clients_lock      = threading.Lock()


def broadcast(message, sender=None):
    """Send a message to every connected client."""
    print(f"[BROADCAST] {message}")
    with clients_lock:
        for client in connected_clients:
            if client is not sender:
                client.send_message(message)


# Wire broadcast into the engine so it can notify all clients
auction_engine.broadcast_fn = broadcast


# ─────────────────────────────────────────────────────────────
#  Per-client handler (one thread per connected client)
# ─────────────────────────────────────────────────────────────
class ClientHandler(threading.Thread):

    def __init__(self, conn, addr):
        super().__init__(daemon=True)
        self.conn        = conn
        self.addr        = addr
        self.client_name = None
        self.running     = True

    # ── Main receive loop ─────────────────────────────────
    def run(self):
        self._send_banner()
        try:
            buffer = ""
            while self.running:
                data = self.conn.recv(4096).decode("utf-8")
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        print(f"[{self.addr[0]}] [{self.client_name or 'unregistered'}] {line}")
                        self.handle_message(line)
        except ssl.SSLError as e:
            print(f"[SSL Error] {self.client_name or self.addr}: {e}")
        except OSError:
            pass
        except Exception as e:
            print(f"[Client Error] {self.client_name or self.addr}: {e}")
        finally:
            self.cleanup()

    def _send_banner(self):
        self.send_message("╔══════════════════════════════════════════╗")
        self.send_message("║    Welcome to the Real-Time Auction!     ║")
        self.send_message("║    Connection is SSL/TLS Encrypted ✓     ║")
        self.send_message("╚══════════════════════════════════════════╝")
        self.send_message("Type HELP to see all available commands.")
        self.send_message("──────────────────────────────────────────")

    # ── Command dispatcher ────────────────────────────────
    def handle_message(self, message):
        parts   = message.split(" ", 6)   # max 7 tokens for ADD_ITEM
        command = parts[0].upper()
        engine  = auction_engine

        # ── REGISTER ──────────────────────────────────────
        if command == Protocol.REGISTER:
            if len(parts) < 2:
                self.send_message("ERROR Usage: REGISTER <username>")
                return
            username = parts[1].strip()
            result   = engine.register_bidder(username)
            self.send_message(result)
            if result.startswith("OK"):
                self.client_name = username
                broadcast(f"🔔 {username} joined the auction!", self)

        # ── LIST_ITEMS ────────────────────────────────────
        elif command == Protocol.LIST_ITEMS:
            self.send_message(engine.list_active_items())

        # ── VIEW_ITEM ─────────────────────────────────────
        elif command == Protocol.VIEW_ITEM:
            if len(parts) < 2:
                self.send_message("ERROR Usage: VIEW_ITEM <itemId>")
            else:
                self.send_message(engine.get_item_details(parts[1]))

        # ── BID ───────────────────────────────────────────
        elif command == Protocol.BID:
            if len(parts) < 3:
                self.send_message("ERROR Usage: BID <itemId> <amount>")
            elif not self.client_name:
                self.send_message(Protocol.ERR_NOT_REGISTERED)
            else:
                try:
                    amount = float(parts[2])
                    self.send_message(
                        engine.place_bid(self.client_name, parts[1], amount)
                    )
                except ValueError:
                    self.send_message(Protocol.ERR_INVALID_AMOUNT)

        # ── MY_BIDS ───────────────────────────────────────
        elif command == Protocol.MY_BIDS:
            if not self.client_name:
                self.send_message(Protocol.ERR_NOT_REGISTERED)
            else:
                bidder = engine.get_bidder_by_username(self.client_name)
                if not bidder or not bidder.my_bids:
                    self.send_message("You have not placed any bids yet.")
                else:
                    lines = ["=== Your Bids ==="]
                    for b in bidder.my_bids:
                        lines.append(b.get_bid_summary())
                    self.send_message("\n".join(lines))

        # ── BID_HISTORY ───────────────────────────────────
        elif command == Protocol.BID_HISTORY:
            if len(parts) < 2:
                self.send_message("ERROR Usage: BID_HISTORY <itemId>")
            else:
                self.send_message(engine.get_item_details(parts[1]))

        # ── ADD_ITEM ──────────────────────────────────────
        elif command == Protocol.ADD_ITEM:
            # ADD_ITEM <id> <name> <desc> <startPrice> <reservePrice> <durationSecs>
            if len(parts) < 7:
                self.send_message(
                    "ERROR Usage: ADD_ITEM <id> <name> <desc> "
                    "<startPrice> <reservePrice> <durationSecs>"
                )
            else:
                try:
                    self.send_message(engine.add_item(
                        parts[1], parts[2], parts[3],
                        float(parts[4]), float(parts[5]), int(parts[6])
                    ))
                except ValueError:
                    self.send_message("ERROR Invalid number in ADD_ITEM.")

        # ── PING ──────────────────────────────────────────
        elif command == Protocol.PING:
            self.send_message(f"{Protocol.PONG} Server alive! [SSL Secured] Clients online: {len(connected_clients)}")

        # ── HELP ──────────────────────────────────────────
        elif command == Protocol.HELP:
            self.send_message(Protocol.HELP_TEXT)

        # ── QUIT ──────────────────────────────────────────
        elif command == Protocol.QUIT:
            self.send_message(f"OK Goodbye {self.client_name or ''}! See you next time.")
            self.cleanup()

        else:
            self.send_message(f"ERROR Unknown command: '{command}' | Type HELP")

    # ── Helpers ───────────────────────────────────────────
    def send_message(self, message):
        try:
            self.conn.sendall((message + "\n").encode("utf-8"))
        except Exception:
            pass

    def cleanup(self):
        self.running = False
        if self.client_name:
            auction_engine.mark_disconnected(self.client_name)
            broadcast(f"🔔 {self.client_name} has left the auction.")
        with clients_lock:
            if self in connected_clients:
                connected_clients.remove(self)
        try:
            self.conn.close()
        except Exception:
            pass
        print(f"[Server] Cleaned up: {self.client_name or self.addr}")


# ─────────────────────────────────────────────────────────────
#  Start server
# ─────────────────────────────────────────────────────────────
def start_server():
    import os
    from config import SERVER_IP

    # Validate cert/key files exist
    for f in (CERTFILE, KEYFILE):
        if not os.path.exists(f):
            print(f"\nERROR: '{f}' not found.")
            print("Run:  python gen_cert.py   to generate certificates first.\n")
            return

    print()
    print("╔══════════════════════════════════════════╗")
    print("║      Auction Server  —  Starting Up      ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Binding to 0.0.0.0:{SERVER_PORT}  (reachable from all network interfaces)")
    print(f"  Clients should connect to: {SERVER_IP}:{SERVER_PORT}")
    print()

    # Add sample auction items (only if state file is empty / fresh start)
    from engine.state_manager import STATE_FILE
    if not os.path.exists(STATE_FILE):
        print("[Server] Loading sample auction items...")
        auction_engine.add_item("I001", "MacBook_Pro",     "Apple_Laptop_M3",    500.0, 400.0, 300)
        auction_engine.add_item("I002", "iPhone_15_Pro",   "Apple_Smartphone",   300.0, 250.0, 240)
        auction_engine.add_item("I003", "Sony_WH1000XM5",  "Noise_Cancelling",    50.0,  40.0, 180)
        print("[Server] 3 sample items added.\n")
    else:
        print("[Server] Restored items from saved state.\n")

    # Build SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=CERTFILE, keyfile=KEYFILE)

    # Raw TCP socket → bind to ALL interfaces so other laptops can reach it
    raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    raw_socket.bind(("0.0.0.0", SERVER_PORT))
    raw_socket.listen(10)

    ssl_server = ssl_context.wrap_socket(raw_socket, server_side=True)

    print("[Server] SSL certificate loaded ✓")
    print(f"[Server] Listening for clients on port {SERVER_PORT}...")
    print("[Server] Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                conn, addr = ssl_server.accept()
                print(f"[Server] New client connected: {addr[0]}:{addr[1]}")

                handler = ClientHandler(conn, addr)
                with clients_lock:
                    connected_clients.append(handler)
                handler.start()

                print(f"[Server] Active clients: {len(connected_clients)}")

            except ssl.SSLError as e:
                print(f"[Server] SSL handshake failed: {e}")
            except Exception as e:
                print(f"[Server] Accept error: {e}")

    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        auction_engine.timer_service.shutdown()
        raw_socket.close()
        print("[Server] Goodbye.")
