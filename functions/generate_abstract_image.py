import colorsys
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "art_params.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Input art_params.json must exist in S3 before abstract image generation can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "abstract_art.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Output abstract_art.png must have been uploaded to S3 after image generation completes")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_abstract_image(folder: str, input1: str, output1: str) -> None:
    """
    Downloads art_params.json from S3. Uses the algorithmically derived visual
    parameters (color palettes, shape distributions, layer compositions, fractal
    seeds, noise frequencies, opacity levels) to programmatically render a
    high-resolution abstract modern art image using layered geometric shapes,
    flow fields, and noise-based gradients. Saves the resulting PNG to S3.

    No external APIs or credentials are required — all rendering is deterministic
    from the fused art parameter set produced by fuse_data_into_art_params.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting abstract art image generation")

    local_input = "art_params_generate_local.json"
    local_output = "abstract_art_generate_local.png"

    try:
        # -----------------------------------------------------------------------
        # Download and parse the art parameters
        # -----------------------------------------------------------------------
        faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)
        faasr_log(f"Downloaded '{input1}' from S3 folder '{folder}'")

        with open(local_input) as f:
            params = json.load(f)

        cp = params.get("color_palette")
        sd = params.get("shape_distribution")
        tp = params.get("texture_params")
        cr = params.get("composition_rules")

        for section_name, section_val in [
            ("color_palette", cp),
            ("shape_distribution", sd),
            ("texture_params", tp),
            ("composition_rules", cr),
        ]:
            if not section_val:
                msg = f"Art params missing or empty section '{section_name}'"
                faasr_log(msg)
                raise RuntimeError(msg)

        # -----------------------------------------------------------------------
        # Extract parameters
        # -----------------------------------------------------------------------
        # Color palette
        hues_deg = [float(h) for h in cp.get("hues_degrees", [30, 60, 90, 120, 150])]
        saturation = float(cp.get("saturation", 0.7))
        brightness = float(cp.get("brightness", 0.8))
        overlay_effect = cp.get("overlay_effect", "none")

        # Texture
        noise_freq = float(tp.get("noise_frequency", 2.0))
        noise_amp = float(tp.get("noise_amplitude", 0.3))
        stroke_weight = float(tp.get("stroke_weight", 2.0))
        wind_dir_factor = float(tp.get("wind_directional_factor", 0.3))
        texture_type = tp.get("texture_type", "granular")

        # Composition
        layer_count = max(1, int(cr.get("layer_count", 4)))
        focal_point = cr.get("focal_point", "center")
        radial_symmetry = bool(cr.get("radial_symmetry", False))
        element_density = float(cr.get("element_density", 0.5))
        compositional_flow = cr.get("compositional_flow", "lateral")
        movement_direction = cr.get("movement_direction", "horizontal")
        golden_ratio_guide = bool(cr.get("golden_ratio_guide", True))

        # Shape distribution
        primary_shape_count = max(3, int(sd.get("primary_shape_count", 5)))
        circle_ratio = float(sd.get("circle_ratio", 0.5))
        bg_density = float(sd.get("background_shape_density", 0.3))

        faasr_log(
            f"Parameters: palette={cp.get('base_palette_name')}, "
            f"texture={texture_type}, flow={compositional_flow}, "
            f"focal={focal_point}, layers={layer_count}"
        )

        # -----------------------------------------------------------------------
        # Image canvas — high resolution
        # -----------------------------------------------------------------------
        W, H = 2400, 2400

        # -----------------------------------------------------------------------
        # Deterministic RNG seed derived from art parameters
        # -----------------------------------------------------------------------
        seed_val = int(abs(sum(hues_deg)) * 100 + noise_freq * 1000 + layer_count * 37) % (2**31)
        rng = np.random.default_rng(seed_val)

        # -----------------------------------------------------------------------
        # Color helpers
        # -----------------------------------------------------------------------
        def hsv_to_rgb_int(h_deg, s, v):
            """Convert HSV (hue in degrees) to an (R, G, B) int triple."""
            r, g, b = colorsys.hsv_to_rgb((h_deg % 360) / 360.0,
                                          float(np.clip(s, 0.0, 1.0)),
                                          float(np.clip(v, 0.0, 1.0)))
            return (int(r * 255), int(g * 255), int(b * 255))

        # Three tonal variants of the palette
        colors_mid = [hsv_to_rgb_int(h, saturation, brightness) for h in hues_deg]
        colors_dark = [hsv_to_rgb_int(h, saturation * 0.9, brightness * 0.35) for h in hues_deg]
        colors_light = [hsv_to_rgb_int(h, saturation * 0.35, min(1.0, brightness * 1.3))
                        for h in hues_deg]

        # Matplotlib colormap from the dark palette (used for smooth gradient)
        mpl_colors_dark = [tuple(c / 255.0 for c in rgb) for rgb in colors_dark]
        mpl_cmap = mcolors.LinearSegmentedColormap.from_list(
            "art_palette_dark", mpl_colors_dark, N=512
        )

        # -----------------------------------------------------------------------
        # 1. Background gradient (matplotlib colormap → numpy → PIL)
        # -----------------------------------------------------------------------
        faasr_log("Rendering background gradient")

        if compositional_flow == "ascending":
            # Dark at bottom, lighter toward top
            t = np.linspace(1.0, 0.0, H)[:, np.newaxis] * np.ones((1, W))
        elif compositional_flow == "descending":
            t = np.linspace(0.0, 1.0, H)[:, np.newaxis] * np.ones((1, W))
        else:
            # Lateral gradient (left to right)
            t = np.ones((H, 1)) * np.linspace(0.0, 1.0, W)[np.newaxis, :]

        # Apply the matplotlib colormap; result is (H, W, 4) float in [0,1]
        bg_rgba = (mpl_cmap(t) * 255).astype(np.uint8)
        bg_img = Image.fromarray(bg_rgba, "RGBA")

        # Working canvas stays RGBA throughout compositing
        canvas = bg_img.copy()

        # -----------------------------------------------------------------------
        # 2. Noise texture layer (multi-octave sine approximation of Perlin noise)
        # -----------------------------------------------------------------------
        faasr_log("Generating noise texture")

        xs = np.linspace(0.0, noise_freq * 2.0 * np.pi, W, dtype=np.float32)
        ys = np.linspace(0.0, noise_freq * 2.0 * np.pi, H, dtype=np.float32)
        Xg, Yg = np.meshgrid(xs, ys)

        noise = np.zeros((H, W), dtype=np.float32)
        freq_mul = 1.0
        amp_mul = 1.0
        for _ in range(5):
            ang = float(rng.uniform(0.0, 2.0 * np.pi))
            phase = float(rng.uniform(0.0, 2.0 * np.pi))
            noise += amp_mul * np.sin(
                freq_mul * (Xg * math.cos(ang) + Yg * math.sin(ang)) + phase
            )
            freq_mul *= 2.0
            amp_mul *= 0.5

        # Normalise to [0, 1]
        noise_min, noise_max = noise.min(), noise.max()
        noise = (noise - noise_min) / (noise_max - noise_min + 1e-9)

        # Blend a mid-palette color modulated by the noise field
        mid_rgb = np.array(colors_mid[len(colors_mid) // 2], dtype=np.float32)
        noise_alpha = (noise * noise_amp * 200.0).astype(np.uint8)
        noise_rgb = (noise[:, :, np.newaxis] * mid_rgb).astype(np.uint8)
        noise_rgba = np.dstack([noise_rgb, noise_alpha])
        noise_img = Image.fromarray(noise_rgba, "RGBA")
        canvas.alpha_composite(noise_img)

        # -----------------------------------------------------------------------
        # 3. Flow field (direction driven by noise + composition + wind)
        # -----------------------------------------------------------------------
        faasr_log("Rendering flow field")

        flow_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        flow_draw = ImageDraw.Draw(flow_overlay)

        n_flow = max(30, int(120 * element_density))
        for i in range(n_flow):
            x0 = float(rng.uniform(0, W))
            y0 = float(rng.uniform(0, H))
            cidx = i % len(colors_mid)
            fc = colors_mid[cidx]
            flow_alpha = int(45 + 75 * float(rng.random()))
            step_size = 16.0 + stroke_weight * 4.0
            n_steps = max(8, int(10 + 20 * element_density))
            sw = max(1, int(stroke_weight * 0.8))

            # Base angle from compositional movement direction
            if movement_direction == "upward":
                base_ang = -math.pi / 2.0
            elif movement_direction == "downward":
                base_ang = math.pi / 2.0
            else:
                base_ang = 0.0

            cx, cy = x0, y0
            prev = (cx, cy)
            for s in range(n_steps):
                nv = float(noise[int(cy) % H, int(cx) % W])
                ang = (base_ang
                       + wind_dir_factor * math.pi * 0.4
                       + (nv - 0.5) * math.pi * 1.8)
                nx = cx + math.cos(ang) * step_size
                ny = cy + math.sin(ang) * step_size

                # Skip segment if it would jump across the canvas (wrap artefact)
                if abs(nx - cx) < W * 0.35 and abs(ny - cy) < H * 0.35:
                    lw = max(1, sw + int(sw * (1.0 - s / n_steps)))
                    flow_draw.line([prev, (nx, ny)], fill=fc + (flow_alpha,), width=lw)

                cx = nx % W
                cy = ny % H
                prev = (cx, cy)

        canvas.alpha_composite(flow_overlay)

        # -----------------------------------------------------------------------
        # 4. Layered geometric shapes (circles + polygons)
        # -----------------------------------------------------------------------
        faasr_log(f"Rendering {layer_count} shape layers")

        focal_map = {
            "center":      (W * 0.50, H * 0.50),
            "edges":       (W * 0.08, H * 0.50),
            "upper_right": (W * 0.78, H * 0.22),
            "lower_left":  (W * 0.22, H * 0.78),
        }
        fx, fy = focal_map.get(focal_point, (W * 0.5, H * 0.5))

        phi = (1.0 + math.sqrt(5.0)) / 2.0  # golden ratio

        for layer in range(layer_count):
            layer_t = layer / max(layer_count - 1, 1)
            layer_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer_draw = ImageDraw.Draw(layer_overlay)

            # More shapes in earlier (background) layers
            n_shapes = max(3, int(primary_shape_count * (1.6 - layer_t * 0.6)))

            for s_idx in range(n_shapes):
                # Position: golden-ratio spiral around focal point, or random-biased
                if golden_ratio_guide and s_idx % 3 == 0:
                    gr_ang = s_idx * 2.0 * math.pi / phi
                    gr_r = math.sqrt(s_idx + 1) * W * 0.038
                    sx = float(np.clip(fx + gr_r * math.cos(gr_ang), 0, W))
                    sy = float(np.clip(fy + gr_r * math.sin(gr_ang), 0, H))
                else:
                    bias = max(0.1, 0.55 - layer_t * 0.25)
                    sx = bias * fx + (1.0 - bias) * float(rng.uniform(0, W))
                    sy = bias * fy + (1.0 - bias) * float(rng.uniform(0, H))

                # Size decreases in later (foreground) layers for depth illusion
                size_base = W * 0.11 * (1.3 - layer_t * 0.5)
                size = size_base * float(rng.uniform(0.35, 1.0))

                # Cycle through palette colors
                cidx = (layer * n_shapes + s_idx) % len(colors_mid)
                col = colors_mid[cidx]
                shape_alpha = int(
                    55 + 130 * (1.0 - layer_t * 0.65) * float(rng.uniform(0.45, 1.0))
                )

                roll = float(rng.uniform(0.0, 1.0))

                # Radial symmetry: mirror across centre
                positions = [(sx, sy)]
                if radial_symmetry:
                    positions += [
                        (W - sx, sy),
                        (sx, H - sy),
                        (W - sx, H - sy),
                    ]

                for px, py in positions:
                    if roll < circle_ratio:
                        # Ellipse (slightly non-uniform for organic feel)
                        rx = size * float(rng.uniform(0.8, 1.2))
                        ry = size * float(rng.uniform(0.8, 1.2))
                        layer_draw.ellipse(
                            [px - rx, py - ry, px + rx, py + ry],
                            fill=col + (shape_alpha,),
                        )
                    else:
                        # Irregular convex polygon
                        n_sides = int(3 + int(rng.integers(0, 6)))
                        base_rot = float(rng.uniform(0.0, 2.0 * math.pi))
                        pts = [
                            (
                                px + size * math.cos(base_rot + 2.0 * math.pi * i / n_sides)
                                     * float(rng.uniform(0.75, 1.25)),
                                py + size * math.sin(base_rot + 2.0 * math.pi * i / n_sides)
                                     * float(rng.uniform(0.75, 1.25)),
                            )
                            for i in range(n_sides)
                        ]
                        layer_draw.polygon(pts, fill=col + (shape_alpha,))

            canvas.alpha_composite(layer_overlay)
            faasr_log(f"  Layer {layer + 1}/{layer_count} composited ({n_shapes} shapes)")

        # -----------------------------------------------------------------------
        # 5. Background micro-shapes (constellation density → star-like scatter)
        # -----------------------------------------------------------------------
        faasr_log("Rendering background micro-shapes")

        micro_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        micro_draw = ImageDraw.Draw(micro_overlay)
        n_micro = max(10, int(350 * bg_density))
        for _ in range(n_micro):
            mx = float(rng.uniform(0, W))
            my = float(rng.uniform(0, H))
            ms = float(rng.uniform(3, 22))
            cidx = int(rng.integers(0, len(colors_light)))
            mc = colors_light[cidx]
            m_alpha = int(25 + 55 * float(rng.random()))
            micro_draw.ellipse(
                [mx - ms, my - ms, mx + ms, my + ms],
                fill=mc + (m_alpha,),
            )
        canvas.alpha_composite(micro_overlay)

        # -----------------------------------------------------------------------
        # 6. Weather overlay effect
        # -----------------------------------------------------------------------
        faasr_log(f"Applying overlay effect: '{overlay_effect}'")

        if overlay_effect == "fog":
            fog_img = Image.new("RGBA", (W, H), (200, 210, 230, 65))
            canvas.alpha_composite(fog_img)
            # Soft blur for atmospheric diffusion
            canvas = canvas.convert("RGB").filter(ImageFilter.GaussianBlur(radius=2))
            canvas = canvas.convert("RGBA")

        elif overlay_effect == "rain":
            rain_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            rain_draw = ImageDraw.Draw(rain_overlay)
            n_drops = max(50, int(700 * element_density))
            for _ in range(n_drops):
                rx = float(rng.uniform(0, W))
                ry = float(rng.uniform(0, H))
                rl = float(rng.uniform(18, 55))
                rain_draw.line(
                    [(rx, ry), (rx + rl * 0.15, ry + rl)],
                    fill=(190, 215, 255, 75),
                    width=1,
                )
            canvas.alpha_composite(rain_overlay)

        elif overlay_effect == "snow":
            snow_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            snow_draw = ImageDraw.Draw(snow_overlay)
            n_flakes = max(50, int(450 * element_density))
            for _ in range(n_flakes):
                sx2 = float(rng.uniform(0, W))
                sy2 = float(rng.uniform(0, H))
                sr2 = float(rng.uniform(2, 15))
                snow_draw.ellipse(
                    [sx2 - sr2, sy2 - sr2, sx2 + sr2, sy2 + sr2],
                    fill=(248, 252, 255, 130),
                )
            canvas.alpha_composite(snow_overlay)

        elif overlay_effect == "storm":
            storm_overlay = Image.new("RGBA", (W, H), (4, 4, 18, 115))
            storm_draw = ImageDraw.Draw(storm_overlay)
            # Lightning bolt paths
            for _ in range(6):
                lx2 = float(rng.uniform(W * 0.15, W * 0.85))
                cx3, cy3 = lx2, 0.0
                n_seg = max(6, int(rng.integers(7, 15)))
                for _ in range(n_seg):
                    nx3 = cx3 + float(rng.uniform(-90, 90))
                    ny3 = cy3 + H / n_seg
                    storm_draw.line(
                        [(cx3, cy3), (nx3, ny3)],
                        fill=(255, 252, 200, 210),
                        width=2,
                    )
                    cx3, cy3 = nx3, ny3
            canvas.alpha_composite(storm_overlay)

        elif overlay_effect == "light_cloud":
            cloud_img = Image.new("RGBA", (W, H), (228, 232, 248, 22))
            canvas.alpha_composite(cloud_img)

        # "none" and "mixed" require no additional overlay

        # -----------------------------------------------------------------------
        # 7. Final texture pass via scipy
        # -----------------------------------------------------------------------
        faasr_log(f"Applying final texture pass: texture_type='{texture_type}'")

        canvas_rgb = canvas.convert("RGB")
        canvas_arr = np.array(canvas_rgb, dtype=np.float32)

        if texture_type == "smooth":
            # Gaussian blur smooths impasto / brush stroke edges
            canvas_arr = gaussian_filter(canvas_arr, sigma=[1.8, 1.8, 0])

        elif texture_type == "rough":
            # Moderate grain to mimic textured canvas
            grain = rng.normal(0.0, 12.0, canvas_arr.shape).astype(np.float32)
            canvas_arr = np.clip(canvas_arr + grain, 0, 255)

        elif texture_type == "chaotic":
            # Heavy grain + slight per-channel blur for painterly chaos
            grain = rng.normal(0.0, 22.0, canvas_arr.shape).astype(np.float32)
            canvas_arr = np.clip(canvas_arr + grain, 0, 255)
            canvas_arr = gaussian_filter(canvas_arr, sigma=[0.8, 0.8, 0])

        # "granular" → no additional pass (the raw noise texture is enough)

        canvas_final = Image.fromarray(canvas_arr.astype(np.uint8), "RGB")

        # -----------------------------------------------------------------------
        # Save and upload
        # -----------------------------------------------------------------------
        faasr_log(f"Saving high-resolution PNG ({W}x{H})")
        canvas_final.save(local_output, format="PNG")

        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log(
            f"Abstract art image uploaded to S3 folder '{folder}' as '{output1}' "
            f"({W}x{H} px, overlay='{overlay_effect}', texture='{texture_type}')"
        )

    finally:
        for tmp_path in [local_input, local_output]:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---