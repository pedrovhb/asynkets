import asyncio
from datetime import timedelta

import pytest

from asynkets import PeriodicPulse


@pytest.mark.asyncio
async def test_periodic_pulse_with_timedelta_period():
    periodic_pulse = PeriodicPulse(timedelta(seconds=1))
    assert periodic_pulse.period == timedelta(seconds=1)


@pytest.mark.asyncio
async def test_periodic_pulse_with_count():
    periodic_pulse = PeriodicPulse(timedelta(seconds=0.1))

    async def iter_counter():
        count = 0
        async for _ in periodic_pulse:
            count += 1
        return count

    counter = asyncio.create_task(iter_counter())
    assert periodic_pulse.period == timedelta(seconds=0.1)

    await asyncio.sleep(0.35)
    periodic_pulse.close()
    assert await counter == 3
