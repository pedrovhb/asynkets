from asyncio import Event
from functools import partialmethod


class Switch:
    def __init__(self, initial_state: bool = False) -> None:
        super().__init__()
        self._ev_on = Event()
        self._ev_off = Event()
        self._state: bool = initial_state
        self.set_state(initial_state)

    def set_state(self, state: bool) -> None:
        """Set the switch to a specific state.

        Args:
            state: The state to set.
        """
        if state:
            self.set()
        else:
            self.clear()

    def set(self) -> None:
        """Turn the switch on."""

        if not self._state:
            self._state = True
            self._ev_on.set()
            self._ev_off.clear()

    def clear(self) -> None:
        """Turn the switch off."""
        if self._state:
            self._state = False
            self._ev_off.set()
            self._ev_on.clear()

    def is_set(self) -> bool:
        """Return True if the switch is on."""
        return self._state

    def is_clear(self) -> bool:
        """Return True if the switch is off."""
        return not self._state

    async def wait(self) -> None:
        """Wait until the switch is in the "on" state.

        Returns immediately if the switch is already in the "on" state.
        """
        if not self._state:
            await self._ev_on.wait()

    async def wait_clear(self) -> None:
        """Wait until the switch is in the "off" state.

        Returns immediately if the switch is already in the "off" state.
        """
        if self._state:
            await self._ev_off.wait()

    async def wait_for(self, state: bool) -> None:
        """Wait until the switch is in a specific state. Returns immediately if it already is.

        Args:
            state: The state to wait for.
        """
        if state:
            await self.wait()
        else:
            await self.wait_clear()

    async def wait_toggle(self) -> None:
        """Wait for the switch to change from False to True, or True to False."""
        if self._state:
            await self.wait_clear()
        else:
            await self.wait()

    async def wait_toggle_to(self, state: bool) -> None:
        """Wait for the switch to change from one state to another.

        Does not return immediately if the switch is already in the target state, but waits for the
        next change.

        Args:
            state: The state to wait for.
        """
        if state:
            await self.wait_clear()
            await self.wait()
        else:
            await self.wait()
            await self.wait_clear()

    wait_toggled_on = partialmethod(wait_toggle_to, True)
    wait_toggled_off = partialmethod(wait_toggle_to, False)
