import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

# Canvas dimensions — high-resolution output
WIDTH = 1920
HEIGHT = 1080
HORIZON_Y = int(HEIGHT * 0.44)   # horizon line: 44 % from top


# ── Colour helpers ────────────────────────────────────────────────────────────

def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _sky_palette(sky_tone, time_of_day, haze):
    """Return (zenith_rgb, horizon_rgb) for the sky gradient."""
    if time_of_day == "night":
        return (4, 4, 25), (18, 18, 55)
    if time_of_day == "twilight":
        return (45, 28, 85), (255, 110, 50)
    # daytime
    tone_map = {
        "icy_blue":      ((75, 138, 196),  (178, 212, 238)),
        "pale_blue":     ((100, 158, 210), (192, 218, 238)),
        "daylight_blue": ((28,  98, 176),  (118, 178, 222)),
        "warm_azure":    ((20,  88, 200),  (138, 192, 232)),
        "hazy_golden":   ((178, 158,  98), (232, 212, 162)),
    }
    zenith, horizon = tone_map.get(sky_tone, ((28, 98, 176), (118, 178, 222)))
    # Humidity haze blends horizon toward milky-white
    horizon = _lerp(horizon, (252, 250, 240), haze * 0.45)
    return zenith, horizon


def _ground_base(season, scene_type):
    if scene_type == "urban_cityscape":
        return (58, 58, 63)
    return {
        "winter":  (215, 222, 232),
        "spring":  (88, 158, 78),
        "summer":  (52, 126, 46),
        "autumn":  (138, 98, 48),
        "unknown": (68, 118, 58),
    }.get(season, (68, 118, 58))


def _tree_color(season, night):
    if night:
        return {"winter": (90, 90, 100), "spring": (38, 78, 28),
                "summer": (18, 68, 18),  "autumn": (78, 52, 18),
                "unknown": (28, 68, 22)}.get(season, (28, 68, 22))
    return {"winter": (155, 162, 168), "spring": (78, 158, 68),
            "summer": (38, 118, 28),   "autumn": (168, 98, 28),
            "unknown": (58, 128, 48)}.get(season, (58, 128, 48))


# ── Noise helpers ─────────────────────────────────────────────────────────────

def _noise(h, w, sigma, rng):
    raw = rng.random((h, w)).astype(np.float32)
    return gaussian_filter(raw, sigma=sigma)


def _norm(a):
    lo, hi = a.min(), a.max()
    return np.zeros_like(a) if hi == lo else (a - lo) / (hi - lo)


# ── Sky layer ─────────────────────────────────────────────────────────────────

def _draw_sky(canvas, sky_atm, time_of_day, rng):
    sky_tone = sky_atm.get("sky_color_tone", "daylight_blue")
    haze = float(sky_atm.get("haze_factor", 0.2))
    zenith, horizon = _sky_palette(sky_tone, time_of_day, haze)
    for y in range(HORIZON_Y):
        t = y / max(HORIZON_Y - 1, 1)
        canvas[y, :] = _lerp(zenith, horizon, t ** 0.7)


# ── Cloud layer ───────────────────────────────────────────────────────────────

def _draw_clouds(canvas, sky_atm, time_of_day, rng):
    cloud_cov = float(sky_atm.get("cloud_coverage", 0.3))
    atm = sky_atm.get("atmospheric_condition", "clear")
    if cloud_cov <= 0.02 and atm not in ("foggy",):
        return

    n1 = _norm(_noise(HORIZON_Y, WIDTH, sigma=55, rng=rng))
    n2 = _norm(_noise(HORIZON_Y, WIDTH, sigma=18, rng=rng))
    combined = _norm(n1 * 0.65 + n2 * 0.35)

    if atm == "foggy":
        threshold, alpha, cloud_rgb = 0.0, 0.72, (198, 198, 202)
    elif atm in ("overcast", "stormy"):
        threshold = max(0.0, 0.95 - cloud_cov)
        alpha = 0.82
        cloud_rgb = (88, 88, 98) if time_of_day == "night" else (128, 128, 138)
    else:
        threshold = max(0.0, 1.0 - cloud_cov * 1.1)
        alpha = 0.58
        cloud_rgb = (58, 60, 78) if time_of_day == "night" else (242, 242, 248)

    mask = np.clip((combined - threshold) / max(1 - threshold, 0.01), 0.0, 1.0) * alpha
    for c, cv in enumerate(cloud_rgb):
        layer = canvas[:HORIZON_Y, :, c].astype(np.float32)
        canvas[:HORIZON_Y, :, c] = np.clip(
            layer * (1 - mask) + cv * mask, 0, 255
        ).astype(np.uint8)


# ── Celestial layer ───────────────────────────────────────────────────────────

def _draw_celestial(canvas, celestial, sky_atm, time_of_day, rng):
    img = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)
    cloud_cov = float(sky_atm.get("cloud_coverage", 0.3))

    if time_of_day == "night":
        # Star field
        star_density = float(celestial.get("star_field_density", 0.4))
        n_stars = int(star_density * 700 + 60)
        for _ in range(n_stars):
            sx = int(rng.integers(0, WIDTH))
            sy = int(rng.integers(0, int(HORIZON_Y * 0.92)))
            br = int(rng.integers(140, 256))
            r = 1 if rng.random() < 0.82 else 2
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(br, br, br))

        # Moon
        moon = celestial.get("moon", {})
        if moon.get("is_visible", False) and cloud_cov < 0.85:
            moon_br = float(moon.get("brightness", 0.5))
            moon_alt = float(moon.get("altitude_deg", 45.0))
            moon_az = float(moon.get("azimuth_deg", 200.0))
            mx = int((moon_az % 360) / 360.0 * WIDTH)
            my = int(HORIZON_Y * (1.0 - moon_alt / 90.0) * 0.88)
            mr = max(12, int(18 + moon_br * 14))
            mc = (int(210 + moon_br * 40), int(210 + moon_br * 38), int(175 + moon_br * 22))
            # Glow rings
            for gr in range(mr + 28, mr, -6):
                frac = (gr - mr) / 28.0
                gc = _lerp(mc, (18, 18, 50), frac * 0.9)
                draw.ellipse([mx - gr, my - gr, mx + gr, my + gr], fill=gc)
            draw.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=mc)

        # Bright planets
        for planet in celestial.get("visible_planets", []):
            pbr = float(planet.get("brightness", 0.4))
            if pbr < 0.3:
                continue
            p_alt = float(planet.get("altitude_deg") or 30.0)
            p_az = float(planet.get("azimuth_deg") or 180.0)
            px = int((p_az % 360) / 360.0 * WIDTH)
            py = int(HORIZON_Y * (1.0 - p_alt / 90.0) * 0.88)
            pr = max(1, int(pbr * 5))
            pc = int(175 + pbr * 75)
            draw.ellipse([px - pr, py - pr, px + pr, py + pr],
                         fill=(pc, pc, int(pc * 0.88)))

    elif time_of_day == "twilight":
        # Setting / rising sun near horizon
        sun_x = int(WIDTH * 0.62)
        sun_y = HORIZON_Y - 18
        for gr in range(130, 18, -12):
            frac = (gr - 18) / 112.0
            gc = _lerp((255, 80, 10), (255, 220, 80), 1 - frac)
            draw.ellipse([sun_x - gr, sun_y - gr, sun_x + gr, sun_y + gr], fill=gc)
        draw.ellipse([sun_x - 22, sun_y - 22, sun_x + 22, sun_y + 22],
                     fill=(255, 235, 90))

    else:  # daytime
        if cloud_cov < 0.82:
            sun_x = int(WIDTH * 0.72)
            sun_y = int(HORIZON_Y * 0.22)
            for gr in range(90, 12, -12):
                frac = (gr - 12) / 78.0
                gc = _lerp((255, 248, 200), (255, 195, 60), frac * 0.6)
                draw.ellipse([sun_x - gr, sun_y - gr, sun_x + gr, sun_y + gr], fill=gc)
            draw.ellipse([sun_x - 18, sun_y - 18, sun_x + 18, sun_y + 18],
                         fill=(255, 252, 210))

    canvas[:] = np.array(img)


# ── Terrain layer ─────────────────────────────────────────────────────────────

def _draw_terrain(canvas, scene_el, scene_act, sky_atm, rng):
    scene_type = scene_el.get("scene_type", "rural_landscape")
    season = scene_el.get("season", "unknown")
    time_of_day = scene_el.get("time_of_day", "daytime")
    night = time_of_day == "night"

    ground_rgb = _ground_base(season, scene_type)
    canvas[HORIZON_Y:, :] = ground_rgb

    if scene_type == "urban_cityscape":
        _draw_urban(canvas, sky_atm, time_of_day, season, rng)
    elif scene_type == "rural_landscape":
        _draw_rural(canvas, scene_el, scene_act, time_of_day, season, night, rng)
    else:
        _draw_suburban(canvas, scene_el, time_of_day, season, night, rng)


def _draw_rural(canvas, scene_el, scene_act, time_of_day, season, night, rng):
    h, w = canvas.shape[:2]
    img = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)

    # ── Background mountain / hill silhouette ──
    mtn_noise = _norm(_noise(1, w, sigma=110, rng=rng))[0]
    mtn_h = int(HEIGHT * 0.13)
    mtn_colors = {
        "winter": (138, 148, 168), "spring": (78, 128, 68),
        "summer": (48, 108, 40),   "autumn": (118, 88, 42),
        "unknown": (68, 110, 55),
    }
    mc = mtn_colors.get(season, (68, 110, 55))
    if night:
        mc = tuple(max(0, c - 55) for c in mc)
    for x in range(w):
        top = int(HORIZON_Y - mtn_noise[x] * mtn_h)
        draw.line([(x, top), (x, HORIZON_Y + 2)], fill=mc)

    # ── Midground rolling hills ──
    hill_noise = _norm(_noise(1, w, sigma=75, rng=rng))[0]
    hill_h = int(HEIGHT * 0.10)
    hc = _lerp(mc, (0, 0, 0), 0.12)
    for x in range(w):
        top = int(HORIZON_Y + 5 + hill_noise[x] * hill_h)
        draw.line([(x, top), (x, HORIZON_Y + hill_h + 20)], fill=hc)

    # ── River / water body ──
    river_noise = _norm(_noise(1, h - HORIZON_Y, sigma=28, rng=rng))[0]
    river_base_x = int(w * 0.28)
    river_color = (72, 122, 172) if not night else (28, 42, 72)
    for y in range(HORIZON_Y + hill_h + 10, h - 10):
        idx = min(y - HORIZON_Y - hill_h - 10, len(river_noise) - 1)
        rx = river_base_x + int(river_noise[idx] * 90 - 45)
        rw = 22 + int(river_noise[idx] * 18)
        draw.line([(max(0, rx), y), (min(w - 1, rx + rw), y)], fill=river_color)

    # ── Trees along hills ──
    tc = _tree_color(season, night)
    trunk = (88, 58, 28)
    n_trees = int(22 + rng.integers(0, 6))
    xs = sorted(rng.integers(0, w, size=n_trees).tolist())
    for tx in xs:
        ty_base = HORIZON_Y + int(hill_h * 0.4) + int(rng.random() * hill_h * 0.5)
        th = int(38 + rng.random() * 58)
        tw = int(th * 0.55)
        # Trunk
        draw.rectangle([tx - 3, ty_base, tx + 3, ty_base + 14], fill=trunk)
        # Crown
        draw.ellipse([tx - tw // 2, ty_base - th, tx + tw // 2, ty_base + 5], fill=tc)

    # ── Dirt path ──
    path_color = (148, 122, 88) if not night else (68, 52, 35)
    path_x = int(w * 0.55)
    for y in range(HORIZON_Y + hill_h + 30, h):
        pw = int(12 + (y - HORIZON_Y - hill_h - 30) * 0.08)
        px0 = max(0, path_x - pw)
        px1 = min(w - 1, path_x + pw)
        draw.line([(px0, y), (px1, y)], fill=path_color)

    canvas[:] = np.array(img)


def _draw_urban(canvas, sky_atm, time_of_day, season, rng):
    h, w = canvas.shape[:2]
    img = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)
    night = time_of_day == "night"

    # ── Road surface ──
    road_color = (52, 52, 57) if night else (72, 72, 78)
    draw.rectangle([0, HORIZON_Y, w, h], fill=road_color)
    # Lane markings
    lane_c = (200, 195, 85)
    for lx in range(0, w, 80):
        draw.rectangle([lx, HORIZON_Y + 38, lx + 42, HORIZON_Y + 42], fill=lane_c)

    # ── Kerb / pavement strip ──
    kerb_c = (115, 115, 120)
    draw.rectangle([0, HORIZON_Y, w, HORIZON_Y + 12], fill=kerb_c)

    # ── Background skyscrapers ──
    bld_base = (42, 48, 58) if night else (152, 158, 170)
    for i in range(16):
        bx = int((i / 16.0) * w + rng.random() * (w // 16) - 10)
        bw = int(48 + rng.random() * 82)
        bh = int(115 + rng.random() * 295)
        by = HORIZON_Y - bh
        shade = int(rng.random() * 28 - 14)
        bc = tuple(max(0, min(255, c + shade)) for c in bld_base)
        draw.rectangle([bx, by, bx + bw, HORIZON_Y], fill=bc)
        # Windows grid
        win_lit = (255, 238, 140) if night else (195, 218, 238)
        win_dark = (28, 32, 40) if night else (155, 172, 192)
        for wy in range(by + 8, HORIZON_Y - 6, 16):
            for wx_off in range(6, bw - 6, 11):
                lit = (rng.random() < 0.68) if night else (rng.random() < 0.38)
                draw.rectangle([bx + wx_off, wy, bx + wx_off + 6, wy + 9],
                               fill=win_lit if lit else win_dark)
        # Antenna / spire
        if rng.random() < 0.35:
            draw.line([(bx + bw // 2, by), (bx + bw // 2, by - int(rng.random() * 40 + 10))],
                      fill=(90, 92, 98), width=2)

    # ── Foreground closer buildings ──
    fg_base = (62, 68, 78) if night else (135, 140, 152)
    for i in range(5):
        bx = int((i / 5.0) * w + rng.random() * 30)
        bw = int(95 + rng.random() * 65)
        bh = int(55 + rng.random() * 110)
        by = HORIZON_Y - bh
        draw.rectangle([bx, by, bx + bw, HORIZON_Y], fill=fg_base)

    # ── Street lights ──
    light_c = (255, 238, 148) if night else (178, 175, 165)
    for lx in range(90, w, 200):
        draw.line([(lx, HORIZON_Y - 62), (lx, HORIZON_Y)],
                  fill=(118, 118, 122), width=3)
        draw.ellipse([lx - 9, HORIZON_Y - 68, lx + 9, HORIZON_Y - 58], fill=light_c)
        if night:
            draw.ellipse([lx - 22, HORIZON_Y - 80, lx + 22, HORIZON_Y - 46],
                         fill=(255, 238, 100))

    # ── Street trees ──
    tc = _tree_color(season, night)
    for tx in range(55, w - 30, 140):
        ty = HORIZON_Y - 5
        draw.rectangle([tx - 3, ty, tx + 3, ty + 18], fill=(88, 58, 28))
        draw.ellipse([tx - 18, ty - 35, tx + 18, ty + 5], fill=tc)

    canvas[:] = np.array(img)


def _draw_suburban(canvas, scene_el, time_of_day, season, night, rng):
    h, w = canvas.shape[:2]
    img = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)

    # ── Grass ──
    grass_c = _ground_base(season, "rural_landscape")
    if night:
        grass_c = tuple(max(0, c - 45) for c in grass_c)
    draw.rectangle([0, HORIZON_Y, w, h], fill=grass_c)

    # ── Road ──
    road_y = HORIZON_Y + int((h - HORIZON_Y) * 0.38)
    road_h = int((h - HORIZON_Y) * 0.22)
    draw.rectangle([0, road_y, w, road_y + road_h],
                   fill=(72, 72, 78) if night else (88, 88, 94))
    lane_y = road_y + road_h // 2
    for lx in range(0, w, 68):
        draw.rectangle([lx, lane_y - 2, lx + 35, lane_y + 2], fill=(210, 198, 78))

    # ── Houses ──
    wall_c = (175, 150, 125) if not night else (55, 45, 40)
    roof_c = (135, 65, 48) if not night else (48, 28, 22)
    door_c = (90, 58, 38)
    for i in range(8):
        hx = int((i / 8.0) * w) + int(rng.random() * 30)
        hw = int(78 + rng.random() * 42)
        hh = int(58 + rng.random() * 42)
        hy = road_y - hh - int(rng.random() * 18) - 5
        draw.rectangle([hx, hy, hx + hw, road_y - 5], fill=wall_c)
        # Roof triangle
        draw.polygon([hx - 8, hy, hx + hw // 2, hy - 28, hx + hw + 8, hy],
                     fill=roof_c)
        # Windows
        win_c = (255, 228, 105) if night else (198, 215, 238)
        draw.rectangle([hx + hw // 5, hy + 14, hx + hw // 5 + 18, hy + 30],
                       fill=win_c)
        draw.rectangle([hx + hw * 3 // 5, hy + 14, hx + hw * 3 // 5 + 18, hy + 30],
                       fill=win_c)
        # Door
        draw.rectangle([hx + hw // 2 - 7, hy + hh - 24, hx + hw // 2 + 7, hy + hh],
                       fill=door_c)

    # ── Background low hills ──
    hill_n = _norm(_noise(1, w, sigma=100, rng=rng))[0]
    hill_hgt = int(HEIGHT * 0.08)
    hill_c = _ground_base(season, "rural_landscape")
    if night:
        hill_c = tuple(max(0, c - 50) for c in hill_c)
    hill_c = _lerp(hill_c, (0, 0, 0), 0.25)
    for x in range(w):
        top = int(HORIZON_Y - hill_n[x] * hill_hgt * 0.6)
        draw.line([(x, top), (x, HORIZON_Y)], fill=hill_c)

    # ── Street trees / hedges ──
    tc = _tree_color(season, night)
    for tx in range(50, w - 30, 118):
        ty = road_y - 8
        draw.rectangle([tx - 3, ty, tx + 3, ty + 16], fill=(88, 58, 28))
        draw.ellipse([tx - 16, ty - 32, tx + 16, ty + 4], fill=tc)

    # ── Lamp posts ──
    lamp_c = (255, 235, 142) if night else (172, 170, 160)
    for lx in range(80, w, 175):
        post_y = road_y
        draw.line([(lx, post_y - 55), (lx, post_y)],
                  fill=(122, 122, 126), width=3)
        draw.ellipse([lx - 8, post_y - 60, lx + 8, post_y - 52], fill=lamp_c)
        if night:
            draw.ellipse([lx - 20, post_y - 72, lx + 20, post_y - 40],
                         fill=(255, 235, 95))

    canvas[:] = np.array(img)


# ── Weather effects ───────────────────────────────────────────────────────────

def _draw_weather_effects(canvas, sky_atm, rng):
    precip = sky_atm.get("precipitation", "none")
    atm = sky_atm.get("atmospheric_condition", "clear")
    h, w = canvas.shape[:2]
    img = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)

    if precip in ("rain", "heavy_rain", "heavy_rain_with_thunder", "light_rain"):
        intensity = {"light_rain": 0.28, "rain": 0.60, "heavy_rain": 0.88,
                     "heavy_rain_with_thunder": 1.0}.get(precip, 0.5)
        n_drops = int(intensity * 1400)
        for _ in range(n_drops):
            rx = int(rng.integers(0, w))
            ry = int(rng.integers(0, h))
            dl = int(7 + rng.random() * 12)
            ac = int(100 + rng.random() * 80)
            draw.line([(rx, ry), (rx + 2, ry + dl)], fill=(ac, ac, ac + 18), width=1)

    elif precip in ("snow", "snow_showers") or atm == "snowy":
        n_flakes = 900
        for _ in range(n_flakes):
            fx = int(rng.integers(0, w))
            fy = int(rng.integers(0, h))
            r = 1 if rng.random() < 0.78 else 2
            draw.ellipse([fx - r, fy - r, fx + r, fy + r], fill=(238, 244, 255))

    canvas[:] = np.array(img)


# ── Post-processing ───────────────────────────────────────────────────────────

def _post_process(canvas, sky_atm, time_of_day):
    haze = float(sky_atm.get("haze_factor", 0.2))
    h, w = canvas.shape[:2]

    # Soft horizon blend (5-pixel gaussian on a narrow band)
    band = slice(HORIZON_Y - 6, HORIZON_Y + 6)
    canvas[band] = gaussian_filter(canvas[band].astype(np.float32),
                                   sigma=[1.5, 4.0, 0]).astype(np.uint8)

    # Daytime atmospheric haze overlay
    if time_of_day == "daytime" and haze > 0.28:
        haze_strength = min((haze - 0.28) / 0.72, 1.0) * 0.18
        haze_color = np.array([252, 248, 232], dtype=np.float32)
        for c in range(3):
            canvas[:, :, c] = np.clip(
                canvas[:, :, c].astype(np.float32) * (1 - haze_strength) +
                haze_color[c] * haze_strength, 0, 255
            ).astype(np.uint8)

    # Vignette — darken corners
    cx, cy = w / 2.0, h / 2.0
    ys, xs = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xs - cx) / cx) ** 2 + ((ys - cy) / cy) ** 2)
    vignette = np.clip(1.0 - dist * 0.35, 0.62, 1.0).astype(np.float32)
    for c in range(3):
        canvas[:, :, c] = np.clip(
            canvas[:, :, c].astype(np.float32) * vignette, 0, 255
        ).astype(np.uint8)


# ── Entry point ───────────────────────────────────────────────────────────────

# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "art_params.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input art parameters file 'art_params.json' must exist in S3 before rendering the concrete scene image")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "concrete_scene.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output rendered scene image 'concrete_scene.png' must be present in S3 after successful execution")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_concrete_scene_image(folder: str, input1: str, output1: str) -> None:
    """
    Reads fused art parameters from S3, renders a high-resolution concrete
    representational scene image (1920×1080 PNG) using Pillow, numpy, and
    scipy, then uploads the result to S3.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    local_params = "art_params_render_local.json"
    local_output = "concrete_scene_render_local.png"

    try:
        faasr_get_file(local_file=local_params, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded art parameters from '{input1}'")

        with open(local_params) as f:
            params = json.load(f)

        # Validate required top-level blocks
        for block in ("sky_atmosphere", "celestial_placement", "scene_activity", "scene_elements"):
            if block not in params:
                msg = f"art_params ('{input1}') is missing required '{block}' block"
                faasr_log(msg)
                raise RuntimeError(msg)

        sky_atm = params["sky_atmosphere"]
        celestial = params["celestial_placement"]
        scene_act = params["scene_activity"]
        scene_el = params["scene_elements"]

        scene_type = scene_el.get("scene_type", "rural_landscape")
        season = scene_el.get("season", "unknown")
        time_of_day = scene_el.get("time_of_day", "daytime")
        lighting = scene_el.get("lighting_quality", "clear_sunlight")

        faasr_log(
            f"Rendering scene: type={scene_type}, season={season}, "
            f"time={time_of_day}, lighting={lighting}, "
            f"sky={sky_atm.get('sky_color_tone')}, "
            f"cloud_cov={sky_atm.get('cloud_coverage')}"
        )

        # Deterministic seed derived from scene parameters
        seed_str = (
            f"{scene_type}_{season}_{time_of_day}_{lighting}_"
            f"{sky_atm.get('sky_color_tone', '')}_{sky_atm.get('atmospheric_condition', '')}"
        )
        seed_val = abs(hash(seed_str)) % (2 ** 31)
        rng = np.random.default_rng(seed_val)

        # Allocate canvas (H × W × 3, uint8)
        canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

        _draw_sky(canvas, sky_atm, time_of_day, rng)
        faasr_log("Sky gradient layer complete")

        _draw_clouds(canvas, sky_atm, time_of_day, rng)
        faasr_log("Cloud layer complete")

        _draw_celestial(canvas, celestial, sky_atm, time_of_day, rng)
        faasr_log("Celestial objects rendered")

        _draw_terrain(canvas, scene_el, scene_act, sky_atm, rng)
        faasr_log("Terrain/scene layer complete")

        _draw_weather_effects(canvas, sky_atm, rng)
        faasr_log("Weather effects applied")

        _post_process(canvas, sky_atm, time_of_day)
        faasr_log("Post-processing (horizon blend, haze, vignette) complete")

        img = Image.fromarray(canvas, mode="RGB")
        img.save(local_output, format="PNG")
        faasr_log(f"Scene image saved locally: {WIDTH}×{HEIGHT} PNG")

        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log(f"Uploaded '{output1}' to S3 folder '{folder}'")

    finally:
        for tmp in [local_params, local_output]:
            if os.path.exists(tmp):
                os.remove(tmp)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---