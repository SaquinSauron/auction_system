# client/auction_client.py
import socket
import ssl
import threading
import os

from config import SERVER_IP, SERVER_PORT, CERTFILE


def start_client():
    # Validate cert file exists
    if not os.path.exists(CERTFILE):
        print(f"\nERROR: '{CERTFILE}' not found.")
        print("Copy 'cert.pem' from the server laptop to this folder.\n")
        return

    print()
    print("╔══════════════════════════════════════════╗")
    print("║        Auction Client  —  SSL Mode       ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Connecting to server: {SERVER_IP}:{SERVER_PORT}")
    print()

    try:
        # Build SSL context (CLIENT side — verify the server cert)
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.load_verify_locations(CERTFILE)
        ssl_context.check_hostname = False      # We verify by IP, not hostname
        ssl_context.verify_mode    = ssl.CERT_REQUIRED

        raw_socket    = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_socket.settimeout(10)
        client_socket = ssl_context.wrap_socket(raw_socket, server_hostname=None)
        client_socket.connect((SERVER_IP, SERVER_PORT))
        client_socket.settimeout(None)

        print("  SSL Handshake   : OK ✓")
        print(f"  Cipher in use   : {client_socket.cipher()[0]}")
        print("  Connection      : Encrypted ✓")
        print()

        # ── Background thread: receive messages from server ──
        stop_event = threading.Event()

        def listen():
            buffer = ""
            try:
                while not stop_event.is_set():
                    data = client_socket.recv(4096).decode("utf-8")
                    if not data:
                        print("\n[Disconnected from server]")
                        stop_event.set()
                        break
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            print(f"\r{line}")
                            print("» ", end="", flush=True)
            except ssl.SSLError as e:
                if not stop_event.is_set():
                    print(f"\n[SSL Error] {e}")
            except OSError:
                pass
            except Exception as e:
                if not stop_event.is_set():
                    print(f"\n[Connection closed] {e}")
            finally:
                stop_event.set()

        listener = threading.Thread(target=listen, daemon=True)
        listener.start()

        # ── Main thread: send user commands ──────────────────
        print("  Commands: REGISTER <name>  |  LIST_ITEMS  |  BID <id> <amount>")
        print("            VIEW_ITEM <id>   |  MY_BIDS     |  HELP  |  QUIT")
        print("──────────────────────────────────────────────────────────────")

        while not stop_event.is_set():
            try:
                user_input = input("» ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Disconnecting...")
                break

            if not user_input:
                continue

            try:
                client_socket.sendall((user_input + "\n").encode("utf-8"))
            except OSError:
                print("  Connection lost.")
                break

            if user_input.upper() == "QUIT":
                break

        stop_event.set()

    except ssl.SSLCertVerificationError as e:
        print(f"\nERROR: SSL certificate verification failed.")
        print(f"       {e}")
        print(f"Make sure 'cert.pem' was copied from the server laptop.")

    except ConnectionRefusedError:
        print(f"\nERROR: Could not connect to {SERVER_IP}:{SERVER_PORT}")
        print("  → Is the server running?")
        print("  → Is SERVER_IP correct in config.py?")
        print("  → Are both laptops on the same network?")

    except socket.timeout:
        print(f"\nERROR: Connection timed out trying to reach {SERVER_IP}:{SERVER_PORT}")
        print("  → Check that the server is running and reachable.")

    except Exception as e:
        print(f"\nClient error: {e}")

    finally:
        try:
            client_socket.close()
        except Exception:
            pass
        print("\n  Client closed. Goodbye!")
