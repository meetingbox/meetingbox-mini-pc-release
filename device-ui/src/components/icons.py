"""
Canvas-drawn icon widgets for MeetingBox device UI.

All icons use Kivy graphics primitives (Line, Ellipse, Triangle, Rectangle)
so they render correctly regardless of font support on the device.

Available icons (set via `kind` kwarg):
  'wifi'       – three arcs + dot
  'bluetooth'  – classic BT diamond symbol
  'battery'    – rectangle body + nub + fill level
  'volume'     – speaker cone + two sound-wave arcs
  'brightness' – circle + 8 radiating rays
  'airplane'   – triangle fuselage + wing line
  'settings'   – circle + 6 gear teeth
  'lock'       – padlock body + shackle arc
  'power'      – broken circle + center line
  'mic'        – capsule body + stand arc + base line
  'dnd'        – crescent moon (Do Not Disturb)

Usage:
    icon = Icon(kind='wifi', size=(24, 24), color=(1, 1, 1, 0.9))
    icon.set_color(COLORS['blue'])     # change color at runtime
    icon.set_level(0.75)               # battery / volume fill, 0-1
"""

from __future__ import annotations

import math
from typing import Tuple

from kivy.graphics import (
    Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle,
    Rotate, RoundedRectangle, Triangle,
)
from kivy.uix.widget import Widget

RGBA = Tuple[float, float, float, float]


def _stroke(**kwargs) -> Line:
    """Line with rounded caps and joints.

    Kivy defaults to square butt-ends, which is the main reason hand-drawn
    icons read as crude next to a real icon set — every stroke terminates in a
    hard corner. Rounding caps/joints is the single biggest fidelity win here.
    """
    kwargs.setdefault("cap", "round")
    kwargs.setdefault("joint", "round")
    return Line(**kwargs)


class Icon(Widget):
    """Generic canvas-drawn icon widget.

    Parameters
    ----------
    kind    : str   – one of the supported icon kinds (see module docstring)
    color   : tuple – initial RGBA color, default white
    level   : float – fill ratio 0-1, used by 'battery' and 'volume'
    """

    def __init__(
        self,
        kind: str,
        color: RGBA = (1.0, 1.0, 1.0, 0.9),
        level: float = 1.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._kind = kind
        self._color = color
        self._level = max(0.0, min(1.0, level))
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_color(self, rgba: RGBA):
        self._color = rgba
        self._redraw()

    def set_level(self, level: float):
        """Set fill ratio (0-1). Redraws immediately."""
        self._level = max(0.0, min(1.0, level))
        self._redraw()

    # ------------------------------------------------------------------
    # Draw dispatch
    # ------------------------------------------------------------------

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width < 1 or self.height < 1:
            return

        cx = self.center_x
        cy = self.center_y
        m = min(self.width, self.height)   # icon bounding square
        lw = max(1.2, m * 0.09)           # stroke width

        with self.canvas:
            Color(*self._color)
            fn = {
                "wifi":       self._wifi,
                "bluetooth":  self._bluetooth,
                "battery":    self._battery,
                "volume":     self._volume,
                "brightness": self._brightness,
                "airplane":   self._airplane,
                "settings":   self._settings,
                "lock":       self._lock,
                "power":      self._power,
                "mic":        self._mic,
                "dnd":        self._dnd,
            }.get(self._kind)
            if fn:
                fn(cx, cy, m, lw)

    # ------------------------------------------------------------------
    # Individual icon drawers
    # ------------------------------------------------------------------

    def _wifi(self, cx, cy, m, lw):
        """Signal dot with three arcs fanning above it.

        The old version hung everything off a dot at -0.42m, so the drawn shape
        sat in the bottom of the box with dead space above it. The fan is now
        balanced around the centre and the arcs open wider (124° vs 100°), which
        is closer to how a wifi glyph normally reads.
        """
        dot_cy = cy - m * 0.30
        d = max(3, m * 0.15)
        Ellipse(pos=(cx - d / 2, dot_cy - d / 2), size=(d, d))
        # Radii are spaced 0.20m apart. At the previous 0.15m spacing the gap
        # between bands was only ~0.06m against a 0.09m stroke, so the three
        # arcs crowded into a single blob at panel size.
        # Kivy ellipse angles: 0° = top, clockwise — a span centred on 0 arches
        # over the dot (∩).
        for r in (m * 0.22, m * 0.42, m * 0.62):
            _stroke(
                ellipse=(cx - r, dot_cy - r, r * 2, r * 2, -65, 65),
                width=lw * 0.9,
            )

    def _bluetooth(self, cx, cy, m, lw):
        """Classic Bluetooth B-diamond symbol.

        Vertical spine + two right-pointing chevrons (top & bottom half).
        """
        half_h = m * 0.44
        half_w = m * 0.24
        top    = cy + half_h
        bot    = cy - half_h
        right  = cx + half_w

        # One continuous path — spine bottom→top, then the two flags back down
        # through the centre. Drawing it as three separate strokes overdrew the
        # junctions, which thickened and blunted the corners of the rune.
        _stroke(points=[
            cx,    bot,                    # spine start
            cx,    top,                    # spine end / upper flag start
            right, cy + half_h * 0.50,     # upper flag tip
            cx,    cy,                     # waist
            right, cy - half_h * 0.50,     # lower flag tip
            cx,    bot,                    # back to the foot
        ], width=lw)

    def _battery(self, cx, cy, m, lw):
        """Rectangle body + positive nub + fill rect."""
        bw = m * 0.84
        bh = m * 0.40
        bx = cx - bw / 2
        by = cy - bh / 2
        nub_w = m * 0.07
        nub_h = bh * 0.42
        body_w = bw - nub_w

        # Body outline — rounded, like every real battery glyph.
        r_body = bh * 0.28
        _stroke(rounded_rectangle=(bx, by, body_w, bh, r_body), width=lw)
        # Positive nub (right side), rounded on its outer corners.
        RoundedRectangle(
            pos=(bx + body_w, cy - nub_h / 2),
            size=(nub_w, nub_h),
            radius=[nub_w * 0.45],
        )
        # Fill, inset and rounded so it echoes the body instead of a hard block.
        if self._level > 0.02:
            pad = lw * 1.2
            fill_w = max(0, (body_w - pad * 2) * self._level)
            if fill_w > 0:
                RoundedRectangle(
                    pos=(bx + pad, by + pad),
                    size=(fill_w, bh - pad * 2),
                    radius=[min(fill_w, bh - pad * 2) * 0.28],
                )

    def _volume(self, cx, cy, m, lw):
        """Speaker (neck + cone) + two sound-wave arcs.

        The cone alone was a bare triangle pointing the wrong way round; a real
        speaker glyph is a small rectangular neck with the cone flaring out of
        it.
        """
        sx = cx - m * 0.40
        tw = m * 0.28
        th = m * 0.38
        neck_w = tw * 0.42
        neck_h = th * 0.44
        # Neck (the driver box against the left edge)
        Rectangle(pos=(sx, cy - neck_h / 2), size=(neck_w, neck_h))
        # Cone flaring right from the neck
        Triangle(points=[
            sx + neck_w, cy - neck_h / 2,
            sx + neck_w, cy + neck_h / 2,
            sx + tw,     cy + th / 2,
        ])
        Triangle(points=[
            sx + neck_w, cy - neck_h / 2,
            sx + tw,     cy + th / 2,
            sx + tw,     cy - th / 2,
        ])
        # Sound-wave arcs. These used 315→405, i.e. a span centred on 0° — the
        # TOP of the circle — so the waves arched over the speaker instead of
        # radiating from it. Centred on 90° (Kivy's 3 o'clock) they open to the
        # right, which is what a volume glyph reads as.
        base_x = sx + tw
        for r in (m * 0.20, m * 0.34):
            _stroke(
                ellipse=(base_x - r, cy - r, r * 2, r * 2, 40, 140),
                width=lw,
            )

    def _brightness(self, cx, cy, m, lw):
        """Circle + 8 short radiating rays."""
        r_c = m * 0.20
        _stroke(circle=(cx, cy, r_c), width=lw)
        r1, r2 = m * 0.30, m * 0.44
        for angle_deg in range(0, 360, 45):
            rad = math.radians(angle_deg)
            _stroke(points=[
                cx + math.cos(rad) * r1, cy + math.sin(rad) * r1,
                cx + math.cos(rad) * r2, cy + math.sin(rad) * r2,
            ], width=lw)

    def _airplane(self, cx, cy, m, lw):
        """Upright airplane silhouette, drawn as one closed shape.

        Previously three disconnected strokes (fuselage, wing, tail) that read
        as random marks rather than a plane. Now a single symmetric outline:
        nose, swept wings, waist, tailplane.
        """
        s = m
        pts = [
            (0.00,  0.46),   # nose
            (0.09,  0.20),   # right shoulder
            (0.42, -0.04),   # right wingtip
            (0.42, -0.15),
            (0.09, -0.06),   # wing trailing edge back to body
            (0.07, -0.30),
            (0.20, -0.40),   # right tailplane tip
            (0.20, -0.47),
            (0.00, -0.40),   # tail centre
            (-0.20, -0.47),  # left tailplane tip
            (-0.20, -0.40),
            (-0.07, -0.30),
            (-0.09, -0.06),
            (-0.42, -0.15),  # left wingtip
            (-0.42, -0.04),
            (-0.09,  0.20),  # left shoulder
        ]
        flat = []
        for px, py in pts:
            flat.extend([cx + px * s, cy + py * s])
        _stroke(points=flat, width=lw, close=True)

    def _settings(self, cx, cy, m, lw):
        """Gear: hub ring + 8 rounded teeth around it.

        The old version drew straight spokes radiating from a circle, which
        reads as a sun/asterisk rather than a gear. Real teeth sit tangentially
        around the rim, so each is drawn as a small rounded rect rotated into
        place.
        """
        r_hub = m * 0.24
        _stroke(circle=(cx, cy, r_hub), width=lw)

        tooth_w = m * 0.14
        tooth_h = m * 0.14
        r_tooth = r_hub + tooth_h * 0.42
        for i in range(8):
            PushMatrix()
            Rotate(angle=i * 45.0, origin=(cx, cy))
            RoundedRectangle(
                pos=(cx - tooth_w / 2, cy + r_tooth - tooth_h / 2),
                size=(tooth_w, tooth_h),
                radius=[tooth_w * 0.32],
            )
            PopMatrix()

    def _lock(self, cx, cy, m, lw):
        """Padlock: rounded body + shackle arc rising from its top edge.

        The body was a sharp-cornered rectangle outline, which reads as a box
        rather than a padlock. A solid rounded body with the shackle springing
        from its top edge is the shape people actually recognise.
        """
        bw, bh = m * 0.54, m * 0.40
        bx = cx - bw / 2
        by = cy - m * 0.40
        RoundedRectangle(pos=(bx, by), size=(bw, bh), radius=[m * 0.09])

        # Shackle: the TOP half of a circle centred on the body's top edge, so
        # it arches over (∩) with both ends landing on the body. Angles 0→180
        # would give the right half of the circle instead.
        r = m * 0.17
        top = by + bh
        _stroke(
            ellipse=(cx - r, top - r, r * 2, r * 2, -90, 90),
            width=lw,
        )

    def _power(self, cx, cy, m, lw):
        """Power symbol: broken circle + vertical line to top."""
        r = m * 0.38
        # Circle arc leaving a gap at the top (30° gap each side)
        _stroke(ellipse=(cx - r, cy - r, r * 2, r * 2, 210, 510), width=lw * 1.3)
        # Vertical line from center to top
        _stroke(points=[cx, cy, cx, cy + r * 1.05], width=lw * 1.5)

    def _mic(self, cx, cy, m, lw):
        """Microphone: filled capsule + U-shaped stand cradle + stem and base.

        The cradle was drawn with angles 0→180, which in Kivy's convention
        (0° = top, clockwise) is the RIGHT half of the circle — a ")" beside the
        capsule rather than a "U" beneath it. It now spans 90→270, the bottom
        half, so it actually cradles the mic.
        """
        bw = m * 0.26
        bh = m * 0.44
        br = bw / 2
        bx = cx - br
        by = cy - m * 0.04
        # Solid capsule reads better at small sizes than a thin outline.
        RoundedRectangle(pos=(bx, by), size=(bw, bh), radius=[br])

        # Cradle: bottom half of a circle centred just under the capsule.
        stand_r = m * 0.27
        stand_cy = by + m * 0.05
        _stroke(
            ellipse=(cx - stand_r, stand_cy - stand_r, stand_r * 2, stand_r * 2, 90, 270),
            width=lw,
        )
        base_y = cy - m * 0.42
        # Stem from the cradle's lowest point down to the base.
        _stroke(points=[cx, stand_cy - stand_r, cx, base_y], width=lw)
        base_hw = m * 0.17
        _stroke(points=[cx - base_hw, base_y, cx + base_hw, base_y], width=lw)

    def _dnd(self, cx, cy, m, lw):
        """Do Not Disturb: crescent moon, as one closed outline.

        The old version mixed two angle conventions: the arcs used Kivy's
        ellipse angles (0° = top, clockwise) while the two lines meant to close
        the shape computed their endpoints with math.cos/sin (0° = right,
        counter-clockwise). Those lines therefore ran to points that were not on
        the arcs, and the crescent never closed.

        This builds the whole outline from explicit points in one convention:
        an outer arc, then the inner arc back, sized so the two circles actually
        intersect at the horns.
        """
        r_out = m * 0.42
        offset = m * 0.30
        theta = math.radians(55)          # half-angle to each horn
        # Inner radius that puts the inner circle through both horn points.
        r_in = math.sqrt(
            r_out * r_out - 2 * r_out * offset * math.cos(theta) + offset * offset
        )
        # Horn position, and its angle as seen from the inner circle's centre.
        hx, hy = r_out * math.cos(theta), r_out * math.sin(theta)
        phi = math.atan2(hy, hx - offset)

        steps = 28
        pts: list[float] = []
        # Outer edge: horn → over the top → around the left → bottom horn.
        a0, a1 = theta, 2 * math.pi - theta
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts += [cx + r_out * math.cos(a), cy + r_out * math.sin(a)]
        # Inner edge: back from the bottom horn to the top one, carving the bite.
        b0, b1 = 2 * math.pi - phi, phi
        for i in range(steps + 1):
            b = b0 + (b1 - b0) * i / steps
            pts += [cx + offset + r_in * math.cos(b), cy + r_in * math.sin(b)]
        _stroke(points=pts, width=lw, close=True)

