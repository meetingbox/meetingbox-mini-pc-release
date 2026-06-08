import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';

/// Processing screen layout — Figma `397:261`.
/// Ported from `device-ui/src/processing_layout.py`. Canvas 1260×800.
abstract final class ProcessingLayout {
  // Header
  static const backBtn = FigmaBox(24.013, 21.188, 76.278, 76.278);
  static const settingsBtn = FigmaBox(1159.708, 21.188, 76.278, 76.278);

  // "Recording complete" status row (Group 45)
  static const checkBadge = FigmaBox(100.291, 153.968, 46.614, 46.614);
  static const headlineLabel = FigmaBox(159.617, 152.555, 360.0, 44.0);
  static const titleLabel = FigmaBox(159.617, 199.170, 560.0, 34.0);
  static const dotSeparator = FigmaBox(728.900, 216.120, 5.65, 5.65);
  static const durationLabel = FigmaBox(750.088, 199.170, 140.0, 34.0);

  // Centre orb (left half)
  static const double _ringOriginX = 146.906;
  static const double _ringOriginY = 292.399;
  static const double _ringSize = 298.049;
  static const double _haloSize = _ringSize * 1.6;

  static const glowOuter = FigmaBox(
    _ringOriginX - (_haloSize - _ringSize) / 2.0,
    _ringOriginY - (_haloSize - _ringSize) / 2.0,
    _haloSize,
    _haloSize,
  );
  static const ringSolid = FigmaBox(_ringOriginX, _ringOriginY, _ringSize, _ringSize);
  static const ringOuter = FigmaBox(
    _ringOriginX - _ringSize * 0.019,
    _ringOriginY,
    _ringSize * 1.038,
    _ringSize * 1.0379,
  );

  // Bottom-left captions (under orb)
  static const headlineBottom = FigmaBox(49.439, 649.776, 540.0, 44.0);
  static const subtitleBottom = FigmaBox(49.439, 707.691, 540.0, 34.0);

  // Right-side cards
  static const stepsCard = FigmaBox(577.735, 261.323, 639.888, 251.435);
  static const notifyBar = FigmaBox(569.260, 542.422, 658.251, 76.278);

  // Stage rows inside the steps card
  static const double _stageCardX = 577.735;
  static const double _stageCardY = 261.323;
  static const double _stageCardW = 639.888;
  static const double _stageCardH = 251.435;
  static const double _stagePadTop = 28.0;
  static const double _stagePadLeft = 21.0;
  static const double _stagePadRight = 28.0;
  static const double _stageIconW = 50.852;
  static const double _stageStatusW = 49.439;
  static const double _stageRowH = 51.0;
  static const double _stageRowGap =
      (_stageCardH - 2 * _stagePadTop - 3 * _stageRowH) / 2.0;
  static const double _stageLabelX = _stagePadLeft + _stageIconW + 28.0;

  /// (icon, label, status) boxes for a stage row.
  static (FigmaBox, FigmaBox, FigmaBox) stageRow(int rowIdx) {
    final yTop = _stageCardY + _stagePadTop + rowIdx * (_stageRowH + _stageRowGap);
    final icon = FigmaBox(_stageCardX + _stagePadLeft, yTop, _stageIconW, _stageRowH);
    const labelW =
        _stageCardW - _stageLabelX - _stagePadRight - _stageStatusW - 8.0;
    final label = FigmaBox(_stageCardX + _stageLabelX, yTop, labelW, _stageRowH);
    final status = FigmaBox(
      _stageCardX + _stageCardW - _stagePadRight - _stageStatusW,
      yTop + (_stageRowH - _stageStatusW) / 2.0,
      _stageStatusW,
      _stageStatusW,
    );
    return (icon, label, status);
  }

  static const double stageFsRatio = 24.0 / kCanvasH;

  // Typography
  static const double headlineFsRatio = 36.726 / kCanvasH;
  static const double titleFsRatio = 28.251 / kCanvasH;
  static const double durationFsRatio = 28.251 / kCanvasH;
  static const double subtitleFsRatio = 28.251 / kCanvasH;

  // Colours
  static const bg = Color(0xFF01081A);
  static const colWhite = Color(0xFFFFFFFF);
  static const colMuted = Color(0xFFB6BAF2);
  static const colHint = Color(0xFF9BA2B2);
  static const colBlue = Color(0xFF0095FF);
}
