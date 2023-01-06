import asyncio
import collections


class Fuse:
    """Similar to asyncio.Event, but can only be set once."""

    def __init__(self) -> None:
        self._waiters: collections.deque[asyncio.Future[bool]] = collections.deque()
        self._value = False

    def set(self) -> None:
        """Set the fuse."""
        if not self._value:
            self._value = True

            for fut in self._waiters:
                if not fut.done():
                    fut.set_result(True)

    def is_set(self) -> bool:
        """Return True if the fuse is set."""
        return self._value

    async def wait(self) -> None:
        """Wait for the fuse to be set."""
        if self._value:
            return

        fut = asyncio.get_event_loop().create_future()
        self._waiters.append(fut)
        try:
            await fut
        finally:
            self._waiters.remove(fut)


__all__ = ("Fuse",)
