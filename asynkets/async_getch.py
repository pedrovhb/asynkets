import asyncio
import sys
from typing import AsyncIterator


async def async_getch() -> AsyncIterator[bytes]:
    """An async iterator that yields characters read from the terminal in a non-blocking way."""

    is_windows = sys.platform == "win32"

    if is_windows:
        # Haven't actually tested this on Windows yet, hopefully it works
        import msvcrt

        getch = msvcrt.getch  # type: ignore

        def cleanup() -> None:
            pass

    else:
        import termios
        import tty

        # Save the current terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

        # Set the terminal to cbreak mode
        tty.setcbreak(sys.stdin)

        getch = sys.stdin.buffer.read1  # type: ignore

        def cleanup() -> None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    # on_char_ready will be called when stdin has a character;
    # it will put the character in a queue, and we'll later
    # yield from it
    char_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def on_char_ready() -> None:
        bs: bytes = getch()
        char_queue.put_nowait(bs)

    # Add a reader for sys.stdin to call on_char_ready when appropriate
    loop = asyncio.get_running_loop()
    loop.add_reader(sys.stdin, on_char_ready)

    try:
        while True:
            yield await char_queue.get()
    finally:
        # Remove the reader for sys.stdin and restore the previous blocking + tty state
        loop.remove_reader(sys.stdin)
        cleanup()


__all__ = ("async_getch",)
