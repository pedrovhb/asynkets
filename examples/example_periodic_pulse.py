import asyncio
import time

from asynkets import PeriodicPulse


async def example_periodic_pulse() -> None:

    periodic_pulse = PeriodicPulse(1)

    # Register a callback to be called every time the pulse is emitted
    periodic_pulse.add_pulse_callback(lambda: print("Pulse callback!"))

    starting_time = time.time()

    # Use pulse as an asynchronous iterator;
    # this will yield every time the pulse is triggered, and the value
    # yielded is the current timestamp as per time.time()
    async for t in periodic_pulse:
        print("Pulse!", t)

        if t > starting_time + 5:
            print("Stopping pulse async iteration...")
            break

    # The callback will keep running until the pulse is closed
    await asyncio.sleep(2)

    print("Closing pulse...")
    periodic_pulse.close()
    print("Closed. No more callbacks will be called.")

    await asyncio.sleep(1)
    print("Bye!")


if __name__ == "__main__":
    asyncio.run(example_periodic_pulse())
