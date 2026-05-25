"""Preview the meeting-summary screen layout (Figma 659:838) on 1260×800."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from summary_layout import (  # noqa: E402
    ACTION_AVATAR_SIZE,
    ACTION_CHECK_SIZE,
    ACTION_DATE_W,
    ACTION_NAME_W,
    ACTION_ROW_HEIGHT,
    ACTION_ROW_YS,
    ACTION_TASK_W,
    ACTION_X_AVATAR,
    ACTION_X_CHECK,
    ACTION_X_DATE,
    ACTION_X_NAME,
    ACTION_X_TASK,
    ACTIONS_CARD,
    ACTIONS_ICON,
    ACTIONS_SCROLL_THUMB,
    ACTIONS_SCROLL_TRACK,
    ACTIONS_TITLE,
    BACK_BTN,
    BG_RGB,
    CANVAS_H,
    CARD_BORDER,
    CARD_FILL,
    CARD_RADIUS,
    DECISION_ROW_HEIGHT,
    DECISION_ROW_YS,
    DECISION_TEXT_W,
    DECISION_TICK_SIZE,
    DECISION_X_TEXT,
    DECISION_X_TICK,
    DECISIONS_CARD,
    DECISIONS_ICON,
    DECISIONS_SCROLL_THUMB,
    DECISIONS_SCROLL_TRACK,
    DECISIONS_TITLE,
    META_CARD,
    META_DATE,
    META_DATE_FS_RATIO,
    META_EXPORT,
    META_FILE_ICON,
    META_PARTICIPANTS,
    META_RECORDED,
    META_SHARE,
    META_TITLE,
    META_TITLE_FS_RATIO,
    PAGE_TITLE,
    PAGE_TITLE_FS_RATIO,
    ROW_TEXT_FS_RATIO,
    SCROLL_RADIUS,
    SCROLL_THUMB_FILL,
    SCROLL_TRACK_FILL,
    SECTION_TITLE_FS_RATIO,
    SUMMARY_CARD,
    SUMMARY_ICON,
    SUMMARY_IMAGE,
    SUMMARY_TEXT,
    SUMMARY_TEXT_FS_RATIO,
    SUMMARY_TITLE,
    SUMMARY_TITLE_FS_RATIO,
    canvas_box,
    font_px,
    row_box,
    scaled_canvas,
)

ASSETS = ROOT / "assets" / "summary" / "figma"
OUT = ASSETS / "summary_layout_preview.png"

SCREEN_W, SCREEN_H = 1260, 800

_RESOLUTIONS: tuple[tuple[int, int, str], ...] = (
    (1260, 800, "design_1260x800"),
    (1280, 720, "hd_16x9_1280x720"),
    (1024, 600, "kiosk_1024x600"),
    (800, 480, "tiny_800x480"),
    (1920, 1080, "fhd_1920x1080"),
)

_CARDS: tuple[dict, ...] = (META_CARD, SUMMARY_CARD, ACTIONS_CARD, DECISIONS_CARD)

# (filename, box) layers drawn on top of the cards in render order.
_IMAGE_LAYERS: tuple[tuple[str, dict], ...] = (
    ("btn_back.png", BACK_BTN),
    ("icon_file_box.png", META_FILE_ICON),
    ("chip_participants.png", META_PARTICIPANTS),
    ("chip_recorded.png", META_RECORDED),
    ("btn_export.png", META_EXPORT),
    ("btn_share.png", META_SHARE),
    ("ai_summary_icon.png", SUMMARY_ICON),
    ("ai_summary_image.png", SUMMARY_IMAGE),
    ("action_items_icon.png", ACTIONS_ICON),
    ("decisions_icon.png", DECISIONS_ICON),
)


def _rect(box, cw, ch, ox, oy):
    x0 = int(ox + box["x"] * cw)
    y0 = int(oy + box["y_top"] * ch)
    x1 = int(ox + (box["x"] + box["w"]) * cw)
    y1 = int(oy + (box["y_top"] + box["h"]) * ch)
    return x0, y0, x1, y1


def _draw_card(draw, box, cw, ch, ox, oy):
    x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
    r = max(2, int(CARD_RADIUS * min(cw / 1260.0, ch / 800.0)))
    fill = tuple(int(c * 255) for c in CARD_FILL[:3])
    border = tuple(int(c * 255) for c in CARD_BORDER[:3])
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill, outline=border, width=2)


def _draw_pill(draw, box, cw, ch, ox, oy, fill):
    x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
    r = max(1, int(SCROLL_RADIUS * min(cw / 1260.0, ch / 800.0)))
    fill_rgb = tuple(int(c * 255) for c in fill[:3])
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill_rgb)


def _draw_text(draw, box, cw, ch, ox, oy, text, fill, font, anchor="lm"):
    x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
    if anchor == "lm":
        draw.text((x0, (y0 + y1) // 2), text, fill=fill, font=font, anchor="lm")
    elif anchor == "ma":
        draw.text(((x0 + x1) // 2, y0), text, fill=fill, font=font, anchor="ma")


def _draw_wrap(draw, box, cw, ch, ox, oy, text, fill, font, max_lines: int = 3):
    """Naive word-wrap into ``max_lines`` lines inside the box."""
    x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
    max_w = x1 - x0
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and cur:
        last = lines[-1]
        while draw.textlength(last + "...", font=font) > max_w and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last + "..."
    line_h = max(font.size + 4, 1)
    for i, ln in enumerate(lines):
        draw.text((x0, y0 + i * line_h), ln, fill=fill, font=font, anchor="la")


def _render(screen_w: int, screen_h: int, out_path: Path) -> None:
    img = Image.new("RGB", (screen_w, screen_h), BG_RGB)
    cw, ch = scaled_canvas(screen_w, screen_h)
    ox = (screen_w - cw) / 2
    oy = (screen_h - ch) / 2

    draw = ImageDraw.Draw(img)

    # Card surfaces first.
    for card in _CARDS:
        _draw_card(draw, card, cw, ch, ox, oy)

    # Composite PNG layers.
    for name, box in _IMAGE_LAYERS:
        path = ASSETS / name
        if not path.is_file():
            print(f"SKIP {name}")
            continue
        asset = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = _rect(box, cw, ch, ox, oy)
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        asset = asset.resize((w, h), Image.Resampling.LANCZOS)
        img.paste(asset, (x0, y0), asset)

    # Mock data for the dynamic rows.
    sample_actions = (
        ("Update client on timeline", "Rahul s.", "May 23", True),
        ("Revise project plan", "Rahul s.", "May 23", True),
        ("Share new budget estimates", "Neha s.", "May 23", False),
        ("Prepare MVP requirements doc", "Arjun m.", "May 23", False),
    )
    sample_decisions = (
        "Launch delayed by 2 weeks",
        "Focus on MVP for initial release",
        "Budget reallocated for priority features",
        "Weekly syncs to continue every Tuesday",
    )

    card_y_top_actions = ACTIONS_CARD["y_top"] * 800.0
    card_y_top_decisions = DECISIONS_CARD["y_top"] * 800.0

    for idx, row_y in enumerate(ACTION_ROW_YS):
        task, name, date, done = sample_actions[idx]
        check_name = "action_check_done.png" if done else "action_check_pending.png"
        check_box = row_box(
            ACTION_X_CHECK, card_y_top_actions, row_y, ACTION_CHECK_SIZE, ACTION_CHECK_SIZE
        )
        check_path = ASSETS / check_name
        if check_path.is_file():
            asset = Image.open(check_path).convert("RGBA")
            x0, y0, x1, y1 = _rect(check_box, cw, ch, ox, oy)
            asset = asset.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
            img.paste(asset, (x0, y0), asset)
        avatar_box = row_box(
            ACTION_X_AVATAR, card_y_top_actions, row_y, ACTION_AVATAR_SIZE, ACTION_AVATAR_SIZE + 1
        )
        avatar_path = ASSETS / "action_avatar.png"
        if avatar_path.is_file():
            asset = Image.open(avatar_path).convert("RGBA")
            x0, y0, x1, y1 = _rect(avatar_box, cw, ch, ox, oy)
            asset = asset.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
            img.paste(asset, (x0, y0), asset)

    for row_y in DECISION_ROW_YS:
        tick_box = row_box(
            DECISION_X_TICK, card_y_top_decisions, row_y, DECISION_TICK_SIZE, DECISION_TICK_SIZE
        )
        tick_path = ASSETS / "decision_tick.png"
        if tick_path.is_file():
            asset = Image.open(tick_path).convert("RGBA")
            x0, y0, x1, y1 = _rect(tick_box, cw, ch, ox, oy)
            asset = asset.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
            img.paste(asset, (x0, y0), asset)

    # Scrollbar pills.
    _draw_pill(draw, ACTIONS_SCROLL_TRACK, cw, ch, ox, oy, SCROLL_TRACK_FILL)
    _draw_pill(draw, ACTIONS_SCROLL_THUMB, cw, ch, ox, oy, SCROLL_THUMB_FILL)
    _draw_pill(draw, DECISIONS_SCROLL_TRACK, cw, ch, ox, oy, SCROLL_TRACK_FILL)
    _draw_pill(draw, DECISIONS_SCROLL_THUMB, cw, ch, ox, oy, SCROLL_THUMB_FILL)

    # Text labels.
    try:
        ft_h = ImageFont.truetype("arialbd.ttf", font_px(PAGE_TITLE_FS_RATIO, ch))
        ft_meta_title = ImageFont.truetype("arialbd.ttf", font_px(META_TITLE_FS_RATIO, ch))
        ft_meta_date = ImageFont.truetype("arial.ttf", font_px(META_DATE_FS_RATIO, ch))
        ft_summary_title = ImageFont.truetype("arialbd.ttf", font_px(SUMMARY_TITLE_FS_RATIO, ch))
        ft_summary_body = ImageFont.truetype("arial.ttf", font_px(SUMMARY_TEXT_FS_RATIO, ch))
        ft_section = ImageFont.truetype("arial.ttf", font_px(SECTION_TITLE_FS_RATIO, ch))
        ft_row = ImageFont.truetype("arial.ttf", font_px(ROW_TEXT_FS_RATIO, ch))
    except OSError:
        ft_h = ft_meta_title = ft_meta_date = ft_summary_title = ft_summary_body = (
            ft_section
        ) = ft_row = ImageFont.load_default()

    white = (255, 255, 255)
    muted = (182, 186, 242)
    hint = (155, 162, 178)

    _draw_text(draw, PAGE_TITLE, cw, ch, ox, oy, "Meeting Summary", white, ft_h, "lm")
    _draw_text(draw, META_TITLE, cw, ch, ox, oy, "Product Sync", white, ft_meta_title, "lm")
    _draw_text(draw, META_DATE, cw, ch, ox, oy, "May 21, 11:00 AM  45 min", muted, ft_meta_date, "lm")
    _draw_text(draw, SUMMARY_TITLE, cw, ch, ox, oy, "AI Summary", white, ft_summary_title, "lm")
    _draw_wrap(
        draw,
        SUMMARY_TEXT,
        cw,
        ch,
        ox,
        oy,
        "The team aligned on the initial release plan, discussed budget constraints, "
        "and identified key risks. The launch is delayed by 2 weeks to accommodate the "
        "required changes and ensure quality.",
        hint,
        ft_summary_body,
        max_lines=3,
    )
    _draw_text(draw, ACTIONS_TITLE, cw, ch, ox, oy, "Action items", white, ft_section, "lm")
    _draw_text(draw, DECISIONS_TITLE, cw, ch, ox, oy, "Decisions Made", white, ft_section, "lm")

    for idx, row_y in enumerate(ACTION_ROW_YS):
        task, name, date, _done = sample_actions[idx]
        _draw_text(
            draw,
            row_box(ACTION_X_TASK, card_y_top_actions, row_y, ACTION_TASK_W, ACTION_ROW_HEIGHT),
            cw, ch, ox, oy, task, hint, ft_row, "lm",
        )
        _draw_text(
            draw,
            row_box(ACTION_X_NAME, card_y_top_actions, row_y, ACTION_NAME_W, ACTION_ROW_HEIGHT),
            cw, ch, ox, oy, name, hint, ft_row, "lm",
        )
        _draw_text(
            draw,
            row_box(ACTION_X_DATE, card_y_top_actions, row_y, ACTION_DATE_W, ACTION_ROW_HEIGHT),
            cw, ch, ox, oy, date, hint, ft_row, "lm",
        )

    for idx, row_y in enumerate(DECISION_ROW_YS):
        _draw_text(
            draw,
            row_box(DECISION_X_TEXT, card_y_top_decisions, row_y, DECISION_TEXT_W, DECISION_ROW_HEIGHT),
            cw, ch, ox, oy, sample_decisions[idx], hint, ft_row, "lm",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    print(f"Wrote {out_path} ({screen_w}x{screen_h})")


def main() -> None:
    _render(SCREEN_W, SCREEN_H, OUT)
    if len(sys.argv) > 1:
        for sw, sh, tag in _RESOLUTIONS:
            _render(sw, sh, ASSETS / f"summary_layout_preview_{tag}.png")


if __name__ == "__main__":
    main()
