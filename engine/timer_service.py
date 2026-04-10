# engine/timer_service.py
import threading


class TimerService:

    def __init__(self, auction_engine):
        self.auction_engine = auction_engine
        self.timers         = {}
        print("[TimerService] Initialized.")

    def schedule_auction_close(self, item_id, duration_seconds):
        """Fire auction close after duration_seconds."""
        print(f"[TimerService] Scheduled close for '{item_id}' in {duration_seconds}s")
        timer = threading.Timer(
            duration_seconds,
            self._close_auction,
            args=[item_id]
        )
        timer.daemon = True
        timer.start()
        self.timers[item_id] = timer

    def _close_auction(self, item_id):
        print(f"[TimerService] Time expired for item: {item_id}")
        self.auction_engine.close_auction(item_id)

    def cancel(self, item_id):
        if item_id in self.timers:
            self.timers[item_id].cancel()
            print(f"[TimerService] Cancelled timer for: {item_id}")

    def shutdown(self):
        for timer in self.timers.values():
            timer.cancel()
        print("[TimerService] All timers cancelled.")
