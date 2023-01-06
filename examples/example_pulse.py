import asyncio

from asynkets import Pulse


async def example_pulse():
    pulse = Pulse()

    pulse.add_pulse_callback(lambda: print("Pulse callback!"))

    async def do_work():
        print("much busy...")
        await asyncio.sleep(1)

    async def pulse_fire_task():
        for _ in range(6):
            await do_work()
            pulse.fire()

    # Start emitting pulses
    asyncio.create_task(pulse_fire_task())

    # Await for the pulse once
    await pulse
    print("I can feel a pulse...")

    # Use pulse as an asynchronous iterator;
    # this will yield every time the pulse is triggered
    async def pulse_wait_task():
        async for _ in pulse:
            print("Pulse iterator got something!")
        print("Pulse async iteration stopped.")

    asyncio.create_task(pulse_wait_task())

    # Wait for the pulse to be fired 5 times
    for i in range(5):
        await pulse
        print("Felt pulse, number", i)

    await asyncio.sleep(0.5)

    # Close the pulse
    print("Closing pulse...")
    pulse.close()

    await asyncio.sleep(1)
    print("Bye!")


if __name__ == "__main__":
    asyncio.run(example_pulse())
