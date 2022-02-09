from time import time

class Timer:
    __slots__ = ('start', 'end')

    def __init__(self):
        self.start = None
        self.end = None

    @property
    def elapsed(self):
        return self.end - self.start

    def __enter__(self):
        self.start = time()

    def __exit__(self, type_, value, traceback):
        self.end = time()
