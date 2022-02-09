import asyncio
import threading


class ExecutionThreadPool:
    __slots__ = ('_loop', 'max_threads', 'worker_queue', 'threads')

    def __init__(self, max_threads: int):
        self._loop = asyncio.get_event_loop()
        self.max_threads = max_threads
        self.worker_queue = []
        self.threads = []

    def submit(self, fn, *args):
        future = self._loop.create_future()

        def wrapped():
            res = fn(*args)
            self._loop.call_soon_threadsafe(future.set_result, res)

        t = threading.Thread(target=wrapped, args=())
        t.daemon = False
        t.start()

        return future
