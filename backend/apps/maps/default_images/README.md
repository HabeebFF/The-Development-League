# Bundled map images

Every map without an image gets `<slug>.png` (or `.jpg` / `.webp`) from this folder after
`python manage.py migrate`. Run `python manage.py load_map_images --force` to replace
images already set.

`<slug>.json` (optional) holds calibration points clicked once on that exact image, so the
map is lined up with the game straight away:

```json
{
  "source": "where the image came from",
  "calibration_points": [
    {"label": "Clock Tower", "world_x": 12.5, "world_z": -40.0, "pixel_x": 510, "pixel_y": 620}
  ]
}
```

All five maps ship calibrated (fitted to logged kill positions, game
x to the right and z up).

Slugs: `bermuda`, `purgatory`, `kalahari`, `nexterra`, `solara`. After calibrating one in the
tool, `python manage.py export_map_calibration <slug>` writes its `<slug>.json`. The map art
belongs to Garena.
