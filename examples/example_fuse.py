from asynkets import Fuse

import asyncio


async def example_fuse() -> None:

    fuse = Fuse()
    print(f"Fuse is set: {fuse.is_set()}")

    async def wait_for_fuse():
        print("Waiting for fuse to be set...")
        await fuse.wait()
        print("Fuse is set!")

    fuse_task = asyncio.create_task(wait_for_fuse())
    await asyncio.sleep(1)
    print("Setting fuse...")
    fuse.set()
    await fuse_task


if __name__ == "__main__":

    asyncio.run(example_fuse())
