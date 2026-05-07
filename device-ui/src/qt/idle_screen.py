"""PySide6 Idle screen — Figma ``#338:60`` (logical frame 892×573).

Structural layout uses ``QVBoxLayout`` / ``QHBoxLayout`` only. The background
image is a dedicated ``CoverImageWidget`` layer stacked *under* content
(decorative).

No ``move()`` / ``setGeometry()`` for major regions — only proportional margins
derived from window size / :mod:`qt.scaling`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from qt.cover_image import CoverImageWidget
from qt.scaling import IDLE_FRAME, sp, spf, scale_from_window

_DEVICE_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = _DEVICE_ROOT / "assets"
_IDLE = _ASSETS / "idle"


def _png(name: str) -> str | None:
    p = _IDLE / name
    return str(p) if p.is_file() else None


class IdleScreen(QWidget):
    """Fullscreen idle / lock-style surface."""

    PREFIX = "Now : "

    def __init__(self) -> None:
        super().__init__()
        self._scale = 1.0
        self._meet_body = "No meetings today"
        self._clock_row: QHBoxLayout | None = None
        self._weather_gap_target: QWidget | None = None

        stack_host = QWidget(self)
        slo = QStackedLayout(stack_host)
        slo.setStackingMode(QStackedLayout.StackingMode.StackAll)
        slo.setContentsMargins(0, 0, 0, 0)

        self._bg = CoverImageWidget(_png("background_landscape.png"), fallback_hex="#010c25")
        slo.addWidget(self._bg)

        self._pane = QWidget()
        self._pane.setAttribute(Qt.WA_TranslucentBackground, True)
        self._pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        slo.addWidget(self._pane)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(stack_host)

        lay = QVBoxLayout(self._pane)
        lay.setSpacing(0)
        self._main = lay

        # ---- Top: clock | weather ----
        top = QHBoxLayout()
        clock = QVBoxLayout()
        clock.setSpacing(0)

        self._greeting = QLabel()
        self._greeting.setStyleSheet("color: #ffffff;")

        self._clock_row = QHBoxLayout()
        self._clock_row.setSpacing(0)
        self._clock_row.setContentsMargins(0, 0, 0, 0)
        self._time = QLabel()
        self._time.setStyleSheet("color: #ffffff;")
        self._ampm = QLabel()
        self._ampm.setStyleSheet("color: #b6baf2;")
        self._clock_row.addWidget(self._time, 0, Qt.AlignmentFlag.AlignBottom)
        self._clock_row.addWidget(self._ampm, 0, Qt.AlignmentFlag.AlignBottom)

        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet("color: #ffffff;")

        clock.addWidget(self._greeting)
        clock.addLayout(self._clock_row)
        clock.addWidget(self._date_lbl)

        top.addLayout(clock, stretch=1)

        weather = QHBoxLayout()
        weather.setSpacing(0)
        self._wx_ic = QLabel()
        self._temp = QLabel()
        self._cond = QLabel()
        self._temp.setStyleSheet("color: #ffffff;")
        self._cond.setStyleSheet("color: #b6baf2;")
        self._temp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._cond.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        wx_txt = QVBoxLayout()
        wx_txt.addWidget(self._temp, alignment=Qt.AlignmentFlag.AlignRight)
        wx_txt.addWidget(self._cond, alignment=Qt.AlignmentFlag.AlignRight)
        wx_txt.setSpacing(0)

        weather.addWidget(self._wx_ic, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gap = QWidget()
        self._weather_gap_target = gap
        weather.addWidget(gap, 0)
        weather.addLayout(wx_txt, 1)

        ww = QWidget()
        ww.setLayout(weather)
        top.addWidget(ww, stretch=0, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        lay.addLayout(top)

        lay.addStretch(1)

        # ---- Bottom: Next up | Record card ----
        bottom = QHBoxLayout()
        bottom.setSpacing(0)

        next_col = QVBoxLayout()
        next_col.setSpacing(0)
        self._next_lbl = QLabel("Next up")
        self._next_lbl.setStyleSheet("color: #006bf9;")

        nrow = QHBoxLayout()
        self._cal = QLabel()
        self._meet_time = QLabel("--:-- --")
        self._meet_time.setStyleSheet("color: #006bf9;")
        nrow.addWidget(self._cal, 0)
        nrow.addWidget(self._meet_time, 1)

        self._meet_title = QLabel()
        self._meet_title.setWordWrap(False)
        self._meet_title.setStyleSheet("color: #ffffff;")

        self._more_lbl = QLabel()
        self._more_lbl.setStyleSheet("color: #006bf9;")

        next_col.addWidget(self._next_lbl)
        next_col.addLayout(nrow)
        next_col.addWidget(self._meet_title)
        next_col.addWidget(self._more_lbl)

        nw = QWidget()
        nw.setLayout(next_col)
        bottom.addWidget(nw, stretch=1)

        self._rec_card = QWidget()
        self._rec_card.setObjectName("IdleRecCard")
        r_in = QHBoxLayout(self._rec_card)
        self._mic = QLabel()
        r_txt = QVBoxLayout()
        self._cta1 = QLabel("Start Recording")
        self._cta2 = QLabel('Tap or say "start recording"')
        self._cta1.setStyleSheet("color: #ffffff;")
        self._cta2.setStyleSheet("color: #ffffff;")
        r_txt.addWidget(self._cta1)
        r_txt.addWidget(self._cta2)
        r_in.addWidget(self._mic)
        r_in.addLayout(r_txt)

        bottom.addWidget(self._rec_card, stretch=0)

        lay.addLayout(bottom)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        self._apply_demo_texts()
        self._tick()

    def _wf(self, px: float) -> QFont:
        fz = max(10, int(round(px)))
        f = QFont()
        f.setPixelSize(fz)
        f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        return f

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self._scale = scale_from_window(w, h, IDLE_FRAME)
        s = self._scale

        ml, mt, mr, mb = sp(46, s), sp(35, s), sp(48, s), sp(43, s)
        self._main.setContentsMargins(ml, mt, mr, mb)

        # Figma font sizes
        self._greeting.setFont(self._wf(spf(20, s)))
        self._time.setFont(self._wf(spf(100, s)))
        self._ampm.setFont(self._wf(spf(35, s)))
        self._date_lbl.setFont(self._wf(spf(30, s)))
        self._temp.setFont(self._wf(spf(35, s)))
        self._cond.setFont(self._wf(spf(30, s)))
        self._next_lbl.setFont(self._wf(spf(28, s)))
        self._meet_time.setFont(self._wf(spf(28, s)))
        self._meet_title.setFont(self._wf(spf(31, s)))
        self._more_lbl.setFont(self._wf(spf(28, s)))
        self._cta1.setFont(self._wf(spf(30, s)))
        self._cta2.setFont(self._wf(spf(20, s)))

        # Spacing: time ↔ AM/PM gap 29 design px
        if self._clock_row is not None:
            self._clock_row.setSpacing(sp(29, s))

        # Weather: icon + 18 px gap before text block
        if self._weather_gap_target is not None:
            self._weather_gap_target.setFixedWidth(sp(18, s))

        # Pixmaps scale with height
        ir = _png("icon_sun.png")
        if ir:
            self._wx_ic.setPixmap(
                QPixmap(ir).scaledToHeight(
                    sp(64, s),
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
        ic = _png("icon_calendar.png")
        if ic:
            self._cal.setPixmap(
                QPixmap(ic).scaledToHeight(
                    sp(34, s),
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
        im = _png("mic_orb.png")
        if im:
            side = sp(101, s)
            self._mic.setPixmap(
                QPixmap(im).scaled(
                    side,
                    side,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )

        self._rec_card.setMinimumSize(sp(414, s), sp(167, s))
        self._meet_title.setMaximumWidth(sp(282, s))
        self._meet_title.setMinimumWidth(1)
        self._elide_meeting_title()

        br = max(10, sp(30, s))
        bw = max(2, round(3 * s))
        self._rec_card.setStyleSheet(
            f"""
            QWidget#IdleRecCard {{
              background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #0038b6, stop:1 #002376);
              border: {bw}px solid #034EE2;
              border-radius: {br}px;
            }}
            """
        )

    def _elide_meeting_title(self) -> None:
        full = f"{self.PREFIX}{self._meet_body}"
        self._meet_title.setToolTip(full)
        fm = self._meet_title.fontMetrics()
        w = self._meet_title.width()
        if w <= 0:
            self._meet_title.setText(full)
            return
        self._meet_title.setText(
            fm.elidedText(full, Qt.TextElideMode.ElideRight, w),
        )

    def _tick(self) -> None:
        n = datetime.now()
        self._time.setText(n.strftime("%I:%M").lstrip("0") or "12:00")
        self._ampm.setText(n.strftime("%p"))
        self._date_lbl.setText(f"{n.strftime('%A, %B')} {n.day}")

    def _apply_demo_texts(self) -> None:
        self._greeting.setText("Good afternoon")
        self._temp.setText("35°C")
        self._cond.setText("Partly cloudy")
        self._meet_time.setText("10:00 AM")
        self._meet_body = (
            "One Piece UI Development Discussion — planning session for kiosk surfaces"
        )
        self._more_lbl.setText("+2 more")
        self._meet_title.setText(f"{self.PREFIX}{self._meet_body}")

    def set_weather(self, temp: str, cond: str) -> None:
        self._temp.setText(temp)
        self._cond.setText(cond)

    def set_next_meeting(self, time_s: str, title: str, more: str = "") -> None:
        self._meet_time.setText(time_s)
        self._meet_body = title
        self._more_lbl.setText(more)
        self._meet_title.setText(f"{self.PREFIX}{self._meet_body}")
        self._elide_meeting_title()
