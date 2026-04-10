# model/bidder.py
from datetime import datetime


class Bidder:

    def __init__(self, bidder_id, username):
        self.bidder_id    = bidder_id
        self.username     = username
        self.is_connected = True
        self.joined_at    = datetime.now()
        self.my_bids      = []

    def add_bid(self, bid):
        self.my_bids.append(bid)

    def get_total_bids(self) -> int:
        return len(self.my_bids)

    def get_highest_bid_on_item(self, item_id) -> float:
        bids = [b.amount for b in self.my_bids if b.item_id == item_id]
        return max(bids) if bids else 0.0

    def get_bidder_summary(self) -> str:
        return (
            f"Bidder[{self.bidder_id}]  {self.username}  "
            f"| Connected: {self.is_connected}  "
            f"| Total bids: {len(self.my_bids)}  "
            f"| Joined: {self.joined_at.strftime('%H:%M:%S')}"
        )
