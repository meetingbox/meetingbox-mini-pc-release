"""Single source of truth for UI content scaling.

Screens are laid out against the Figma 1260x800 artboard with proportional
``size_hint``/``pos_hint``, but absolute pixel values (font sizes, icon sizes,
fixed heights) are multiplied by a scale factor. Historically each screen
computed that factor from the fixed ``config.DISPLAY_WIDTH/DISPLAY_HEIGHT``
constants.

That breaks in the Windows floating-dock companion: there the 7" panel is
rendered at a *physical* centimetre size, so its pixel dimensions vary with the
monitor's true pixel density (EDID). The panel then had one size while the fonts
were scaled for a different, fixed size — so text looked correct on the design
laptop but too big/small on other monitors.

This module keeps ONE effective surface size that both the panel and all content
scale from, so the Figma proportions stay identical on every display and PPI.
On the Linux appliance and the plain desktop window the effective size is just
``DISPLAY_WIDTH x DISPLAY_HEIGHT`` (unchanged behaviour); the dock companion
overrides it with the measured panel size via ``set_effective_display_size``.
"""

FIGMA_W = 1260.0
FIGMA_H = 800.0

# When None, fall back to the config display size (appliance / plain window).
_eff_w: float | None = None
_eff_h: float | None = None


def _config_display_size() -> tuple[float, float]:
    # Imported lazily to avoid a circular import (config never imports ui_scale).
    from config import DISPLAY_HEIGHT, DISPLAY_WIDTH

    return float(DISPLAY_WIDTH), float(DISPLAY_HEIGHT)


def set_effective_display_size(w: float, h: float) -> None:
    """Set the pixel size screen content should scale against.

    Called by the dock companion once it knows the physical panel footprint.
    Must run BEFORE the screens are built (Kivy fixes each label's font size at
    widget-creation time), otherwise existing widgets keep the old scale.
    """
    global _eff_w, _eff_h
    try:
        w = float(w)
        h = float(h)
    except (TypeError, ValueError):
        return
    if w > 0 and h > 0:
        _eff_w, _eff_h = w, h


def effective_size() -> tuple[float, float]:
    if _eff_w and _eff_h:
        return _eff_w, _eff_h
    return _config_display_size()


def effective_width() -> float:
    return effective_size()[0]


def effective_height() -> float:
    return effective_size()[1]


def scale_for(fw: float = FIGMA_W, fh: float = FIGMA_H) -> float:
    """Uniform scale from an artboard of size ``fw x fh`` to the live surface."""
    w, h = effective_size()
    return min(w / float(fw), h / float(fh))


def figma_scale() -> float:
    """Uniform scale from the 1260x800 Figma artboard to the live surface."""
    return scale_for(FIGMA_W, FIGMA_H)


def ff(fs: float) -> int:
    """Scale a Figma font size (px) to the live surface, clamped to a floor."""
    return max(6, round(float(fs) * figma_scale()))
