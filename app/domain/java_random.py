"""Bit-exact port of ``java.util.Random`` and ``Collections.shuffle``.

The original tarot reader was Java. Its readings came from ``new Random(seed)`` fed
into ``Collections.shuffle``, then one ``nextDouble()`` per card to decide reversal.
Python's ``random`` module uses a Mersenne Twister and would produce a completely
different permutation from the same seed, so a faithful revisioning needs this port.

Reference: java.util.Random is a specified 48-bit linear congruential generator, so
this is deterministic and portable rather than an implementation detail.
"""

from __future__ import annotations

from typing import TypeVar

_MASK_48 = (1 << 48) - 1
_MULTIPLIER = 0x5DEECE66D
_ADDEND = 0xB
_DOUBLE_DIVISOR = float(1 << 53)

T = TypeVar("T")


def _to_signed_32(value: int) -> int:
    """Reproduce Java's ``int`` overflow semantics."""
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value >= (1 << 31) else value


class JavaRandom:
    """A drop-in equivalent of ``java.util.Random`` for the operations we need."""

    __slots__ = ("_seed",)

    def __init__(self, seed: int) -> None:
        self._seed = (seed ^ _MULTIPLIER) & _MASK_48

    def _next(self, bits: int) -> int:
        self._seed = (self._seed * _MULTIPLIER + _ADDEND) & _MASK_48
        return _to_signed_32(self._seed >> (48 - bits))

    def next_int(self, bound: int | None = None) -> int:
        """Equivalent to ``nextInt()`` when ``bound`` is omitted, else ``nextInt(bound)``."""
        if bound is None:
            return self._next(32)
        if bound <= 0:
            raise ValueError("bound must be positive")
        candidate = self._next(31)
        limit = bound - 1
        if bound & limit == 0:  # bound is a power of two
            return (bound * candidate) >> 31
        return self._reject_biased(candidate, bound, limit)

    def _reject_biased(self, candidate: int, bound: int, limit: int) -> int:
        """Java's rejection loop that keeps ``nextInt`` uniform."""
        value = candidate % bound
        while _to_signed_32(candidate - value + limit) < 0:
            candidate = self._next(31)
            value = candidate % bound
        return value

    def next_double(self) -> float:
        """Equivalent to ``nextDouble()``."""
        high = self._next(26)
        low = self._next(27)
        return ((high << 27) + low) / _DOUBLE_DIVISOR


def java_shuffle(items: list[T], rng: JavaRandom) -> None:
    """Shuffle in place exactly as ``Collections.shuffle(list, rnd)`` would."""
    for size in range(len(items), 1, -1):
        target = rng.next_int(size)
        items[size - 1], items[target] = items[target], items[size - 1]
