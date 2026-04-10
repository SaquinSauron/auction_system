# model/item.py
from datetime import datetime, timedelta
from enum import Enum


class ItemStatus(Enum):
    WAITING = "WAITING"
    ACTIVE  = "ACTIVE"
    CLOSED  = "CLOSED"


class Item:

    def __init__(self, item_id, item_name, description,
                 starting_price, reserve_price, duration_seconds):

        self.item_id             = item_id
        self.item_name           = item_name
        self.description         = description
        self.starting_price      = starting_price
        self.current_highest_bid = starting_price
        self.highest_bidder_name = "None"
        self.reserve_price       = reserve_price
        self.status              = ItemStatus.WAITING
        self.auction_end_time    = datetime.now() + timedelta(seconds=duration_seconds)
        self.bid_history         = []

    def is_valid_bid(self, amount) -> bool:
        return amount > self.current_highest_bid

    def is_expired(self) -> bool:
        return datetime.now() > self.auction_end_time

    def is_reserve_met(self) -> bool:
        return self.current_highest_bid >= self.reserve_price

    def add_bid_to_history(self, bid):
        self.bid_history.append(bid)

    def time_remaining(self) -> str:
        remaining = (self.auction_end_time - datetime.now()).total_seconds()
        if remaining <= 0:
            return "ENDED"
        mins, secs = divmod(int(remaining), 60)
        return f"{mins}m {secs:02d}s"

    def get_item_details(self) -> str:
        return (
            f"Item[{self.item_id}] {self.item_name}\n"
            f"  Description  : {self.description}\n"
            f"  Current Bid  : {self.current_highest_bid:.2f}  "
            f"(reserve: {self.reserve_price:.2f})\n"
            f"  Leader       : {self.highest_bidder_name}\n"
            f"  Status       : {self.status.value}\n"
            f"  Time Left    : {self.time_remaining()}"
        )

    def get_bid_history_summary(self) -> str:
        if not self.bid_history:
            return f"  No bids yet on {self.item_name}."
        lines = [f"  Bid history for {self.item_name}:"]
        for bid in self.bid_history:
            lines.append(f"    {bid.get_bid_summary()}")
        return "\n".join(lines)
