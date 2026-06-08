import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';

/// Recording screen layout — Figma `863:626`.
/// Ported from `device-ui/src/frame19_layout.py`. Canvas 1260×800.
abstract final class Frame19Layout {
  // Frame 19 origin (centre graphic container)
  static const double _f19x = 389.0;
  static const double _f19y = 105.0;

  static FigmaBox _f19(double lx, double ly, double lw, double lh) =>
      FigmaBox(_f19x + lx, _f19y + ly, lw, lh);

  // Header (top row)
  static const backBtn = FigmaBox(24.013, 21.188, 76.278, 76.278);
  static const recDot = FigmaBox(124.305, 36.726, 19.776, 19.776);
  static const recLabel = FigmaBox(151.144, 29.663, 280.0, 34.0);
  static const startedLabel = FigmaBox(124.305, 63.564, 300.0, 25.0);

  // Frame 19 (centre graphic, 420×420 at 389,105)
  static const double _glowInsetX = 0.1671;
  static const double _glowInsetY = 0.1686;
  static const double _ringW = 219.845;
  static const double _ringH = 217.888;

  static const double ringGlowW = _ringW * (1 + 2 * _glowInsetX);
  static const double ringGlowH = _ringH * (1 + 2 * _glowInsetY);

  static final ringGlow = _f19(
    101.973 - _ringW * _glowInsetX,
    44.684 - _ringH * _glowInsetY,
    ringGlowW,
    ringGlowH,
  );
  static final ringDark = _f19(101.973, 46.664, _ringW, _ringH);
  static final ringGradient = _f19(101.973, 44.684, _ringW, _ringH);

  static final leftVec = _f19(52.0, 67.473, 36.975, 173.319);
  static final rightVec = _f19(331.030, 67.473, 36.975, 173.319);

  // Voice wavebar (Group 46)
  static final wavebar = _f19(126.951, 111.039, 168.882, 85.174);

  // Timer + status
  static final timer = _f19(89.0, 300.0, 243.0, 42.0);
  static final status = _f19(65.0, 346.0, 290.0, 34.0);

  // Bottom controls
  static const btnPause = FigmaBox(146.906, 661.727, 101.704, 101.704);
  static const stopPill = FigmaBox(285.336, 666.726, 646.951, 101.704);
  static const btnSettings = FigmaBox(969.013, 661.726, 101.704, 101.704);

  // Typography (Figma fs_ratio = px / CANVAS_H)
  static const double timerFsRatio = 35.0 / kCanvasH;
  static const double statusFsRatio = 28.251 / kCanvasH;
  static const double recLabelFsRatio = 28.251 / kCanvasH;
  static const double startedFsRatio = 21.188 / kCanvasH;

  // Colours
  static const bg = Color(0xFF01081A);
  static const colWhite = Color(0xFFFFFFFF);
  static const colMuted = Color(0xFFB6BAF2);
  static const colBlue = Color(0xFF006BF9);
  static const colRecDotRed = Color(0xFFFF3B30);
  static const colRecDotGrey = Color(0xFF828696);
  static const colGlowBlue = Color(0xFF006BF9);
}
