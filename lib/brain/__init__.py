"""Cognitive Core — The Operator's Brain. Re-exports Brain and test helpers."""
from lib.brain.run import Brain
from lib.brain.helpers import _reflection_is_low_signal, _compact_state_for_think

__all__ = ["Brain", "_reflection_is_low_signal", "_compact_state_for_think"]
