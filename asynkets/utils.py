from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import AsyncIterator, Iterable, AsyncIterable

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from typing import Callable, cast, Coroutine, TYPE_CHECKING, TypeVar

_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)


_P = ParamSpec("_P")

_A = TypeVar("_A")
_B = TypeVar("_B")


def ensure_coroutine_function(
    fn: Callable[_P, _T_co] | Callable[_P, Coroutine[_A, _B, _T_co]],
    to_thread: bool = False,
) -> Callable[_P, Coroutine[_A, _B, _T_co]]:
    """Given a sync or async function, return an async function.

    Args:
        fn: The function to ensure is async.
        to_thread: Whether to run the function in a thread, if it is sync.

    Returns:
        An async function that runs the original function.
    """

    if asyncio.iscoroutinefunction(fn):
        return fn

    _fn_sync = cast(Callable[_P, _T_co], fn)
    if to_thread:

        @functools.wraps(_fn_sync)
        async def _async_fn(*__args: _P.args, **__kwargs: _P.kwargs) -> _T_co:
            return await asyncio.to_thread(_fn_sync, *__args, **__kwargs)

    else:

        @functools.wraps(_fn_sync)
        async def _async_fn(*__args: _P.args, **__kwargs: _P.kwargs) -> _T_co:
            return _fn_sync(*__args, **__kwargs)

    return _async_fn


async def iter_to_aiter(iterable: Iterable[_T], /, target_dt: float = 0.0005) -> AsyncIterator[_T]:
    """Convert an iterable to an async iterator, running the iterable in a
    thread.

        Args:
            iterable: The iterable to convert.
            target_dt: The target maximum time to possibly block the event loop
    for. Defaults to 0.0005.
                Note that this is not a hard limit, and the actual time spent
    blocking the event loop
                may be longer than this. See also sys.getswitchinterval().

        Yields:
            Items from the iterable.

        Examples:
            >>> async def demo_iter_to_thread():
            ...     async for item in iter_to_aiter(range(5)):
            ...         print(item)
            >>> asyncio.run(demo_iter_to_thread())
            0
            1
            2
            3
            4
    """
    iterator = iter(iterable)
    loop = asyncio.get_running_loop()
    result: list[_T] = []

    def run_iterator() -> None:
        # We assign variables to the function scope to avoid the overhead of
        # looking them up in the closure scope during the hot loop. We also
        # reuse the same list to avoid the overhead of allocating a new list
        # every time, and have it in shared memory to avoid the overhead of
        # copying the list to the main thread.
        _result_append = result.append
        _iterator_next = iterator.__next__
        _time_monotonic = time.monotonic
        _target_t = _time_monotonic() + target_dt

        try:
            while _time_monotonic() < _target_t:
                _result_append(_iterator_next())
        except StopIteration:
            raise StopAsyncIteration

    while True:
        try:
            # Run the iterator in a thread until we've reached the target time.
            await loop.run_in_executor(None, run_iterator)

            # Yield the results.
            for item in result:
                yield item

            # Clear the results.
            result.clear()
        except StopAsyncIteration:
            # Yield the remaining items in the result buffer.
            for item in result:
                yield item
            return


def ensure_async_iterator(iterable: Iterable[_T] | AsyncIterable[_T]) -> AsyncIterator[_T]:
    """Given an iterable or async iterable, return an async iterable.

    Args:
        iterable: The iterable to ensure is async.
        to_thread: Whether to run the iterable in a thread, if it is sync.

    Returns:
        An async iterable that runs the original iterable.
    """
    if isinstance(iterable, AsyncIterable):
        return aiter(iterable)

    return aiter(iter_to_aiter(iterable))


def merge_async_iterables(*async_iters: Iterable[_T] | AsyncIterable[_T]) -> AsyncIterator[_T]:
    """Merge multiple iterables or async iterables into one, yielding items as they are received.

    Args:
        async_iters: The async iterators to merge.

    Yields:
        Items from the async iterators, as they are received.

    Examples:
        >>> async def a():
        ...     for i in range(3):
        ...         await asyncio.sleep(0.07)
        ...         yield i
        >>> async def b():
        ...     for i in range(100, 106):
        ...         await asyncio.sleep(0.03)
        ...         yield i
        >>> async def demo_amerge():
        ...     async for item in merge_async_iterables(a(), b()):
        ...         print(item)
        >>> asyncio.run(demo_amerge())
        100
        101
        0
        102
        103
        1
        104
        105
        2
    """

    async def _inner() -> AsyncIterator[_T]:
        futs: dict[asyncio.Future[_T], AsyncIterator[_T]] = {}
        for it in async_iters:
            async_it = ensure_async_iterator(it)
            fut = asyncio.ensure_future(anext(async_it))
            futs[fut] = async_it

        while futs:
            done, _ = await asyncio.wait(futs, return_when=asyncio.FIRST_COMPLETED)
            for done_fut in done:
                try:
                    yield done_fut.result()
                except StopAsyncIteration:
                    pass
                else:
                    fut = asyncio.ensure_future(anext(futs[done_fut]))
                    futs[fut] = futs[done_fut]
                finally:
                    del futs[done_fut]

    return _inner()


if __name__ == "__main__":

    if not TYPE_CHECKING:

        def reveal_type(obj: object) -> None:
            print(f"{obj!r} is {type(obj)}")

    async def my_async_fn(arg1: _T, arg2: list[_T]) -> _T:
        for i in arg2:
            print(i)
        return arg1

    def my_sync_fn(arg1: _T, arg2: list[_T]) -> _T:
        for i in arg2:
            print(i)
        return arg1

    my_async_ensured = ensure_coroutine_function(my_async_fn)
    my_sync_ensured = ensure_coroutine_function(my_sync_fn, to_thread=False)
    my_sync_ensured_to_thread = ensure_coroutine_function(my_sync_fn, to_thread=True)

    # reveal_type(my_async_ensured)
    # reveal_type(my_sync_ensured)
    # reveal_type(my_sync_ensured_to_thread)

    async def main() -> None:

        a = await my_async_ensured(4, [1, 3, 2])
        b = await my_sync_ensured(4, [1, 3, 2])
        c = await my_sync_ensured_to_thread(4, [1, 3, 2])

        print(a, b, c)

        # reveal_type(a)  # asynkets/utils.py:94: note: Revealed type is "builtins.int"
        # reveal_type(b)  # asynkets/utils.py:95: note: Revealed type is "builtins.int"
        # reveal_type(c)  # asynkets/utils.py:96: note: Revealed type is "builtins.int"

    asyncio.run(main())

__all__ = ("ensure_coroutine_function",)
