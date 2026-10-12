"""Player photos for the cards: the background cut out, and the player framed head and
shoulders like the blank picture (head near the top, shoulders filling the bottom).

The cut-out needs the optional ``photos`` extra (rembg and a 170 MB person model, fetched once
into MEDIA_ROOT/.rembg). Without it, or if it fails, the card keeps the photo as uploaded.
"""

from __future__ import annotations

import io
import logging
import os

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image

log = logging.getLogger(__name__)

MODEL = "u2net_human_seg"
# The card's photo box is 7.6 x 7.4 (width x height); the cut-out is saved at that shape.
OUT_W, OUT_H = 760, 740
HEAD_SHARE = 0.52  # the head (top of the hair to the neck) takes this much of the height
HEAD_TOP = 0.04  # space above the hair, as a share of the height

_session = None


def remove_background(img: Image.Image) -> Image.Image:
    global _session
    os.environ.setdefault("REMBG_HOME", str(settings.MEDIA_ROOT / ".rembg"))
    from rembg import new_session, remove

    if _session is None:
        _session = new_session(MODEL)
    return remove(img, session=_session)


def _runs(px, y: int, left: int, right: int) -> list[tuple[int, int]]:
    """The solid stretches of one row of the mask, as (first x, last x)."""
    runs, start = [], None
    for x in range(left, right + 1):
        on = x < right and px[x, y]
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x - 1))
            start = None
    return runs


def _head(alpha: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, float]:
    """Where the head is: (its height from the top of the hair to the neck, its centre x).

    Walks down from the top of the hair following the head's own stretch of each row, so an
    arm beside the head (a salute, pointing at the temple) is left out; a hand touching the
    head only widens a few rows, which a running median smooths away. The head widens, then
    narrows to the neck, then the shoulders spread out: the neck is the narrowest row between.
    """
    left, top, right, bottom = box
    px = alpha.load()
    rows, mids = [], []
    for y in range(top, top + int((bottom - top) * 0.6), 4):
        runs = _runs(px, y, left, right)
        if not runs:
            continue
        if not mids:
            run = max(runs, key=lambda r: r[1] - r[0])
        else:
            cx = sorted(mids)[len(mids) // 2]
            run = min(runs, key=lambda r: max(r[0] - cx, cx - r[1], 0))
        rows.append((y, run[1] - run[0]))
        mids.append((run[0] + run[1]) / 2)
    widths = [w for _, w in rows]
    smooth = [sorted(widths[max(0, i - 2) : i + 3])[len(widths[max(0, i - 2) : i + 3]) // 2]
              for i in range(len(widths))]  # fmt: skip

    peak, neck = 0, None
    for i, w in enumerate(smooth):
        if neck is None:
            peak = max(peak, w)
            if w < 0.85 * peak:
                neck = i
        elif w > 1.5 * smooth[neck]:
            break  # the shoulders
        elif w < smooth[neck]:
            neck = i
    head = mids[: neck or len(mids)]
    cx = sorted(head)[len(head) // 2] if head else (left + right) / 2
    # No neck found (a close-up): a head is about 1.3 times as tall as it is wide.
    head_h = rows[neck][0] - top if neck else int(1.3 * peak)
    return max(head_h, int((bottom - top) * 0.1)), cx


def frame(cut: Image.Image) -> Image.Image:
    """Crop a cut-out (RGBA, transparent background) to head and shoulders."""
    alpha = cut.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    box = alpha.getbbox()
    if not box:
        return cut.resize((OUT_W, OUT_H))
    top = box[1]
    head_h, cx = _head(alpha, box)

    h = head_h / HEAD_SHARE
    w = h * OUT_W / OUT_H
    y0 = top - h * HEAD_TOP
    x0 = cx - w / 2
    out = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0))
    out.paste(cut, (round(-x0), round(-y0)), cut)
    return out.resize((OUT_W, OUT_H), Image.LANCZOS)


def make_cutout(player) -> bool:
    """Build ``player.photo_cutout`` from ``player.photo``. True when it worked."""
    if not player.photo:
        return False
    try:
        with player.photo.open("rb") as f:
            img = Image.open(f)
            img.load()
        img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        cut = remove_background(img)
        box = cut.getchannel("A").point(lambda a: 255 if a > 128 else 0).getbbox()
        if not box or (box[2] - box[0]) * (box[3] - box[1]) < 0.05 * img.width * img.height:
            log.warning("No person found in the photo of player %s", player.pk)
            return False
        cut = frame(cut)
    except Exception:  # no rembg, a bad picture: the card keeps the uploaded photo
        log.exception("Photo cut-out failed for player %s", player.pk)
        return False
    buf = io.BytesIO()
    cut.save(buf, "PNG", optimize=True)
    if player.photo_cutout:
        player.photo_cutout.delete(save=False)
    player.photo_cutout.save(f"player-{player.pk}.png", ContentFile(buf.getvalue()), save=False)
    player.save(update_fields=["photo_cutout"])
    return True
