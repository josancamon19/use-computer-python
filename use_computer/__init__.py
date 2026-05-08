from __future__ import annotations

import mmini as _mmini
from mmini import *  # noqa: F403


class Computer(_mmini.Mmini):
    """use.computer client."""


class AsyncComputer(_mmini.AsyncMmini):
    """Async use.computer client."""


__all__ = [*_mmini.__all__, "AsyncComputer", "Computer"]
