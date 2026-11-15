"""Synthetic short episode for pipeline smoke without show media."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def build_synthetic_episode(out_dir: Path, *, duration_s: float = 12.0) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required")

    video = out_dir / "synthetic.mp4"
    subs = out_dir / "synthetic.en.srt"

    # tone + color bars
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_s}",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=640x360:d={duration_s}",
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(video),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:])

    # Speaker-prefixed lines for cast matching
    subs.write_text(
        """1
00:00:01,000 --> 00:00:03,500
Luffy: I'm gonna be King of the Pirates!

2
00:00:04,000 --> 00:00:06,500
Zoro: Don't get in my way.

3
00:00:07,000 --> 00:00:09,500
Nami: We need a better plan.

4
00:00:10,000 --> 00:00:12,000
Narrator: And so their journey continued.
""",
        encoding="utf-8",
    )
    return {"media": video, "subs": subs}
