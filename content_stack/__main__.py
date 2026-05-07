"""Entry point for `python -m content_stack`.

Delegates to the Typer app in `cli` so the same surface is used whether the
binary `content-stack` (installed via `[project.scripts]`) or the module form
is invoked.
"""

from __future__ import annotations

from content_stack.cli import app


def main() -> None:
    """Invoke the Typer CLI app — kept as a function for testability."""
    app()


if __name__ == "__main__":
    main()
