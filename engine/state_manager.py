# engine/state_manager.py
import os

STATE_FILE = "auction_state.txt"


def save_state(items):
    try:
        with open(STATE_FILE, "w") as f:
            for item in items.values():
                f.write(
                    f"{item.item_id}|{item.item_name}|{item.description}|"
                    f"{item.starting_price}|{item.current_highest_bid}|"
                    f"{item.highest_bidder_name}|{item.reserve_price}|"
                    f"{item.status.value}\n"
                )
        print("[StateManager] State saved.")
    except Exception as e:
        print(f"[StateManager] Save failed: {e}")


def load_state(items):
    from model.item import Item, ItemStatus

    if not os.path.exists(STATE_FILE):
        print("[StateManager] No saved state — starting fresh.")
        return

    try:
        with open(STATE_FILE, "r") as f:
            count = 0
            for line in f:
                parts = line.strip().split("|")
                if len(parts) < 8:
                    continue

                item_id     = parts[0]
                name        = parts[1]
                desc        = parts[2]
                start_price = float(parts[3])
                curr_bid    = float(parts[4])
                leader      = parts[5]
                reserve     = float(parts[6])
                status_str  = parts[7]

                # Restore with duration=0 (timer already ran; status determines active/closed)
                item = Item(item_id, name, desc, start_price, reserve, 0)
                item.current_highest_bid = curr_bid
                item.highest_bidder_name = leader

                try:
                    item.status = ItemStatus(status_str)
                except ValueError:
                    item.status = ItemStatus.CLOSED

                items[item_id] = item
                count += 1

        print(f"[StateManager] Loaded {count} item(s) from saved state.")
    except Exception as e:
        print(f"[StateManager] Load failed: {e}")


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    print("[StateManager] State cleared.")
