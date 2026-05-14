"""Client-side screenshot resize + coord scaling for vision models.

Background — why this lives in the SDK
--------------------------------------
Computer-use models (Anthropic CUA, OpenAI computer-use-preview, Gemini,
Kimi/Fireworks, etc.) return click coordinates **in resized-image space**,
not the original screenshot's pixel space. Each family also resizes the
image to its own internal cap if you send something larger — and that
resize is silent and only loosely documented. If you don't account for it,
clicks land at the wrong place and you debug in circles.

The cleanest fix is to resize the screenshot to a known target *before*
sending it to the model, then multiply the returned coords by the inverse
scale at dispatch time. That's what `scale_screenshot_for_model` does.
`mac.mouse.click` takes native display points, so the multiplication
brings model coords back into the right space.

Per-model caps are probed empirically and live in
`screenshot_cap_for_model`. Tweak there, not at call sites.
"""

from __future__ import annotations

import io

from PIL import Image


def screenshot_cap_for_model(model: str) -> int:
    """Long-edge cap (in pixels) for the resize that precedes vision input.

    Per-family caps are probed for click accuracy; lower caps trade detail
    for stable coordinates on models that drift past their internal limit.
    """
    m = (model or "").lower()
    if "opus-4-7" in m or "opus-4-8" in m or "opus-5" in m:
        return 2576  # Anthropic Opus 4.7+ caps at 2576px
    if "claude" in m or "anthropic/" in m:
        return 1568  # Other Anthropic models cap at 1568px
    if "kimi" in m or "fireworks" in m:
        return 896  # Kimi: y-coord accuracy degrades at >1024 (probed on tall iOS shots)
    return 1280  # OpenAI/Gemini fallback


def scale_screenshot_for_model(
    image_bytes: bytes, model: str
) -> tuple[bytes, int, int, float, float]:
    """Aspect-preserving resize of a screenshot to the model's vision cap.

    Returns `(resized_bytes, api_w, api_h, sx, sy)`:
        - `resized_bytes` — encoded image to send to the model
        - `api_w`, `api_h` — the resized image's dimensions
        - `sx`, `sy` — multiply model-returned coords by these to recover
          native display points

    If the image already fits within the cap, returns the input bytes
    untouched and `sx == sy == 1.0`. JPEG inputs stay JPEG (quality=85);
    PNG inputs stay PNG.
    """
    img = Image.open(io.BytesIO(image_bytes))
    native_w, native_h = img.size
    target = screenshot_cap_for_model(model)
    scale = min(target / native_w, target / native_h, 1.0)
    api_w = int(native_w * scale)
    api_h = int(native_h * scale)
    sx = native_w / api_w
    sy = native_h / api_h
    if scale == 1.0:
        return image_bytes, api_w, api_h, sx, sy
    resized = img.resize((api_w, api_h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    fmt = (img.format or "PNG").upper()
    if fmt == "JPEG":
        resized.convert("RGB").save(buf, format="JPEG", quality=85)
    else:
        resized.save(buf, format="PNG")
    return buf.getvalue(), api_w, api_h, sx, sy
