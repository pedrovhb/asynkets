from __future__ import annotations

from typing import cast, SupportsInt

from .switch import Switch


class EventfulCounter(SupportsInt):
    """EventfulCounter

    This class represents a counter that can be incremented or decremented, and
    also has (optional) minimum and maximum values that it can reach.

    The counter has SwitchEvent instances for being at/beyond the minimum and
    maximum values. This allows waiting for the counter to reach the minimum value,
    to reach the maximum value, to cross from below the minimum value to above the
    minimum value, or to cross from above to below the maximum value.

    The counter can be incremented or decremented by any amount with the inc() and
    dec() methods, or by using the += and -= operators. The counter can also be
    set to a specific value with the set() method.

    If the clamp_to_bounds flag is set, the counter will be clamped to the minimum
    and maximum values when it reaches them. Otherwise, it will continue to
    increment or decrement past them.

    This class inherits from SupportsFloat, which means it can be cast to a
    int using the int() function. It also supports comparison using the
    `>`, `<`, and `==` operators. It can be cast to a boolean using the
    bool() function, which returns True if the counter has a value greater
    than 0.

    Args:
        initial_value: The initial value of the counter. Defaults to 0.

        max_value: The maximum value that the counter can reach, or None. If none, the
            counter has no maximum value. Defaults to None.

        min_value: The minimum value that the counter can reach, or None. If none, the
            counter has no minimum value. Defaults to None.

        clamp_to_bounds: Whether the counter should be clamped to the minimum and maximum values.
            Defaults to False.
    """

    def __init__(
        self,
        initial_value: int = 0,
        max_value: int | None = None,
        min_value: int | None = None,
        clamp_to_bounds: bool = False,
    ) -> None:
        self._counter: int = initial_value
        self._max_value = max_value
        self._min_value = min_value
        self._clamp_to_bounds = clamp_to_bounds

        if max_value is not None and min_value is not None and max_value < min_value:
            raise ValueError("max_value must be greater than min_value")

        if max_value is not None and initial_value > max_value and clamp_to_bounds:
            raise ValueError(
                "initial_value must be less than max_value when clamp_to_bounds is True"
            )

        if min_value is not None and initial_value < min_value and clamp_to_bounds:
            raise ValueError(
                "initial_value must be greater than min_value when clamp_to_bounds is True"
            )

        if min_value is not None and max_value is not None and min_value == max_value:
            raise ValueError("min_value and max_value cannot be equal")

        self._min_ev = Switch()
        self._max_ev = Switch()
        self.set(initial_value)

    def inc(self, by: SupportsInt = 1) -> None:
        """Increment the counter."""
        self.set(self._counter + int(by))

    def dec(self, by: SupportsInt = 1) -> None:
        """Decrement the counter."""
        self.set(self._counter - int(by))

    @property
    def min_value(self) -> int | None:
        """Return the minimum value of the counter."""
        return self._min_value

    @min_value.setter
    def min_value(self, value: int | None) -> None:
        if value is None:
            self._min_value = None
            self._min_ev.set_state(False)
        else:
            if (
                self._max_value is not None
                and value > self._max_value
                and self._clamp_to_bounds
            ):
                raise ValueError("min_value cannot be greater than max_value")

            if value > self._counter and self._clamp_to_bounds:
                raise ValueError(
                    "min_value cannot be greater than current value when clamp_to_bounds is True"
                )

            self._min_value = value
            self.set(self._counter)

    @property
    def max_value(self) -> int | None:
        """Return the maximum value of the counter."""
        return self._max_value

    @max_value.setter
    def max_value(self, value: int | None) -> None:
        if value is None:
            self._max_value = None
            self._max_ev.set_state(False)
        else:
            if (
                self._min_value is not None
                and value < self._min_value
                and self._clamp_to_bounds
            ):
                raise ValueError("max_value cannot be less than min_value")

            if value < self._counter and self._clamp_to_bounds:
                raise ValueError(
                    "max_value cannot be less than current value when clamp_to_bounds is True"
                )

            self._max_value = value
            self.set(self._counter)

    def set(self, value: int) -> None:
        """Set the counter to a specific value."""
        self._counter = value

        if self._max_value is not None and self._counter >= self._max_value:
            self._max_ev.set()
            if self._clamp_to_bounds:
                self._counter = self._max_value

        if self._min_ev.is_set() and self._counter > cast(int, self._min_value):
            self._min_ev.clear()

        if self._min_value is not None and self._counter <= self._min_value:
            self._min_ev.set()
            if self._clamp_to_bounds:
                self._counter = self._min_value

        if self._max_ev.is_set() and self._counter < cast(int, self._max_value):
            self._max_ev.clear()

    def __int__(self) -> int:
        return self._counter

    def __iadd__(self, other: SupportsInt) -> EventfulCounter:
        self.inc(by=other)
        return self

    def __isub__(self, other: SupportsInt) -> EventfulCounter:
        self.dec(by=other)
        return self

    def __gt__(self, other: SupportsInt) -> bool:
        return int(self) > int(other)

    def __lt__(self, other: SupportsInt) -> bool:
        return int(self) < int(other)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SupportsInt):
            return int(self) == int(other)
        return False

    def __bool__(self) -> bool:
        return bool(self._counter)

    def min_is_set(self) -> bool:
        """Return True if the counter is at or below the minimum value."""
        return self._min_ev.is_set()

    def max_is_set(self) -> bool:
        """Return True if the counter is at or above the maximum value."""
        return self._max_ev.is_set()

    async def wait_max(self) -> None:
        """Wait until the counter reaches its maximum value.

        Returns immediately if it already has.
        """
        await self._max_ev.wait()

    async def wait_min(self) -> None:
        """Wait until the counter reaches its minimum value.

        Returns immediately if it already has.
        """
        await self._min_ev.wait()

    async def wait_max_clear(self) -> None:
        """Wait for the counter to be below its maximum value.

        Returns immediately if it already is.
        """
        await self._max_ev.wait_clear()

    async def wait_min_clear(self) -> None:
        """Wait for the counter to be above its minimum value.

        Returns immediately if it already is.
        """
        await self._min_ev.wait_clear()

    def __str__(self) -> str:
        return (
            f"<{self.__class__.__name__}: {self._counter} "
            f"(min: {self._min_value}, max: {self._max_value})>"
        )

    __repr__ = __str__


__all__ = ("EventfulCounter",)
