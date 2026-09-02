"""groundcheck: is each claim in an LLM answer actually backed by its citation?

    report = groundcheck.verify(answer=answer, citations=citations, sources=sources)

See `groundcheck.core` for the full contract (record shapes, verdict
definitions) and the top-level README for the quickstart and the
exit-code contract for the CLI.
"""
from .core import (
    ALL_VERDICTS,
    VERDICT_SPAN_MISMATCH,
    VERDICT_SUPPORTED,
    VERDICT_UNCITED,
    VERDICT_UNRESOLVABLE,
    ClaimVerdict,
    GroundcheckError,
    VerificationReport,
    verify,
)

__version__ = "0.1.0"

__all__ = [
    "verify",
    "VerificationReport",
    "ClaimVerdict",
    "GroundcheckError",
    "VERDICT_SUPPORTED",
    "VERDICT_SPAN_MISMATCH",
    "VERDICT_UNRESOLVABLE",
    "VERDICT_UNCITED",
    "ALL_VERDICTS",
    "__version__",
]
