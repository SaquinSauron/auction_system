# engine/protocol.py

class Protocol:

    # ── Client commands ───────────────────────────────────
    REGISTER    = "REGISTER"
    BID         = "BID"
    LIST_ITEMS  = "LIST_ITEMS"
    VIEW_ITEM   = "VIEW_ITEM"
    BID_HISTORY = "BID_HISTORY"
    MY_BIDS     = "MY_BIDS"
    ADD_ITEM    = "ADD_ITEM"
    QUIT        = "QUIT"
    HELP        = "HELP"
    PING        = "PING"

    # ── Server responses ──────────────────────────────────
    OK             = "OK"
    ERROR          = "ERROR"
    BID_UPDATE     = "BID_UPDATE"
    AUCTION_WON    = "AUCTION_WON"
    AUCTION_CLOSED = "AUCTION_CLOSED"
    NEW_ITEM       = "NEW_ITEM"
    ANTI_SNIPE     = "ANTI_SNIPE"
    PONG           = "PONG"

    # ── Error messages ────────────────────────────────────
    ERR_NOT_REGISTERED = "ERROR Please REGISTER first."
    ERR_ITEM_NOT_FOUND = "ERROR Item not found: "
    ERR_AUCTION_CLOSED = "ERROR Auction is closed: "
    ERR_BID_TOO_LOW    = "ERROR Bid too low. Current highest: "
    ERR_ALREADY_LEADING = "ERROR You are already the highest bidder."
    ERR_INVALID_AMOUNT  = "ERROR Invalid amount — please enter a number."
    ERR_SERVER_BUSY     = "ERROR Server busy. Please try again."
    ERR_DUPLICATE_BID   = "ERROR Duplicate bid — you already placed this exact bid."
    ERR_USERNAME_TAKEN  = "ERROR Username already taken. Choose another."

    HELP_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║                    AUCTION COMMANDS                          ║
╠══════════════════════════════════════════════════════════════╣
║  REGISTER <username>            Join the auction             ║
║  LIST_ITEMS                     See all active auctions      ║
║  VIEW_ITEM <itemId>             Item details + bid history   ║
║  BID <itemId> <amount>          Place a bid                  ║
║  MY_BIDS                        Your bid history             ║
║  BID_HISTORY <itemId>           All bids on an item          ║
║  ADD_ITEM <id> <n> <desc>       Add a new auction item       ║
║           <start> <reserve>                                  ║
║           <durationSeconds>                                  ║
║  PING                           Test connection              ║
║  HELP                           Show this menu               ║
║  QUIT                           Leave the auction            ║
╚══════════════════════════════════════════════════════════════╝"""

    # ── Broadcast message builders ────────────────────────

    @staticmethod
    def bid_update(item_id, item_name, amount, bidder, prev_leader):
        return (
            f"BID_UPDATE | {item_name} [{item_id}] | "
            f"New leader: {bidder} @ {amount:.2f} | "
            f"Previous leader: {prev_leader}"
        )

    @staticmethod
    def auction_won(item_id, item_name, winner, final_price):
        return (
            f"🏆 AUCTION WON | {item_name} [{item_id}] | "
            f"Winner: {winner} | Final price: {final_price:.2f}"
        )

    @staticmethod
    def auction_closed(item_id, item_name, reason):
        return f"🔔 AUCTION CLOSED | {item_name} [{item_id}] | {reason}"

    @staticmethod
    def new_item(item_id, item_name, start_price, duration):
        return (
            f"🆕 NEW ITEM | {item_name} [{item_id}] | "
            f"Starting bid: {start_price:.2f} | Duration: {duration}s"
        )
