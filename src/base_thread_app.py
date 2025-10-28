"""
An abstract base class for creating robust, long-running applications
with multiple background threads and graceful shutdown handling.

This class provides a reusable foundation for managing thread lifecycles,
handling OS signals (SIGINT, SIGTERM), and ensuring a clean exit.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import queue
import signal
import threading
from abc import ABC, abstractmethod


class BaseThreadApp(ABC):
    """
    An abstract base class that provides the core structure for a multi-threaded
    application. It handles thread creation, lifecycle management, and graceful
    shutdown on receiving SIGINT or SIGTERM signals.
    """

    def __init__(self):
        """
        Initializes the core synchronization primitives required for a
        multi-threaded application.
        """
        self._stop_event = threading.Event()
        self._queue = queue.Queue()
        self._data_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def _handle_signal(self, signum, frame):
        """
        Unified signal handler that is called by the OS on SIGINT or SIGTERM.
        It initiates the graceful shutdown process.

        :param signum: The signal number received.
        :param
        """
        print(f"\nSignal {signal.Signals(signum).name} received, initiating graceful shutdown.")
        self.shutdown()

    def shutdown(self):
        """
        Triggers the shutdown sequence by setting the stop event.
        This is the primary method to call to stop the application gracefully.
        """
        if not self._stop_event.is_set():
            print("🛑 Shutting down gracefully...")
            self._stop_event.set()

    @abstractmethod
    def _setup_threads(self):
        """
        Abstract method that MUST be implemented by any child class.

        This method acts as a contract, forcing the developer to define
        all necessary background threads. Threads should be created and
        appended to the `self._threads` list here.

        Example in a child class:
            input_thread = threading.Thread(target=self._my_worker)
            self._threads.append(input_thread)
        """
        pass

    def _join_threads(self):
        """
        Waits for all registered threads to complete their execution.
        This is a blocking call that ensures the main program doesn't exit
        before background tasks have cleaned up.
        """
        print("Waiting for threads to finish...")
        for thread in self._threads:
            thread.join()
        print("✅ All threads have been stopped.")

    def run(self):
        """
        The main public entry point to start the application.

        This method orchestrates the entire lifecycle:
        1. Registers the signal handlers.
        2. Calls the child class's implementation of _setup_threads().
        3. Starts all registered threads.
        4. Waits indefinitely until a shutdown is signaled.
        5. Joins all threads to ensure a clean exit.
        """
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._setup_threads()

        for thread in self._threads:
            thread.start()

        print("\n🚀 Application started. Press Ctrl+C or send SIGTERM to stop.")

        self._stop_event.wait()
        self._join_threads()
