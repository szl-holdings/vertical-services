"""Caller-facing error text for the vertical fabric HTTP surfaces.

Only messages written for the caller leave the process: the catalog's
``UnknownVerticalError`` and the engine's ``EvaluationError``. Any other
``KeyError`` or ``ValueError`` may come from an operator-bound model or kernel
adapter, so its text is logged server-side and replaced by a fixed detail.
"""

from __future__ import annotations

import logging
from typing import Final

from .catalog import UnknownVerticalError
from .engine import EvaluationError

LOGGER: Final = logging.getLogger("frontier_fabric")
NOT_FOUND_DETAIL: Final = "vertical resource not found"
UNPROCESSABLE_DETAIL: Final = "request could not be evaluated"


def not_found_detail(exc: KeyError) -> str:
    if isinstance(exc, UnknownVerticalError):
        return str(exc)
    LOGGER.warning("vertical fabric lookup failed; public detail withheld", exc_info=exc)
    return NOT_FOUND_DETAIL


def unprocessable_detail(exc: ValueError) -> str:
    if isinstance(exc, EvaluationError):
        return str(exc)
    LOGGER.warning("vertical fabric evaluation failed; public detail withheld", exc_info=exc)
    return UNPROCESSABLE_DETAIL
