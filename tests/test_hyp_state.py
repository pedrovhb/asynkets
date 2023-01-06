import pytest

from asynkets import EventfulCounter
from hypothesis import given, strategies as st
from hypothesis.stateful import invariant, precondition, rule, RuleBasedStateMachine
from hypothesis.strategies import DrawFn


@st.composite
def eventful_counters(draw: DrawFn) -> EventfulCounter:

    initial_value = draw(st.integers())
    clamp_to_bounds = draw(st.booleans())

    min_value = draw(
        st.one_of(
            st.none(),
            st.integers(max_value=initial_value if clamp_to_bounds else None),
        )
    )

    if clamp_to_bounds:
        vals = [v for v in (min_value, initial_value) if v is not None]
        max_min = max(vals) if vals else None
        if max_min is not None:
            max_min += 1
    else:
        max_min = min_value + 1 if min_value is not None else None

    max_value = draw(
        st.one_of(
            st.none(),
            st.integers(
                min_value=max_min,
            ),
        )
    )

    return EventfulCounter(
        initial_value=initial_value,
        max_value=max_value,
        min_value=min_value,
        clamp_to_bounds=clamp_to_bounds,
    )


class EventfulCounterStateMachine(RuleBasedStateMachine):
    @given(eventful_counters())
    def __init__(self, counter: EventfulCounter) -> None:
        super().__init__()
        self.counter = counter

    # def teardown(self) -> None:
    #     del self.counter

    @rule(value=st.integers())
    def set(self, value):
        self.counter.set(value)

    @rule(value=st.integers())
    def inc(self, value):
        self.counter.inc(value)

    @rule(value=st.integers())
    def dec(self, value):
        self.counter.dec(value)

    @rule(value=st.integers())
    def iadd(self, value):
        self.counter += value

    @rule(value=st.integers())
    def isub(self, value):
        self.counter -= value

    @rule(value=st.integers())
    def set_max_value(self, value: int):
        if value < self.counter._counter and self.counter._clamp_to_bounds:
            with pytest.raises(ValueError):
                self.counter.max_value = value
        else:
            self.counter.max_value = value

    @rule(value=st.integers())
    def set_min_value(self, value: int):
        if value > self.counter._counter and self.counter._clamp_to_bounds:
            with pytest.raises(ValueError):
                self.counter.min_value = value
        else:
            self.counter.min_value = value

    @precondition(lambda self: self.counter._clamp_to_bounds)
    @invariant()
    def verify_value_in_bounds(self):
        if self.counter._min_value is not None:
            assert self.counter._counter >= self.counter._min_value

        if self.counter._max_value is not None:
            assert self.counter._counter <= self.counter._max_value

    @precondition(lambda self: self.counter._clamp_to_bounds)
    @invariant()
    def verify_min_bounds(self):
        if self.counter._min_value is not None:
            if self.counter._counter <= self.counter._min_value:
                assert self.counter._min_ev.is_set()
                return
        assert not self.counter._min_ev.is_set()

    @precondition(lambda self: self.counter._clamp_to_bounds)
    @invariant()
    def verify_max_bounds(self):
        if self.counter._max_value is not None:
            if self.counter._counter >= self.counter._max_value:
                assert self.counter._max_ev.is_set()
                return
        assert not self.counter._max_ev.is_set()

    @invariant()
    def test_min_value(self):
        assert self.counter.min_value == self.counter._min_value

    @invariant()
    def test_max_value(self):
        assert self.counter.max_value == self.counter._max_value

    @invariant()
    def check_counter_int(self):
        assert int(self.counter) == self.counter._counter


TestEventfulCounter = EventfulCounterStateMachine.TestCase
