"""
Gera um conjunto de dados sintético para classificação binária (100 imagens).

Classes:
  - class_0: Floresta (árvores, folhagem, tons verdes/marrons, céu variado)
  - class_1: Oceano (ondas, espuma, tons azuis, sol/lua, bolhas, peixes)

Origem: imagens criadas localmente com Python + Pillow, sem download de datasets.
Variações: hora do dia, iluminação, quantidade de elementos, posição e escala.
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

IMAGE_SIZE = 224
DEFAULT_SEED = 42
IMAGES_PER_CLASS = 50


def _clamp(value: float, low: float = 0.0, high: float = 255.0) -> int:
    return int(max(low, min(high, value)))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _rgb(r: float, g: float, b: float) -> tuple[int, int, int]:
    return (_clamp(r), _clamp(g), _clamp(b))


def _vary(color: tuple[int, int, int], delta: int, rng: random.Random) -> tuple[int, int, int]:
    return tuple(_clamp(c + rng.randint(-delta, delta)) for c in color)


def _vertical_gradient(
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> Image.Image:
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        color = (
            _clamp(_lerp(top[0], bottom[0], t)),
            _clamp(_lerp(top[1], bottom[1], t)),
            _clamp(_lerp(top[2], bottom[2], t)),
        )
        for x in range(width):
            pixels[x, y] = color
    return img


def _draw_cloud(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float, alpha: int, rng: random.Random) -> None:
    color = (245, 245, 245, alpha)
    r = int(18 * scale)
    offsets = [
        (0, 0, r),
        (int(r * 0.9), int(-r * 0.3), int(r * 0.85)),
        (int(-r * 0.85), int(-r * 0.2), int(r * 0.75)),
        (int(r * 1.5), int(r * 0.1), int(r * 0.7)),
    ]
    for ox, oy, radius in offsets:
        draw.ellipse(
            (cx + ox - radius, cy + oy - radius, cx + ox + radius, cy + oy + radius),
            fill=color,
        )


def _draw_tree(
    draw: ImageDraw.ImageDraw,
    base_x: int,
    ground_y: int,
    scale: float,
    lighting: float,
    rng: random.Random,
) -> None:
    trunk_w = int(10 * scale)
    trunk_h = int(42 * scale)
    trunk_color = _rgb(72 * lighting, 48 * lighting, 32 * lighting)
    trunk_color = _vary(trunk_color, 12, rng)

    trunk_left = base_x - trunk_w // 2
    trunk_top = ground_y - trunk_h
    draw.rectangle(
        (trunk_left, trunk_top, trunk_left + trunk_w, ground_y),
        fill=trunk_color,
    )

    foliage_colors = [
        _rgb(34 * lighting, 110 * lighting, 48 * lighting),
        _rgb(28 * lighting, 95 * lighting, 42 * lighting),
        _rgb(46 * lighting, 128 * lighting, 58 * lighting),
    ]
    foliage_center_y = trunk_top - int(8 * scale)
    foliage_r = int(26 * scale)

    for i in range(3):
        offset_x = rng.randint(-int(8 * scale), int(8 * scale))
        offset_y = rng.randint(-int(6 * scale), int(4 * scale))
        radius = foliage_r + rng.randint(-int(4 * scale), int(6 * scale))
        color = _vary(foliage_colors[i % len(foliage_colors)], 18, rng)
        draw.ellipse(
            (
                base_x + offset_x - radius,
                foliage_center_y + offset_y - radius,
                base_x + offset_x + radius,
                foliage_center_y + offset_y + radius,
            ),
            fill=color,
        )

    if rng.random() < 0.35:
        leaf_r = int(3 * scale)
        for _ in range(rng.randint(4, 10)):
            lx = base_x + rng.randint(-int(30 * scale), int(30 * scale))
            ly = foliage_center_y + rng.randint(-int(20 * scale), int(15 * scale))
            leaf_color = _vary(_rgb(55 * lighting, 145 * lighting, 65 * lighting), 20, rng)
            draw.ellipse((lx - leaf_r, ly - leaf_r, lx + leaf_r, ly + leaf_r), fill=leaf_color)


def _draw_forest_scene(rng: random.Random, size: int) -> Image.Image:
    mood = rng.choice(["manha", "tarde", "nublado", "entardecer"])
    lighting = rng.uniform(0.75, 1.15)

    sky_presets = {
        "manha": ((120, 185, 235), (190, 225, 250)),
        "tarde": ((95, 165, 220), (170, 210, 245)),
        "nublado": ((145, 160, 175), (185, 195, 205)),
        "entardecer": ((255, 170, 120), (120, 90, 150)),
    }
    sky_top, sky_bottom = sky_presets[mood]
    sky_top = _vary(sky_top, 15, rng)
    sky_bottom = _vary(sky_bottom, 15, rng)

    ground_y = rng.randint(int(size * 0.62), int(size * 0.78))
    ground_color = _vary(_rgb(55 * lighting, 95 * lighting, 48 * lighting), 18, rng)
    horizon_color = _vary(_rgb(75 * lighting, 120 * lighting, 62 * lighting), 18, rng)

    img = _vertical_gradient(size, size, sky_top, horizon_color)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, ground_y, size, size), fill=ground_color)

    if mood != "nublado" and rng.random() < 0.7:
        sun_x = rng.randint(int(size * 0.15), int(size * 0.85))
        sun_y = rng.randint(int(size * 0.08), int(size * 0.25))
        sun_r = rng.randint(12, 22)
        sun_color = (255, 240, 170, 220) if mood != "entardecer" else (255, 190, 110, 230)
        draw.ellipse((sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r), fill=sun_color)

    cloud_count = rng.randint(1, 4) if mood in {"manha", "tarde", "nublado"} else rng.randint(0, 2)
    for _ in range(cloud_count):
        cx = rng.randint(0, size)
        cy = rng.randint(int(size * 0.05), int(size * 0.35))
        scale = rng.uniform(0.7, 1.4)
        alpha = rng.randint(90, 170) if mood == "nublado" else rng.randint(60, 130)
        _draw_cloud(draw, cx, cy, scale, alpha, rng)

    tree_count = rng.randint(4, 8)
    tree_slots = sorted(rng.sample(range(size - 20), tree_count))
    for slot in tree_slots:
        scale = rng.uniform(0.65, 1.35)
        depth = rng.random()
        base_x = slot + rng.randint(-8, 8)
        adjusted_ground = ground_y + rng.randint(-4, 6)
        local_light = lighting * _lerp(0.85, 1.05, depth)
        _draw_tree(draw, base_x, adjusted_ground, scale, local_light, rng)

    if rng.random() < 0.5:
        bush_count = rng.randint(2, 5)
        for _ in range(bush_count):
            bx = rng.randint(10, size - 10)
            by = ground_y + rng.randint(-6, 4)
            br = rng.randint(10, 18)
            bush_color = _vary(_rgb(40 * lighting, 105 * lighting, 50 * lighting), 22, rng)
            draw.ellipse((bx - br, by - br, bx + br, by - br // 2), fill=bush_color)

    return img.convert("RGB")


def _draw_wave_layer(
    draw: ImageDraw.ImageDraw,
    width: int,
    base_y: int,
    amplitude: int,
    wavelength: float,
    color: tuple[int, int, int],
    phase: float,
) -> None:
    points_top = []
    for x in range(width + 1):
        y = base_y + int(amplitude * math.sin((x / wavelength) * 2 * math.pi + phase))
        points_top.append((x, y))

    polygon = points_top + [(width, base_y + amplitude + 8), (0, base_y + amplitude + 8)]
    draw.polygon(polygon, fill=color)


def _draw_fish(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, color: tuple[int, int, int]) -> None:
    body_w = int(16 * scale)
    body_h = int(8 * scale)
    draw.ellipse((x, y, x + body_w, y + body_h), fill=color)
    tail = [
        (x + body_w, y + body_h // 2),
        (x + body_w + int(8 * scale), y - int(4 * scale)),
        (x + body_w + int(8 * scale), y + body_h + int(4 * scale)),
    ]
    draw.polygon(tail, fill=color)


def _draw_ocean_scene(rng: random.Random, size: int) -> Image.Image:
    mood = rng.choice(["dia_claro", "fim_de_tarde", "tempestade", "noite_lunar"])
    lighting = rng.uniform(0.7, 1.1)

    sky_presets = {
        "dia_claro": ((70, 150, 225), (130, 195, 245)),
        "fim_de_tarde": ((255, 175, 120), (80, 120, 190)),
        "tempestade": ((55, 70, 95), (95, 110, 130)),
        "noite_lunar": ((15, 25, 55), (35, 50, 85)),
    }
    sky_top, sky_bottom = sky_presets[mood]
    sky_top = _vary(sky_top, 12, rng)
    sky_bottom = _vary(sky_bottom, 12, rng)

    horizon_y = rng.randint(int(size * 0.28), int(size * 0.42))
    img = _vertical_gradient(size, size, sky_top, sky_bottom)
    draw = ImageDraw.Draw(img, "RGBA")

    if mood == "dia_claro" and rng.random() < 0.75:
        sun_x = rng.randint(int(size * 0.65), int(size * 0.9))
        sun_y = rng.randint(int(size * 0.08), int(size * 0.2))
        sun_r = rng.randint(11, 18)
        draw.ellipse(
            (sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r),
            fill=(255, 245, 190, 230),
        )

    if mood == "noite_lunar":
        moon_x = rng.randint(int(size * 0.1), int(size * 0.85))
        moon_y = rng.randint(int(size * 0.08), int(size * 0.22))
        moon_r = rng.randint(10, 16)
        draw.ellipse(
            (moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r),
            fill=(235, 235, 245, 240),
        )
        for _ in range(rng.randint(8, 18)):
            sx = rng.randint(0, size)
            sy = rng.randint(0, horizon_y)
            sr = rng.randint(1, 2)
            draw.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 255, 255, 220))

    if mood in {"dia_claro", "fim_de_tarde"} and rng.random() < 0.6:
        cloud_count = rng.randint(1, 3)
        for _ in range(cloud_count):
            _draw_cloud(
                draw,
                rng.randint(0, size),
                rng.randint(int(size * 0.05), int(size * 0.25)),
                rng.uniform(0.6, 1.1),
                rng.randint(50, 120),
                rng,
            )

    deep = _vary(_rgb(8 * lighting, 70 * lighting, 135 * lighting), 15, rng)
    mid = _vary(_rgb(20 * lighting, 105 * lighting, 175 * lighting), 15, rng)
    shallow = _vary(_rgb(45 * lighting, 150 * lighting, 205 * lighting), 15, rng)

    base_wave = horizon_y + rng.randint(8, 20)
    _draw_wave_layer(draw, size, base_wave, rng.randint(6, 12), rng.uniform(28, 48), deep, rng.uniform(0, math.pi))
    _draw_wave_layer(
        draw,
        size,
        base_wave + rng.randint(14, 24),
        rng.randint(5, 10),
        rng.uniform(24, 40),
        mid,
        rng.uniform(0, math.pi),
    )
    _draw_wave_layer(
        draw,
        size,
        base_wave + rng.randint(28, 42),
        rng.randint(4, 8),
        rng.uniform(20, 36),
        shallow,
        rng.uniform(0, math.pi),
    )

    foam_y = base_wave + rng.randint(10, 28)
    for x in range(0, size, rng.randint(6, 12)):
        if rng.random() < 0.55:
            fy = foam_y + rng.randint(-4, 6)
            fw = rng.randint(4, 10)
            fh = rng.randint(2, 5)
            draw.ellipse((x, fy, x + fw, fy + fh), fill=(235, 245, 255, 170))

    fish_count = rng.randint(0, 4)
    for _ in range(fish_count):
        fx = rng.randint(10, size - 30)
        fy = rng.randint(horizon_y + 20, size - 20)
        fish_color = _vary(_rgb(230 * lighting, 120 * lighting, 70 * lighting), 25, rng)
        _draw_fish(draw, fx, fy, rng.uniform(0.7, 1.2), fish_color)

    bubble_count = rng.randint(6, 18)
    for _ in range(bubble_count):
        bx = rng.randint(8, size - 8)
        by = rng.randint(horizon_y + 10, size - 8)
        br = rng.randint(2, 6)
        draw.ellipse((bx - br, by - br, bx + br, by + br), outline=(220, 240, 255, 140))

    if rng.random() < 0.35:
        sand_height = rng.randint(12, 28)
        sand_color = _vary(_rgb(220 * lighting, 200 * lighting, 150 * lighting), 18, rng)
        draw.rectangle((0, size - sand_height, size, size), fill=sand_color)

    return img.convert("RGB")


def generate_dataset(
    output_dir: Path,
    images_per_class: int = IMAGES_PER_CLASS,
    image_size: int = IMAGE_SIZE,
    seed: int = DEFAULT_SEED,
) -> None:
    rng = random.Random(seed)
    class_dirs = {
        "class_0": output_dir / "class_0",
        "class_1": output_dir / "class_1",
    }

    for path in class_dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    generators = {
        "class_0": _draw_forest_scene,
        "class_1": _draw_ocean_scene,
    }

    for class_name, generator in generators.items():
        target_dir = class_dirs[class_name]
        for index in range(images_per_class):
            scene = generator(rng, image_size)
            filename = f"{class_name}_{index:03d}.png"
            scene.save(target_dir / filename, format="PNG")

    print(f"Dataset gerado em: {output_dir.resolve()}")
    print(f"  class_0 (floresta): {images_per_class} imagens")
    print(f"  class_1 (oceano):   {images_per_class} imagens")
    print(f"  resolucao: {image_size}x{image_size}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera dataset sintetico floresta vs oceano.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Diretorio raiz do dataset (default: data)",
    )
    parser.add_argument(
        "--images-per-class",
        type=int,
        default=IMAGES_PER_CLASS,
        help="Quantidade de imagens por classe (default: 50)",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=IMAGE_SIZE,
        help="Largura e altura das imagens (default: 224)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Seed para reproducibilidade (default: 42)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_dataset(
        output_dir=args.output_dir,
        images_per_class=args.images_per_class,
        image_size=args.image_size,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
