"""Erzeugt die Brand-Assets, die HACS für eine Integration erwartet.

HACS sucht zuerst nach ``custom_components/<domain>/brand/icon.png`` und
greift nur ersatzweise auf das Repository home-assistant/brands zurück.
Anforderungen laut brands-Repository: quadratisches PNG, 256x256 beziehungsweise
512x512 für die @2x-Variante, Transparenz erwünscht, möglichst wenig Leerraum
an den Rändern.

Motiv: ein Wassertropfen mit einem Absperrbalken – Leckageschutz.

Aufruf:
    python tools/make_brand_assets.py
"""

from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw

OUT_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "syrup" / "brand"

DROP_COLOR = (30, 136, 199, 255)   # Wasserblau
BAR_COLOR = (11, 79, 118, 255)     # dunkleres Blau für den Absperrbalken

SUPERSAMPLE = 4
BASE = 512
PADDING = 4 / 256  # Anteil der Kantenlänge, der frei bleibt


def teardrop(steps: int = 720) -> list[tuple[float, float]]:
    """Tropfenkontur als Polygon in normalisierten Koordinaten.

    Grundlage ist die Kurve ``x = cos t``, ``y = sin t * sin(t/2)**2``; sie
    liefert eine Spitze bei ``t = 0``. Anschließend um 90 Grad gedreht, damit
    die Spitze oben sitzt.
    """
    points = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        u = math.cos(t)
        v = math.sin(t) * math.sin(t / 2) ** 2
        points.append((v, -u))  # Spitze nach oben
    return points


def fit(points: list[tuple[float, float]], size: int, padding: float):
    """Polygon mittig in ein Quadrat der Kantenlänge ``size`` einpassen."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    scale = (size * (1 - 2 * padding)) / span
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    return [
        (size / 2 + (x - cx) * scale, size / 2 + (y - cy) * scale) for x, y in points
    ]


def render(size: int) -> Image.Image:
    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.polygon(fit(teardrop(), canvas, PADDING), fill=DROP_COLOR)

    # Absperrbalken über der unteren Hälfte, etwas breiter als der Tropfen,
    # damit er die Bildbreite ausfüllt und kaum Leerraum bleibt.
    bar_h = canvas * 0.155
    bar_y = canvas * 0.655
    inset = canvas * PADDING
    draw.rounded_rectangle(
        [inset, bar_y, canvas - inset, bar_y + bar_h],
        radius=bar_h / 2,
        fill=BAR_COLOR,
    )

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        path = OUT_DIR / name
        render(size).save(path, "PNG", optimize=True)
        print(f"{path.relative_to(OUT_DIR.parents[2])}  {size}x{size}")


if __name__ == "__main__":
    main()
