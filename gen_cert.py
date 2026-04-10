# gen_cert.py
# Generates a self-signed SSL cert that works over a local network.
# Run this ONLY on the SERVER laptop, then copy cert.pem to client laptops.
#
# Usage:
#   python gen_cert.py                      (uses SERVER_IP from config.py)
#   python gen_cert.py 192.168.1.100        (override IP via argument)

import sys
import datetime
import ipaddress

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("ERROR: cryptography library not found.")
    print("Install it with:  pip install cryptography")
    sys.exit(1)

from config import SERVER_IP, CERTFILE, KEYFILE

def generate_cert(ip_address: str):
    print("=" * 50)
    print("  Auction SSL Certificate Generator")
    print("=" * 50)
    print(f"  Generating certificate for IP: {ip_address}")
    print()

    # ── Step 1: Generate RSA private key ──────────────────
    print("[1/4] Generating RSA 2048-bit private key...")
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    print("      Done.")

    # ── Step 2: Build certificate ─────────────────────────
    print("[2/4] Building X.509 certificate...")
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ip_address),
    ])

    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address(ip_address)),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256(), default_backend())
    )
    print("      Done.")

    # ── Step 3: Save private key ──────────────────────────
    print(f"[3/4] Saving private key → {KEYFILE}  (server only, never share)")
    with open(KEYFILE, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))
    print("      Done.")

    # ── Step 4: Save certificate ──────────────────────────
    print(f"[4/4] Saving certificate  → {CERTFILE}  (copy this to client laptops)")
    with open(CERTFILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print("      Done.")

    print()
    print("=" * 50)
    print("  Certificate generated successfully!")
    print()
    print("  NEXT STEPS:")
    print(f"  1. Copy '{CERTFILE}' to BOTH client laptops")
    print(f"     (place it in the same folder as main.py)")
    print(f"  2. Set SERVER_IP = \"{ip_address}\" in config.py")
    print(f"     on ALL THREE laptops")
    print(f"  3. Run:  python main.py server   (on server laptop)")
    print(f"  4. Run:  python main.py client   (on each client laptop)")
    print("=" * 50)


if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else SERVER_IP
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        print(f"ERROR: '{ip}' is not a valid IP address.")
        sys.exit(1)
    generate_cert(ip)
