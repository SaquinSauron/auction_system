# engine/auction_engine.py
import uuid
import threading
from datetime import datetime, timedelta

from model.item           import Item, ItemStatus
from model.bid            import Bid
from model.bidder         import Bidder
from engine.protocol      import Protocol
from engine.timer_service import TimerService
from engine               import state_manager


class AuctionEngine:

    def __init__(self):
        self.items          = {}
        self.bidders        = {}
        self.item_locks     = {}
        self.processed_bids = set()
        self.broadcast_fn   = None

        self.timer_service = TimerService(self)
        state_manager.load_state(self.items)
        print("[AuctionEngine] Initialized.")

    # ─────────────────────────────────────────
    #  BIDDER MANAGEMENT
    # ─────────────────────────────────────────

    def register_bidder(self, username):
        if not username or len(username) < 2:
            return "ERROR Username must be at least 2 characters."
        for b in self.bidders.values():
            if b.username.lower() == username.lower():
                return Protocol.ERR_USERNAME_TAKEN

        bidder_id  = str(uuid.uuid4())[:8]
        new_bidder = Bidder(bidder_id, username)
        self.bidders[bidder_id] = new_bidder
        print(f"[AuctionEngine] Registered: {username}  (id={bidder_id})")
        return f"OK Registered as '{username}'.  Your session ID: {bidder_id}"

    def get_bidder_by_username(self, username):
        for b in self.bidders.values():
            if b.username.lower() == username.lower():
                return b
        return None

    def mark_disconnected(self, username):
        b = self.get_bidder_by_username(username)
        if b:
            b.is_connected = False
            print(f"[AuctionEngine] Disconnected: {username}")

    # ─────────────────────────────────────────
    #  ITEM MANAGEMENT
    # ─────────────────────────────────────────

    def add_item(self, item_id, item_name, description,
                 starting_price, reserve_price, duration_seconds):

        if item_id in self.items:
            return f"ERROR Item ID '{item_id}' already exists."

        item        = Item(item_id, item_name, description,
                           starting_price, reserve_price, duration_seconds)
        item.status = ItemStatus.ACTIVE
        self.items[item_id]      = item
        self.item_locks[item_id] = threading.Lock()

        self.timer_service.schedule_auction_close(item_id, duration_seconds)

        print(f"[AuctionEngine] Item added: {item_name} (id={item_id}, {duration_seconds}s)")

        if self.broadcast_fn:
            self.broadcast_fn(
                Protocol.new_item(item_id, item_name, starting_price, duration_seconds),
                None
            )

        state_manager.save_state(self.items)
        return f"OK Item added: {item_name} (ID: {item_id})"

    def list_active_items(self):
        active = [i for i in self.items.values() if i.status == ItemStatus.ACTIVE]
        if not active:
            return "No active auctions at the moment."
        lines = ["=== Active Auctions ==="]
        for item in active:
            lines.append(item.get_item_details())
        return "\n".join(lines)

    def get_item_details(self, item_id):
        item = self.items.get(item_id)
        if not item:
            return Protocol.ERR_ITEM_NOT_FOUND + item_id
        return item.get_item_details() + "\n" + item.get_bid_history_summary()

    # ─────────────────────────────────────────
    #  BID HANDLING
    # ─────────────────────────────────────────

    def place_bid(self, username, item_id, amount):

        # 1 — Bidder must be registered
        bidder = self.get_bidder_by_username(username)
        if not bidder:
            return Protocol.ERR_NOT_REGISTERED

        # 2 — Duplicate bid fingerprint check
        fingerprint = f"{username}:{item_id}:{amount}"
        if fingerprint in self.processed_bids:
            return Protocol.ERR_DUPLICATE_BID

        # 3 — Item must exist
        item = self.items.get(item_id)
        if not item:
            return Protocol.ERR_ITEM_NOT_FOUND + item_id

        # 4 — Acquire per-item lock (fair, non-blocking timeout)
        lock = self.item_locks.get(item_id)
        if not lock:
            return Protocol.ERR_ITEM_NOT_FOUND + item_id

        acquired = lock.acquire(timeout=3)
        if not acquired:
            return Protocol.ERR_SERVER_BUSY

        try:
            # 5 — Auction must be active
            if item.status != ItemStatus.ACTIVE:
                return Protocol.ERR_AUCTION_CLOSED + item.item_name

            # 6 — Auction must not have expired
            if item.is_expired():
                item.status = ItemStatus.CLOSED
                return Protocol.ERR_AUCTION_CLOSED + item.item_name

            # 7 — Bid must beat current highest
            if not item.is_valid_bid(amount):
                return (f"{Protocol.ERR_BID_TOO_LOW}"
                        f"{item.current_highest_bid:.2f}  — bid higher than that.")

            # 8 — Cannot outbid yourself
            if item.highest_bidder_name.lower() == username.lower():
                return Protocol.ERR_ALREADY_LEADING

            # 9 — Update item
            previous_leader          = item.highest_bidder_name
            item.current_highest_bid = amount
            item.highest_bidder_name = username

            # 10 — Record bid object
            bid = Bid(bidder.bidder_id, username, item_id, amount)
            item.add_bid_to_history(bid)
            bidder.add_bid(bid)
            self.processed_bids.add(fingerprint)

            # 11 — Anti-sniping: extend timer if bid in last 10 seconds
            seconds_left = (item.auction_end_time - datetime.now()).total_seconds()
            if 0 < seconds_left <= 10:
                item.auction_end_time += timedelta(seconds=30)
                print(f"[AuctionEngine] Anti-snipe: {item.item_name} extended 30s")
                if self.broadcast_fn:
                    self.broadcast_fn(
                        f"⏱ ANTI-SNIPE | {item.item_name} extended by 30s "
                        f"(bid placed in final 10s!)",
                        None
                    )

            # 12 — Broadcast new leader to all clients
            if self.broadcast_fn:
                self.broadcast_fn(
                    Protocol.bid_update(item_id, item.item_name,
                                        amount, username, previous_leader),
                    None
                )

            # 13 — Persist state
            state_manager.save_state(self.items)

            print(f"[AuctionEngine] Bid accepted: {bid.get_bid_summary()}")
            return f"OK Bid accepted! You are leading on '{item.item_name}' with {amount:.2f}"

        finally:
            lock.release()

    # ─────────────────────────────────────────
    #  AUCTION CLOSE (called by TimerService)
    # ─────────────────────────────────────────

    def close_auction(self, item_id):
        item = self.items.get(item_id)
        if not item:
            return

        if item_id not in self.item_locks:
            self.item_locks[item_id] = threading.Lock()

        with self.item_locks[item_id]:
            if item.status == ItemStatus.CLOSED:
                return

            item.status = ItemStatus.CLOSED
            print(f"[AuctionEngine] Closing: {item.item_name}")

            if not self.broadcast_fn:
                return

            if not item.is_reserve_met():
                self.broadcast_fn(
                    Protocol.auction_closed(
                        item_id, item.item_name,
                        "Reserve price NOT met — no winner."
                    ), None
                )
            elif item.highest_bidder_name == "None":
                self.broadcast_fn(
                    Protocol.auction_closed(
                        item_id, item.item_name,
                        "No bids received — no winner."
                    ), None
                )
            else:
                self.broadcast_fn(
                    Protocol.auction_won(
                        item_id, item.item_name,
                        item.highest_bidder_name,
                        item.current_highest_bid
                    ), None
                )

            state_manager.save_state(self.items)

    # ─────────────────────────────────────────
    #  ACCESSORS
    # ─────────────────────────────────────────

    def get_items(self):   return self.items
    def get_bidders(self): return self.bidders
