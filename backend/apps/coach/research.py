"""Load researched Free Fire knowledge into the knowledge base as drafts for staff.

The research file (``data/research-*.json``) holds entries gathered from patch notes, the
wiki, esports coverage and pro guides, each with its sources, patch and any disagreement
between sources, plus suggested outlines for named places on our maps.

Rules, so staff stay in control:
- New entries arrive as DRAFTs. The coach only uses APPROVED ones.
- An entry staff wrote, edited or reviewed is never overwritten.
- An existing entry with no text ("needs writing") is filled, and becomes a draft.
- Numbers already on an entry came from our own replay files: they are kept, and a
  research number that disagrees is noted under conflicts instead.
- Place outlines arrive as SUGGESTED map areas, only on calibrated maps, and never replace
  an area staff already drew with the same name.

The functions take the model classes as arguments so the data migration can pass its
historical models.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.maps import calibration

DATA = Path(__file__).parent / "data"
LATEST = DATA / "research-ob55.json"

DRAFT, APPROVED = "DRAFT", "APPROVED"
STAFF, RESEARCH = "STAFF", "RESEARCH"
SUGGESTED = "SUGGESTED"


def read(path: Path = LATEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _same(a, b) -> bool:
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(a - b) < 1e-9
    return a == b


def _merge_data(ours: dict, theirs: dict) -> tuple[dict, list[str]]:
    """Our numbers plus the research ones we lack; disagreements as sentences."""
    merged = {**theirs, **ours}
    notes = [
        f"Our replay files measured {k} = {json.dumps(ours[k])}; the sources say"
        f" {json.dumps(theirs[k])}. Our number is kept."
        for k in theirs
        if k in ours and not _same(ours[k], theirs[k])
    ]
    return merged, notes


def _fields(item: dict) -> dict:
    return {
        "body": item["body"].strip(),
        "sources": item.get("sources", []),
        "patch": item.get("patch", "")[:20],
        "conflicts": item.get("conflicts", "").strip(),
        "weak_sources": bool(item.get("weak")),
        "weak_reason": item.get("weak_reason", "")[:300],
        "status": DRAFT,
        "origin": RESEARCH,
    }


def suggest_areas(payload: dict, Map, MapArea) -> dict[tuple[str, str], object]:
    """Suggested outlines from the research, in world coordinates of each calibrated map.

    Boxes are given as fractions of the map image (0-1, from the top left), so they fit
    whatever size of image each server has. Returns {(map slug, lower name): area}.
    """
    found: dict[tuple[str, str], object] = {}
    maps = {m.slug: m for m in Map.objects.all()}
    for s in payload.get("areas", []):
        m = maps.get(s["map"])
        if m is None:
            continue
        existing = MapArea.objects.filter(map=m, name__iexact=s["name"]).first()
        if existing is not None:
            found[(m.slug, s["name"].lower())] = existing
            continue
        if not (m.transform and m.image_width and m.image_height):
            continue  # can't place it without a calibrated image
        t = calibration.Transform.from_dict(m.transform)
        u0, v0, u1, v1 = s["box"]
        corners = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        polygon = [
            [round(c, 1) for c in t.to_world(u * m.image_width, v * m.image_height)]
            for u, v in corners
        ]
        cx, cz = calibration.polygon_centre(polygon)
        area = MapArea.objects.create(
            map=m,
            name=s["name"],
            polygon=polygon,
            centre_x=cx,
            centre_z=cz,
            status=SUGGESTED,
            note=s.get("note", ""),
        )
        found[(m.slug, s["name"].lower())] = area
    return found


def load(payload: dict, KnowledgeEntry, Map, MapArea) -> dict[str, int]:
    """Apply the research. Returns counts: created, filled, refreshed, kept, areas."""
    before = MapArea.objects.count()
    areas = suggest_areas(payload, Map, MapArea)
    maps = {m.slug: m for m in Map.objects.all()}
    counts = {"created": 0, "filled": 0, "refreshed": 0, "kept": 0}
    for item in payload["entries"]:
        if not item.get("body", "").strip() or not item.get("sources"):
            continue
        map_ = maps.get(item.get("map") or "")
        place = item.get("place")
        area = areas.get((map_.slug, place.lower())) if map_ and place else None
        entry = KnowledgeEntry.objects.filter(
            kind=item["kind"], title__iexact=item["title"], map=map_
        ).first()
        fields = _fields(item)
        if entry is None:
            KnowledgeEntry.objects.create(
                kind=item["kind"],
                title=item["title"][:120],
                map=map_,
                area=area,
                data=item.get("data", {}),
                **fields,
            )
            counts["created"] += 1
        elif not entry.body.strip() and entry.reviewed_at is None:
            # A "needs writing" entry: fill it, keeping the numbers we measured.
            data, notes = _merge_data(entry.data or {}, item.get("data", {}))
            fields["conflicts"] = "\n".join(filter(None, [fields["conflicts"], *notes]))
            for k, v in {**fields, "data": data}.items():
                setattr(entry, k, v)
            entry.area = entry.area or area
            entry.save()
            counts["filled"] += 1
        elif (
            entry.origin == RESEARCH
            and entry.status == DRAFT
            and entry.updated_by_id is None
            and entry.reviewed_at is None
        ):
            # Still an untouched draft from an earlier research run: refresh it.
            for k, v in {**fields, "data": item.get("data", {})}.items():
                setattr(entry, k, v)
            entry.area = entry.area or area
            entry.save()
            counts["refreshed"] += 1
        else:
            counts["kept"] += 1
    counts["areas"] = MapArea.objects.count() - before
    return counts
