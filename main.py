#!/usr/bin/env python3
"""Courier and checker for the news-image-20261121 entry image.

Structure of this round-2 implementation:

1. ``PinnedImage`` bundles the expected identity of ``entry.png``
   and knows how to compare a measured file against that identity.
2. ``measure_file`` walks a file in blocks, validating the PNG
   header on the first block and hashing everything it reads.
3. ``deliver`` ties the two together: measure the source, copy it
   into the destination directory, measure the copy, report.

The destination comes from the ``MAKEFUN_OUTPUT_DIR`` environment
variable and defaults to ``/output``. The module depends only on
the standard library, touches no network and reads no clock, so
its output is fully deterministic.
"""

import hashlib
import os
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

PINNED_SIZE = 260701
PINNED_SHA256 = "6323da5b9b1a90ecbc5b31eb4d4c61f9fe5de81c692972b0c183e0cfbc170b73"
PINNED_WIDTH = 1024
PINNED_HEIGHT = 1024

_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
_BLOCK_SIZE = 32768


@dataclass(frozen=True)
class Measured:
    size: int
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class PinnedImage:
    size: int
    sha256: str
    width: int
    height: int

    def check(self, measured, label):
        """Raise ValueError naming every field that disagrees."""
        diffs = []
        if measured.size != self.size:
            diffs.append("size %r != pinned %r" % (measured.size, self.size))
        if measured.sha256 != self.sha256:
            diffs.append("sha256 %r != pinned %r" % (measured.sha256, self.sha256))
        if (measured.width, measured.height) != (self.width, self.height):
            diffs.append(
                "dimensions %rx%r != pinned %rx%r"
                % (measured.width, measured.height, self.width, self.height)
            )
        if diffs:
            raise ValueError("%s does not match the pin: %s" % (label, ", ".join(diffs)))


PINNED = PinnedImage(
    size=PINNED_SIZE,
    sha256=PINNED_SHA256,
    width=PINNED_WIDTH,
    height=PINNED_HEIGHT,
)


def _blocks(handle):
    while True:
        data = handle.read(_BLOCK_SIZE)
        if not data:
            return
        yield data


def measure_file(path):
    """Return a ``Measured`` for *path*, validating its PNG header."""
    digest = hashlib.sha256()
    total = 0
    dims = None
    with Path(path).open("rb") as handle:
        for block in _blocks(handle):
            if dims is None:
                if len(block) < 24 or block[:8] != _SIGNATURE:
                    raise ValueError("%s: invalid PNG signature" % path)
                if block[12:16] != b"IHDR":
                    raise ValueError("%s: IHDR chunk not found first" % path)
                dims = struct.unpack(">II", block[16:24])
            digest.update(block)
            total += len(block)
    if dims is None:
        raise ValueError("%s: no data read" % path)
    return Measured(size=total, sha256=digest.hexdigest(), width=dims[0], height=dims[1])


def verified(path, label):
    """Measure *path*, check it against ``PINNED`` and return it."""
    result = measure_file(path)
    PINNED.check(result, label)
    return result


def deliver():
    source_dir = Path(__file__).resolve().parent
    source = source_dir / "entry.png"
    verified(source, "source entry.png")

    out_dir = Path(os.getenv("MAKEFUN_OUTPUT_DIR") or "/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    placed = out_dir / source.name
    with source.open("rb") as src, placed.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=_BLOCK_SIZE)

    final = verified(placed, "placed entry.png")
    print(
        "entry.png: %dx%d, %d bytes, sha256 %s"
        % (final.width, final.height, final.size, final.sha256)
    )
    print("wrote %s" % placed)
    return 0


if __name__ == "__main__":
    raise SystemExit(deliver())
