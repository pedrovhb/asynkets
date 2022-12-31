import asyncio
from asyncio import Task
from datetime import timedelta
from typing import ParamSpec, AsyncIterator, Callable, Generator

from asynkets.pulse import Pulse
from asynkets.utils import ensure_coroutine_function

_P = ParamSpec("_P")


class Ticker:
    def __init__(
        self,
        period: float | timedelta,
        count: int | None = None,
        start: bool = True,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self._iteration_count = 0
        self._ready_pulse = Pulse()
        self._done_event = asyncio.Event()

        if isinstance(period, timedelta):
            # Convert timedelta to a float representing the number of seconds
            period = period.total_seconds()
        self._period = period
        self._event_loop = loop or asyncio.get_event_loop()

        self._start_time = self._event_loop.time()
        self._count = count
        self._started = False

        self._tick_handle: asyncio.TimerHandle | None = None
        self._periodic_tasks = set[Task[None]]()

        if start:
            self.start()

    def start(self) -> None:
        if self._started:
            raise RuntimeError("Ticker instance has already been started")
        self._started = True
        self._start_time = self._event_loop.time()
        self._tick()

    def _tick(self) -> None:
        """Fires off the periodic logic, and schedules the next iteration of itself.

        This method is called for the first time after `start`, and then schedules itself to be
        called again after the period has elapsed on each iteration.
        """
        if self.is_done:
            return

        # Stop scheduling iterations if the count has been reached
        if self._count is not None and self._iteration_count > self._count:
            self.stop()
            return

        self._ready_pulse.fire()
        next_time = self._iteration_count * self._period + self._start_time
        self._iteration_count += 1
        self._tick_handle = self._event_loop.call_at(next_time, self._tick)

    def stop(self) -> None:
        """Stops the Ticker instance from running."""
        if self._tick_handle is not None:
            self._tick_handle.cancel()
            self._done_event.set()

    async def wait_done(self) -> None:
        """Waits until the Ticker instance has finished running (if it has a count) or has been
        stopped.
        """
        await self._done_event.wait()

    @property
    def period(self) -> timedelta:
        return timedelta(seconds=self._period)

    @property
    def iteration_count(self) -> int:
        return self._iteration_count

    @property
    def until_next(self) -> timedelta:
        """Returns the remaining time until the next iteration.

        Returns:
            The remaining time until the next iteration.

        Raises:
            RuntimeError: If the Ticker instance has not been started, or has been stopped.
        """
        if self._tick_handle is None:
            raise RuntimeError("Ticker instance has not been started")
        if self.is_done:
            raise RuntimeError("Ticker instance has finished running")
        return timedelta(seconds=self._tick_handle.when() - self._event_loop.time())

    @property
    def is_done(self) -> bool:
        return self._done_event.is_set()

    def __await__(self) -> Generator[None, None, float]:
        """Waits until the next iteration of the Ticker instance."""
        return self._ready_pulse.__await__()

    async def _aiter(self) -> AsyncIterator[float]:
        if self.is_done:
            return
        done_future = asyncio.ensure_future(self._done_event.wait())
        while True:
            done, pending = await asyncio.wait(
                {
                    pulse := self._ready_pulse.wait(),
                    done_future,
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            if done_future in done:
                return
            yield await pulse

    def __aiter__(self) -> AsyncIterator[float]:
        return self._aiter()

    def run_periodically(
        self,
        fn: Callable[_P, object],
        to_thread: bool = False,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> Task[None]:
        """Runs a function or coroutine function at a fixed interval as per the Ticker instance.

        The function is called with the given arguments and keyword arguments, and is run in a
        separate task. The task is returned, and can be cancelled if necessary. It is marked
        as done when the Ticker instance is stopped, either by reaching the count or by calling
        `stop`.

        Args:
            fn: The function or coroutine function to run.
            to_thread: Whether to run the function in a thread. If True, the function must be a
                regular function, not a coroutine function.
            *args: The arguments to pass to the function.
            **kwargs: The keyword arguments to pass to the function.

        Returns:
            A Task that runs the function or coroutine function at a fixed interval.
        """

        if to_thread and asyncio.iscoroutinefunction(fn):
            raise ValueError("Cannot run a coroutine function in a thread")

        async def _run_periodically() -> None:
            _async_fn = ensure_coroutine_function(fn, to_thread)
            async for _ in self:
                await _async_fn(*args, **kwargs)

        task = asyncio.create_task(_run_periodically())
        self._periodic_tasks.add(task)
        return task


__all__ = ("Ticker",)


if __name__ == "__main__":
    import asyncio
    import time

    async def main() -> None:
        ticker = Ticker(1)
        async for _ in ticker:
            print(time.time())

    asyncio.run(main())
