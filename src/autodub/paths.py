"""Report/manifest path helpers — prefer paths relative to cwd / out_dir."""

from __future__ import annotations

from pathlib import Path


def reportable_path(path: Path | str, *bases: Path | str | None) -> str:
    """Return a path relative to the first matching base (cwd, out_dir, …).

    Falls back to the absolute path only when ``path`` is outside every base.
    Never invents a relative path that would escape via ``..`` chains beyond
    a single ``..`` segment — if relativize would require leaving the base
    tree, try the next base instead.
    """
    resolved = Path(path).expanduser().resolve()
    candidates: list[Path] = []
    for base in bases:
        if base is None:
            continue
        candidates.append(Path(base).expanduser().resolve())
    cwd = Path.cwd().resolve()
    if cwd not in candidates:
        candidates.append(cwd)

    for base in candidates:
        try:
            rel = resolved.relative_to(base)
        except ValueError:
            continue
        text = str(rel)
        if text == ".":
            return str(base.name) if base.name else "."
        return text
    return str(resolved)
