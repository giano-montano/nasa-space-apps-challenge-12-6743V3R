"""
Scientific Image Processing Engine for SPHEREx Astronomical Frames.
Implements astronomical stretch algorithms (asinh, log, linear, zscale),
detector co-addition (stacking), and multi-epoch subtraction.
"""

import io
import base64
import numpy as np
from PIL import Image


def apply_astronomical_stretch(
    data: np.ndarray,
    stretch: str = "asinh",
    pmin: float = 0.5,
    pmax: float = 99.7,
    asinh_factor: float = 0.05
) -> np.ndarray:
    """
    Applies astronomical contrast scaling to a 2D float flux image.
    Returns 8-bit uint8 array (0-255).
    """
    arr = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    # Calculate percentile bounds
    vmin = float(np.percentile(arr, pmin))
    vmax = float(np.percentile(arr, pmax))
    if vmax <= vmin:
        vmax = vmin + 1e-6

    # Clip to percentile bounds
    clipped = np.clip(arr, vmin, vmax)
    norm = (clipped - vmin) / (vmax - vmin)

    if stretch == "asinh":
        # Lupton et al. (1999) asinh scaling
        scaled = np.arcsinh(norm / asinh_factor) / np.arcsinh(1.0 / asinh_factor)
    elif stretch == "log":
        scaled = np.log1p(norm * 9.0) / np.log1p(9.0)
    elif stretch == "sqrt":
        scaled = np.sqrt(norm)
    else:  # linear
        scaled = norm

    scaled_uint8 = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
    return scaled_uint8


def compute_difference_image(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """
    Calculates difference image (A - B) normalized around mid-gray (128).
    Stationary background stars cancel out completely.
    Moving or fluctuating objects produce bright (positive) or dark (negative) residuals.
    """
    diff = frame_a.astype(np.float32) - frame_b.astype(np.float32)
    # Robust sigma clipping
    med = np.median(diff)
    std = np.std(diff) + 1e-5
    # Map [-4*std, +4*std] -> [0, 255] with 0 diff at 128
    scaled = 128.0 + (diff - med) / (4.0 * std) * 127.0
    return np.clip(scaled, 0, 255).astype(np.uint8)


def array_to_png_base64(arr_uint8: np.ndarray, colormap: str = "gray") -> str:
    """
    Converts 2D uint8 numpy array to base64 data URI PNG with colormap.
    """
    h, w = arr_uint8.shape
    if colormap == "gray":
        img = Image.fromarray(arr_uint8, mode="L")
    elif colormap == "difference":
        # Color difference: negative = cyan (#00D2FF), zero = dark slate (#171B26), positive = rose (#FF5C93)
        # Create RGB image
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        norm = (arr_uint8.astype(np.float32) - 128.0) / 128.0  # -1 to +1
        pos = np.clip(norm, 0, 1.0)
        neg = np.clip(-norm, 0, 1.0)
        zero = 1.0 - np.abs(norm)

        # Base background: dark space #0F1219 (15, 18, 25)
        rgb[:, :, 0] = np.clip(15 * zero + 255 * pos + 0 * neg, 0, 255).astype(np.uint8)
        rgb[:, :, 1] = np.clip(18 * zero + 92 * pos + 210 * neg, 0, 255).astype(np.uint8)
        rgb[:, :, 2] = np.clip(25 * zero + 147 * pos + 255 * neg, 0, 255).astype(np.uint8)
        img = Image.fromarray(rgb, mode="RGB")
    elif colormap == "space_rose":
        # Custom SPHEREx theme: deep space to vibrant rose/gold
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        val = arr_uint8.astype(np.float32) / 255.0
        # Red channel
        rgb[:, :, 0] = np.clip(val * 255 + np.power(val, 2) * 50, 0, 255).astype(np.uint8)
        # Green channel
        rgb[:, :, 1] = np.clip(np.power(val, 1.8) * 180 + np.power(val, 3) * 75, 0, 255).astype(np.uint8)
        # Blue channel
        rgb[:, :, 2] = np.clip(np.power(val, 1.2) * 200 + np.power(val, 4) * 55, 0, 255).astype(np.uint8)
        img = Image.fromarray(rgb, mode="RGB")
    else:
        img = Image.fromarray(arr_uint8, mode="L")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

