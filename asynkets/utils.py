from __future__ import annotations

import asyncio
import functools
from typing import (
    ParamSpec,
    reveal_type,
    cast,
    TypeVar,
    TYPE_CHECKING,
    Coroutine,
    overload,
    Callable,
)

_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)


_P = ParamSpec("_P")


@overload
def ensure_coroutine_function(
    fn: Callable[_P, Coroutine[object, object, _T_co]],
    to_thread: bool = ...,
) -> Callable[_P, Coroutine[object, object, _T_co]]:
    ...


@overload
def ensure_coroutine_function(
    fn: Callable[_P, _T_co],
    to_thread: bool = ...,
) -> Callable[_P, Coroutine[object, object, _T_co]]:
    ...


def ensure_coroutine_function(
    fn: Callable[_P, _T_co] | Callable[_P, Coroutine[object, object, _T_co]],
    to_thread: bool = False,
) -> Callable[_P, Coroutine[object, object, _T_co]]:
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

    reveal_type(my_async_ensured)
    reveal_type(my_sync_ensured)
    reveal_type(my_sync_ensured_to_thread)

    async def main() -> None:

        a = await my_async_ensured(4, [1, 3, 2])
        b = await my_sync_ensured(4, [1, 3, 2])
        c = await my_sync_ensured_to_thread(4, [1, 3, 2])

        reveal_type(a)  # asynkets/utils.py:94: note: Revealed type is "builtins.int"
        reveal_type(b)  # asynkets/utils.py:95: note: Revealed type is "builtins.int"
        reveal_type(c)  # asynkets/utils.py:96: note: Revealed type is "builtins.int"

    asyncio.run(main())
