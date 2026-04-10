# main.py
import sys

def print_usage():
    print()
    print("  Usage:")
    print("    python main.py server          → Start the auction server")
    print("    python main.py client          → Connect as a bidder")
    print()
    print("  Quick start (3 laptops):")
    print("    Laptop 1 (server):  python main.py server")
    print("    Laptop 2 (client):  python main.py client")
    print("    Laptop 3 (client):  python main.py client")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "server":
        from server.auction_server import start_server
        start_server()

    elif mode == "client":
        from client.auction_client import start_client
        start_client()

    else:
        print(f"  Unknown mode: '{mode}'")
        print_usage()
        sys.exit(1)
