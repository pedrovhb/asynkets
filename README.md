
# asynkets

`asynkets` is a Python library which provides miscellaneous utilities that are useful when writing `asyncio` code.

Provided utilities include:

- *`Switch`*: A class that allows waiting for state changes of a switch that can be turned on or off. It provides async methods for waiting until it is in a specific state, and for waiting until it switches to a different state.
- *`EventfulCounter`*: A counter that can be incremented or decremented and has optional minimum and maximum values. It also provides async methods for waiting until some threshold (either low or high) is reached, or until some threshold is reached or left, by leveraging Switches.
- *`Fuse`*: Similar to asyncio's Event, but can only be set once.
- *`Pulse`*: A pulse that can be triggered and waited for. It can also be given a function to call when it is triggered and can be used as an async iterator.
- *`PeriodicPulse`*: A pulse that fires periodically at a specified interval and delay. It can be closed and used as an async iterator like the Pulse class.
- *`ensure_coroutine_function`* and *`ensure_async_iterator`*: return guaranteed async versions of a sync or async function or iterable, respectively. If the function or iterable is synchronous, it will be wrapped to be async; if it is already async, it will be returned as-is.
- *`merge_async_iterables`*: Merges multiple iterables or async iterables into one, yielding items as they are received.


## Installation

`asynkets` is available on PyPI and can be installed with `pip` or your favorite package manager.

```bash
pip install asynkets
```

## Usage

(todo)

## License

The library is provided under the MIT license. See the [LICENSE](LICENSE) file for more information.
