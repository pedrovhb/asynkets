# Complete the class below with the missing collection methods.

from __future__ import annotations

import asyncio
import textwrap
from asyncio import Task
from collections import deque
from collections.abc import Sequence
from datetime import timedelta
from itertools import islice, pairwise
from typing import (
    AsyncIterable,
    Callable,
    Coroutine,
    Generator,
    Generic,
    Iterable,
    overload,
    SupportsIndex,
    TypeVar,
)

from .switch import Switch

_T = TypeVar("_T")

_SyncFn = Callable[[_T], None]
_AsyncFn = Callable[[_T], Coroutine[object, object, None]]


class TimedDeque(Generic[_T], deque[_T]):
    """A TimedDeque works like a deque, but any appended items are removed after a
    certain period of time. The period is specified in seconds or as a timedelta.

    Callbacks can be added to the TimedDeque, which are called whenever an item is
    removed from the TimedDeque. The item that was removed is passed to the callback as
    an argument. The callback will also be called when the item is removed by other means,
    such as when the TimedDeque is cleared, when the item is popped, or when the item is
    removed by the deque being full (per maxlen) when a new item is appended. If the callback
    is a coroutine function, it will be scheduled as a task; otherwise, it will be scheduled
    via the event loop's call_soon method.

    The TimedDeque can be awaited, in which case it will block until the deque is empty.

    Notes:
        - Some deque methods have return types that are incompatible with those of its
            MutableSequence ABC (e.g. pop and __setitem__). These methods have a
            type: ignore[override] comment to suppress the mypy error.

    """

    def __init__(
        self,
        period: float | timedelta,
        iterable: Iterable[_T] = (),
        maxlen: int | None = None,
        callbacks: list[_SyncFn[_T] | _AsyncFn[_T]] | None = None,
    ) -> None:
        super().__init__(maxlen=maxlen)
        self._loop = asyncio.get_event_loop()

        self._period = period.total_seconds() if isinstance(period, timedelta) else period
        self._callbacks: list[_SyncFn[_T] | _AsyncFn[_T]] = callbacks or []
        self._pending_futs: dict[int, asyncio.Future[_T]] = {}

        self._empty = Switch(initial_state=len(self) == 0)

        self.extend(iterable)

    def __await__(self) -> Generator[None, None, None]:
        yield from self._empty.wait().__await__()

    def add_callback(self, callback: _SyncFn[_T] | _AsyncFn[_T]) -> None:
        self._callbacks.append(callback)

    def _resolve(self, fut: asyncio.Future[_T]) -> None:
        """Called when an item is removed. Schedules callbacks and pops the item's future."""
        item = fut.result()
        for callback in self._callbacks:
            if asyncio.iscoroutinefunction(callback):
                self._loop.create_task(callback(item))
            else:
                self._loop.call_soon(callback, item)

        if len(self) == 0:
            self._empty.set()

    def _remove_item(self, item: _T, remove_from_self: bool = False) -> None:
        """Remove an item from the deque and set its future's result.

        Args:
            item: The item to remove.
            remove_from_self: Whether to remove the item from the deque. This is necessary
                when the item is removed by the period expiring; in other cases, the item
                is already removed from the deque (e.g. when the item is popped).
        """

        if remove_from_self:
            super().remove(item)

        if id(item) in self._pending_futs:
            fut = self._pending_futs.pop(id(item))
            fut.set_result(item)

    def append(self, item: _T) -> None:

        if len(self) == self.maxlen:
            self._remove_item(self.popleft())

        super().append(item)
        self._empty.clear()

        new_fut = self._loop.create_future()
        self._pending_futs[id(item)] = new_fut
        new_fut.add_done_callback(self._resolve)
        self._loop.call_later(self._period, self._remove_item, item, True)

    def appendleft(self, item: _T) -> None:
        if len(self) == self.maxlen:
            self._remove_item(self.pop())

        super().appendleft(item)
        self._empty.clear()

        new_fut = self._loop.create_future()
        self._pending_futs[id(item)] = new_fut
        new_fut.add_done_callback(self._resolve)
        self._loop.call_later(self._period, self._remove_item, item, True)

    def clear(self) -> None:
        for item in self:
            self._remove_item(item)
        super().clear()
        self._empty.set()

    def pop(self) -> _T:  # type: ignore[override]
        item = super().pop()
        self._remove_item(item)
        return item

    def popleft(self) -> _T:
        item = super().popleft()
        self._remove_item(item)
        return item

    def remove(self, item: _T) -> None:
        super().remove(item)
        self._remove_item(item)

    def extend(self, iterable: Iterable[_T]) -> None:
        for item in iterable:
            self.append(item)

    def extendleft(self, iterable: Iterable[_T]) -> None:
        for item in iterable:
            self.appendleft(item)

    def __delitem__(self, index: SupportsIndex) -> None:  # type: ignore[override]
        item = self[index]
        super().__delitem__(index)
        self._remove_item(item)

    def __setitem__(self, index: SupportsIndex, value: _T) -> None:  # type: ignore[override]
        item = self[index]
        super().__setitem__(index, value)
        self._remove_item(item)

    def fill_from_async_iterable(self, iterable: AsyncIterable[_T]) -> Task[None]:
        """Fill the TimedDeque from an async iterable.

        Args:
            iterable: The async iterable to fill the TimedDeque from.
        """
        return self._loop.create_task(self._fill_from_async_iterable(iterable))

    async def _fill_from_async_iterable(self, iterable: AsyncIterable[_T]) -> None:
        async for item in iterable:
            self.append(item)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._period}, {super().__repr__()})"

    __str__ = __repr__


class TimeBucket(Generic[_T], Sequence[_T]):
    """A TimeBucket object is a list of TimedDeques. When an item is appended to a
    TimeBucket, it is appended to the first TimedDeque in the list. As it's removed from
    the TimedDeque, it is appended to the next TimedDeque in the list. This continues until
    the item is removed from the last TimedDeque.
    """

    def __init__(
        self,
        period: float | timedelta,
        num_buckets: int,
        iterable: Iterable[_T] = (),
    ) -> None:
        self._period = period.total_seconds() if isinstance(period, timedelta) else period
        self._empty = Switch(initial_state=True)

        self._loop = asyncio.get_event_loop()
        self._buckets: tuple[TimedDeque[_T], ...] = tuple(
            TimedDeque(period=self._period) for _ in range(num_buckets)
        )

        for a, b in pairwise(self._buckets):
            a.add_callback(b.appendleft)
        self._buckets[-1].add_callback(lambda _: self._empty.set() if len(self) == 0 else None)

        for item in iterable:
            self.append(item)

    def __await__(self) -> Generator[None, None, None]:
        yield from self._empty.wait().__await__()

    def __len__(self) -> int:
        return sum(len(bucket) for bucket in self._buckets)

    @overload
    def __getitem__(self, index: SupportsIndex | int) -> _T:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[_T]:
        ...

    def __getitem__(self, index: SupportsIndex | int | slice) -> _T | list[_T]:
        if isinstance(index, slice):
            return [item for bucket in self._buckets[index] for item in bucket]
        else:
            int_index = int(index)

            # todo - optimize this to skip buckets as in the commented code below
            if int_index >= 0:
                return next(islice(self, int_index, int_index + 1))
            else:
                return next(islice(reversed(self), -int_index, -int_index + 1))

            # for bucket in self._buckets:
            #     if int_index < len(bucket):
            #         return bucket[int_index]
            #     else:
            #         int_index -= len(bucket)
            # raise IndexError("index out of range")

    def __iter__(self) -> Generator[_T, None, None]:
        for bucket in reversed(self._buckets):
            yield from reversed(bucket)

    def __reversed__(self) -> Generator[_T, None, None]:
        for bucket in self._buckets:
            yield from bucket

    def append(self, item: _T) -> None:
        self._buckets[0].appendleft(item)
        self._empty.clear()

    def fill_from_async_iterable(self, iterable: AsyncIterable[_T]) -> Task[None]:
        """Fill the TimedDeque from an async iterable.

        Args:
            iterable: The async iterable to fill the TimedDeque from.
        """
        return self._loop.create_task(self._fill_from_async_iterable(iterable))

    async def _fill_from_async_iterable(self, iterable: AsyncIterable[_T]) -> None:
        async for item in iterable:
            self.append(item)

    def __repr__(self) -> str:
        bucket_strs: list[str] = []
        for i, bucket in enumerate(self._buckets):
            bucket_strs.append(f"T - {i * self._period}: {list(bucket)}")
            # todo - handle 0.30000000000000004
        s = textwrap.indent("\n".join(bucket_strs), " " * 4)
        return (
            f"{self.__class__.__name__}"
            f"({self._period}s window, {len(self._buckets)} buckets, {len(self)} items) [\n{s}\n]"
        )

    __str__ = __repr__


if __name__ == "__main__":

    async def main() -> None:
        td = TimedDeque(1, range(10))

        async def filler() -> None:
            for i in range(50):
                td.append(i)
                await asyncio.sleep(0.01)
                print(f"Appended {i}")

            print("Done appending")

        asyncio.create_task(filler())

        td.add_callback(print)

        await td
        print("deque is empty")

        time_bucket = TimeBucket(0.1, 5, range(10))

        for i in range(50):
            time_bucket.append(i)
            await asyncio.sleep(0.01)
            print(time_bucket)

        for item in time_bucket:
            print(item)
        print(
            time_bucket[0],
            time_bucket[1],
            time_bucket[2],
            time_bucket[3],
            time_bucket[4],
            time_bucket[20],
            time_bucket[-2],
        )

    asyncio.run(main())


__all__ = ("TimeBucket", "TimedDeque")
