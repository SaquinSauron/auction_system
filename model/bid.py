# model/bid.py
import uuid
from datetime import datetime


class Bid:

    def __init__(self, bidder_id, bidder_name, item_id, amount):
        self.bid_id      = str(uuid.uuid4())[:8]
        self.bidder_id   = bidder_id
        self.bidder_name = bidder_name
        self.item_id     = item_id
        self.amount      = amount
        self.timestamp   = datetime.now()

    def get_bid_summary(self) -> str:
        return (
            f"Bid[{self.bid_id}]  {self.bidder_name:<12} "
            f"${self.amount:.2f}   "
            f"@ {self.timestamp.strftime('%H:%M:%S')}"
        )
