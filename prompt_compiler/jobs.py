"""Session-owned background work. Workers never access Streamlit state."""
from threading import Event, Lock, Thread
from time import monotonic


class BackgroundJob:
    def __init__(self, worker, fingerprint):
        self.cancel_event = Event()
        self.done = Event()
        self._lock = Lock()
        self._state = {'stage': 'starting', 'message': 'Getting started…', 'api_calls': 0}
        self.result = None
        self.error = None
        self.fingerprint = fingerprint
        self.started_at = monotonic()
        def run():
            try:
                self.result = worker(self.cancel_event, self.update)
            except Exception as exc:
                self.error = str(exc)
            finally:
                self.done.set()
        self._thread = Thread(target=run, daemon=True, name='prompt-compiler-generation')

    def start(self):
        self._thread.start()
        return self

    def update(self, value):
        with self._lock:
            self._state.update(value)

    def snapshot(self):
        with self._lock:
            return {**self._state, 'elapsed_seconds': monotonic() - self.started_at,
                    'cancelling': self.cancel_event.is_set(), 'done': self.done.is_set()}

    def cancel(self):
        self.cancel_event.set()
        self.update({'message': 'Stopping after the active request…'})

    def accepts_result(self, fingerprint):
        return self.done.is_set() and not self.cancel_event.is_set() and self.fingerprint == fingerprint
