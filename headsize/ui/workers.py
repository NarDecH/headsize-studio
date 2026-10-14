"""Background workers so slow work never blocks the UI thread."""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)


class FunctionWorker(QRunnable):
    """Run a callable in the global thread pool and report back with signals.

    Failures are reported as a message string plus the traceback for the log,
    never as an exception crossing thread boundaries.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D102 - QRunnable interface
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            self.signals.failed.emit(f"{exc}\n{traceback.format_exc()}")
            return
        self.signals.finished.emit(result)


class WorkerPool:
    """Keeps references to running workers and exposes a small submit API."""

    def __init__(self) -> None:
        self.pool = QThreadPool.globalInstance()
        self._active: list[FunctionWorker] = []

    def submit(
        self,
        fn: Callable[..., Any],
        *,
        on_finished: Callable[[Any], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> FunctionWorker:
        worker = FunctionWorker(fn, **kwargs)
        self._active.append(worker)

        def _done(result: Any) -> None:
            self._release(worker)
            if on_finished:
                on_finished(result)

        def _failed(message: str) -> None:
            self._release(worker)
            if on_failed:
                on_failed(message)

        worker.signals.finished.connect(_done)
        worker.signals.failed.connect(_failed)
        self.pool.start(worker)
        return worker

    def start(self, worker: FunctionWorker) -> FunctionWorker:
        """Start an already-built worker (used when progress is needed)."""
        self._active.append(worker)
        worker.signals.finished.connect(lambda _r: self._release(worker))
        worker.signals.failed.connect(lambda _m: self._release(worker))
        self.pool.start(worker)
        return worker

    def _release(self, worker: FunctionWorker) -> None:
        try:
            self._active.remove(worker)
        except ValueError:
            pass

    def wait(self, timeout_ms: int = 3000) -> None:
        self.pool.waitForDone(timeout_ms)

    @property
    def busy(self) -> bool:
        return bool(self._active)


__all__ = ["FunctionWorker", "WorkerPool", "WorkerSignals"]
