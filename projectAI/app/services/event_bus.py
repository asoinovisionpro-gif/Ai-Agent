import threading
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler):
        with self._lock:
            self._handlers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict):
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                pass

    def publish_async(self, event_type: str, payload: dict):
        t = threading.Thread(target=self.publish, args=(event_type, payload), daemon=True)
        t.start()


event_bus = EventBus()
