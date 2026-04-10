# performance_test.py
# ============================================================
#  Auction System — Performance & Stress Tester
# ============================================================
#
#  Tests the live auction server with concurrent simulated clients.
#  Measures: connection time, bid latency, throughput, error rates.
#
#  Requirements:
#    - Server must be running:  python main.py server
#    - cert.pem must be present in this folder
#
#  Usage:
#    python performance_test.py                    (default: 5 clients, 10 bids each)
#    python performance_test.py --clients 20       (20 concurrent clients)
#    python performance_test.py --clients 10 --bids 50
#    python performance_test.py --stress           (ramp-up stress test)
#    python performance_test.py --latency          (latency benchmark only)
# ============================================================

import socket
import ssl
import threading
import time
import argparse
import statistics
import random
import string
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# ─────────────────────────────────────────────────────────────
#  Config (mirrors config.py)
# ─────────────────────────────────────────────────────────────
try:
    from config import SERVER_IP, SERVER_PORT, CERTFILE
except ImportError:
    SERVER_IP   = "127.0.0.1"
    SERVER_PORT = 8080
    CERTFILE    = "cert.pem"


# ─────────────────────────────────────────────────────────────
#  Result container
# ─────────────────────────────────────────────────────────────
class TestResult:
    def __init__(self, client_id):
        self.client_id        = client_id
        self.connected        = False
        self.connect_time_ms  = 0.0
        self.bids_sent        = 0
        self.bids_accepted    = 0
        self.bids_rejected    = 0
        self.bid_latencies_ms = []
        self.errors           = []
        self.total_time_ms    = 0.0

    def avg_latency(self):
        return statistics.mean(self.bid_latencies_ms) if self.bid_latencies_ms else 0.0

    def p95_latency(self):
        if not self.bid_latencies_ms:
            return 0.0
        sorted_l = sorted(self.bid_latencies_ms)
        idx = max(0, int(len(sorted_l) * 0.95) - 1)
        return sorted_l[idx]


# ─────────────────────────────────────────────────────────────
#  Single simulated client
# ─────────────────────────────────────────────────────────────
class SimulatedClient:

    def __init__(self, client_id, num_bids, item_ids, base_bid=10.0):
        self.client_id  = client_id
        self.num_bids   = num_bids
        self.item_ids   = item_ids
        self.base_bid   = base_bid
        self.username   = f"bot_{client_id}_{''.join(random.choices(string.ascii_lowercase, k=4))}"
        self.conn       = None
        self.result     = TestResult(client_id)
        self._recv_buf  = ""
        self._lock      = threading.Lock()

    def _build_ssl_context(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(CERTFILE)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_REQUIRED
        return ctx

    def _connect(self):
        t0 = time.perf_counter()
        ctx = self._build_ssl_context()
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(10)
        self.conn = ctx.wrap_socket(raw, server_hostname=None)
        self.conn.connect((SERVER_IP, SERVER_PORT))
        self.conn.settimeout(5)
        self.result.connect_time_ms = (time.perf_counter() - t0) * 1000
        self.result.connected       = True
        self._drain()          # consume welcome banner

    def _send(self, message):
        self.conn.sendall((message + "\n").encode("utf-8"))

    def _recv_line(self, timeout=5.0):
        """Read one newline-terminated line from the server."""
        deadline = time.time() + timeout
        while "\n" not in self._recv_buf:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("No response from server")
            self.conn.settimeout(remaining)
            chunk = self.conn.recv(4096).decode("utf-8")
            if not chunk:
                raise ConnectionError("Server closed connection")
            self._recv_buf += chunk
        line, self._recv_buf = self._recv_buf.split("\n", 1)
        return line.strip()

    def _drain(self, wait=0.3):
        """Consume all pending data (banner, multi-line responses)."""
        self.conn.settimeout(wait)
        try:
            while True:
                chunk = self.conn.recv(4096).decode("utf-8")
                if not chunk:
                    break
                self._recv_buf += chunk
        except (socket.timeout, ssl.SSLError):
            pass
        self._recv_buf = ""     # discard banner content

    def _register(self):
        self._send(f"REGISTER {self.username}")
        response = self._recv_line()
        if "OK" not in response:
            raise RuntimeError(f"Registration failed: {response}")

    def _place_bid(self, item_id, amount):
        t0 = time.perf_counter()
        self._send(f"BID {item_id} {amount:.2f}")
        response = self._recv_line()
        latency  = (time.perf_counter() - t0) * 1000

        self.result.bids_sent        += 1
        self.result.bid_latencies_ms.append(latency)

        if response.startswith("OK"):
            self.result.bids_accepted += 1
        else:
            self.result.bids_rejected += 1

        return response, latency

    def run(self):
        t_start = time.perf_counter()
        try:
            self._connect()
            self._register()

            for i in range(self.num_bids):
                item_id = random.choice(self.item_ids)
                # Spread bids across a range so not all bots send identical amounts
                amount  = self.base_bid + (self.client_id * 0.1) + (i * 0.01) + random.uniform(0, 0.5)
                self._place_bid(item_id, amount)
                time.sleep(random.uniform(0.05, 0.15))    # realistic pacing

        except Exception as e:
            self.result.errors.append(str(e))
        finally:
            self.result.total_time_ms = (time.perf_counter() - t_start) * 1000
            try:
                if self.conn:
                    self._send("QUIT")
                    self.conn.close()
            except Exception:
                pass

        return self.result


# ─────────────────────────────────────────────────────────────
#  Reporter
# ─────────────────────────────────────────────────────────────
def print_report(results, test_name, wall_time_s):
    connected      = [r for r in results if r.connected]
    failed_connect = [r for r in results if not r.connected]

    all_latencies  = []
    total_sent     = 0
    total_accepted = 0
    total_rejected = 0
    total_errors   = 0

    for r in connected:
        all_latencies.extend(r.bid_latencies_ms)
        total_sent     += r.bids_sent
        total_accepted += r.bids_accepted
        total_rejected += r.bids_rejected
        total_errors   += len(r.errors)

    connect_times = [r.connect_time_ms for r in connected]

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print(f"║  {test_name:<56}║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Timestamp     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<39}║")
    print(f"║  Server        : {SERVER_IP}:{SERVER_PORT:<35}║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  CONNECTION                                              ║")
    print(f"║    Total clients     : {len(results):<34}║")
    print(f"║    Connected OK      : {len(connected):<34}║")
    print(f"║    Failed to connect : {len(failed_connect):<34}║")
    if connect_times:
        print(f"║    Avg connect time  : {statistics.mean(connect_times):<30.2f} ms  ║")
        print(f"║    Max connect time  : {max(connect_times):<30.2f} ms  ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  BID PERFORMANCE                                        ║")
    print(f"║    Total bids sent   : {total_sent:<34}║")
    print(f"║    Accepted          : {total_accepted:<34}║")
    print(f"║    Rejected          : {total_rejected:<34}║")
    if all_latencies:
        avg = statistics.mean(all_latencies)
        med = statistics.median(all_latencies)
        p95 = sorted(all_latencies)[int(len(all_latencies) * 0.95)]
        p99 = sorted(all_latencies)[int(len(all_latencies) * 0.99)]
        mn  = min(all_latencies)
        mx  = max(all_latencies)
        std = statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0
        print(f"║    Min latency       : {mn:<30.2f} ms  ║")
        print(f"║    Avg latency       : {avg:<30.2f} ms  ║")
        print(f"║    Median latency    : {med:<30.2f} ms  ║")
        print(f"║    P95 latency       : {p95:<30.2f} ms  ║")
        print(f"║    P99 latency       : {p99:<30.2f} ms  ║")
        print(f"║    Max latency       : {mx:<30.2f} ms  ║")
        print(f"║    Std deviation     : {std:<30.2f} ms  ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  THROUGHPUT                                             ║")
    throughput = total_sent / wall_time_s if wall_time_s > 0 else 0
    print(f"║    Wall time         : {wall_time_s:<30.2f} s   ║")
    print(f"║    Bids/second       : {throughput:<34.2f}║")
    print(f"║    Errors            : {total_errors:<34}║")
    print("╚══════════════════════════════════════════════════════════╝")

    if failed_connect:
        print(f"\n  ⚠  {len(failed_connect)} client(s) failed to connect:")
        for r in failed_connect:
            for e in r.errors:
                print(f"     Client {r.client_id}: {e}")

    if any(r.errors for r in connected):
        print("\n  ⚠  Runtime errors:")
        for r in connected:
            for e in r.errors:
                print(f"     Client {r.client_id}: {e}")


# ─────────────────────────────────────────────────────────────
#  Test modes
# ─────────────────────────────────────────────────────────────
ITEM_IDS = ["I001", "I002", "I003"]   # default items pre-loaded by server


def run_concurrent_test(num_clients, num_bids):
    """All clients connect and bid simultaneously."""
    print(f"\n  ▶ Concurrent test: {num_clients} clients × {num_bids} bids each")
    print(f"    Target: {SERVER_IP}:{SERVER_PORT}")
    print("    Starting...\n")

    clients = [
        SimulatedClient(i, num_bids, ITEM_IDS, base_bid=100.0 + i)
        for i in range(num_clients)
    ]

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_clients) as pool:
        futures = [pool.submit(c.run) for c in clients]
        results = [f.result() for f in as_completed(futures)]
    wall = time.perf_counter() - t0

    print_report(results, "CONCURRENT LOAD TEST", wall)


def run_latency_benchmark(num_bids=50):
    """Single client, sequential bids — pure latency measurement."""
    print(f"\n  ▶ Latency benchmark: 1 client, {num_bids} sequential bids")

    client = SimulatedClient(0, num_bids, ITEM_IDS, base_bid=200.0)
    t0     = time.perf_counter()
    result = client.run()
    wall   = time.perf_counter() - t0

    print_report([result], "LATENCY BENCHMARK (single client)", wall)


def run_stress_test():
    """Ramp clients from 1 → 5 → 10 → 20, report at each level."""
    ramp_levels = [1, 5, 10, 20]
    print(f"\n  ▶ Stress ramp test: {ramp_levels} clients per stage, 10 bids each")

    for level in ramp_levels:
        print(f"\n{'─' * 60}")
        print(f"  Stage: {level} concurrent client(s)")
        print(f"{'─' * 60}")
        clients = [
            SimulatedClient(i, 10, ITEM_IDS, base_bid=50.0 + i)
            for i in range(level)
        ]
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            futures = [pool.submit(c.run) for c in clients]
            results = [f.result() for f in as_completed(futures)]
        wall = time.perf_counter() - t0
        print_report(results, f"STRESS TEST — {level} CLIENTS", wall)
        time.sleep(1)    # brief pause between stages


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Auction System Performance Tester")
    parser.add_argument("--clients", type=int,  default=5,   help="Number of concurrent clients")
    parser.add_argument("--bids",    type=int,  default=10,  help="Bids per client")
    parser.add_argument("--stress",  action="store_true",    help="Run ramp-up stress test")
    parser.add_argument("--latency", action="store_true",    help="Run latency benchmark (1 client)")
    args = parser.parse_args()

    # Pre-flight checks
    if not os.path.exists(CERTFILE):
        print(f"\n  ERROR: '{CERTFILE}' not found.")
        print("  Copy cert.pem from the server laptop to this folder.\n")
        return

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         Auction System — Performance Tester              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Make sure the server is running:  python main.py server")
    print(f"  Server target: {SERVER_IP}:{SERVER_PORT}")

    if args.stress:
        run_stress_test()
    elif args.latency:
        run_latency_benchmark(num_bids=args.bids)
    else:
        run_concurrent_test(num_clients=args.clients, num_bids=args.bids)

    print()


if __name__ == "__main__":
    main()
