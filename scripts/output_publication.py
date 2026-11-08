"""Publication facts shared by the CSV merger and output-extension CLI."""
from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass(frozen=True)
class PublicationResult:
    output: Path
    published: bool
    warnings: tuple[str, ...] = ()
    residual_temporary: Path | None = None


def finish_publication(temporary: Path | None, output: Path,
                       published: bool) -> PublicationResult:
    """Clean only our temporary name; never reverse a successful link.

    Called in finally so a failed write/link keeps its original exception.
    Cleanup errors are separately visible, including when publication failed.
    """
    if temporary is not None:
        try:
            temporary.unlink(missing_ok=True)
        except OSError as error:
            state = "published" if published else "not published"
            message = (f"[PublicationWarning] {state}: {output}; temporary cleanup "
                       f"failed, residual path: {temporary}; {error}")
            # A disconnected diagnostic stream must not mask the write/link result.
            try:
                print(message, file=sys.stderr)
            except (OSError, ValueError):
                pass
            return PublicationResult(output, published, (message,), temporary)
    return PublicationResult(output, published)
