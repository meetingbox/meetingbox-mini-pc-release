import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';

/// Meeting Summary layout tokens.
/// Ported from `device-ui/src/summary_layout.py`. Canvas 1260×800.
/// This screen is a light theme (#F2F2F7).
abstract final class SummaryLayout {
  // Topbar
  static const topbar = FigmaBox(0.0, 0.0, 1260.0, 56.0);
  static const backBtn = FigmaBox(24.0, 10.0, 36.0, 36.0);
  static const pageTitle = FigmaBox(72.0, 14.0, 360.0, 30.0);
  static const double pageTitleFsRatio = 22.0 / kCanvasH;
  static const topExport = FigmaBox(1030.0, 10.0, 96.0, 36.0);
  static const topShare = FigmaBox(1134.0, 10.0, 96.0, 36.0);

  // Recording card
  static const metaCard = FigmaBox(0.0, 56.0, 1260.0, 92.0);
  static const double _mx = 24.0;
  static const double _my = 78.0;
  static const metaFileIcon = FigmaBox(_mx, _my, 48.0, 48.0);
  static const metaTitle = FigmaBox(_mx + 64.0, _my + 2.0, 620.0, 24.0);
  static const metaDate = FigmaBox(_mx + 64.0, _my + 26.0, 620.0, 20.0);
  static const metaParticipants = FigmaBox(_mx + 900.0, _my + 4.0, 332.0, 40.0);
  static const double metaTitleFsRatio = 17.0 / kCanvasH;
  static const double metaDateFsRatio = 15.0 / kCanvasH;

  // Sidebar
  static const sidebarCard = FigmaBox(24.0, 168.0, 200.0, 580.0);
  static const double _sx = 24.0;
  static const double _sy = 168.0;
  static const double _tabXOffset = 8.0;
  static const double _tabYOffset = 8.0;
  static const double _tabW = 184.0;
  static const double _tabH = 40.0;
  static const double _tabGap = 4.0;

  static FigmaBox tab(int i) => FigmaBox(
        _sx + _tabXOffset,
        _sy + _tabYOffset + i * (_tabH + _tabGap),
        _tabW,
        _tabH,
      );

  static final tabOverview = tab(0);
  static final tabActionItems = tab(1);
  static final tabKeyPoints = tab(2);
  static final tabDecisions = tab(3);
  static final tabTranscript = tab(4);
  static final tabParticipants = tab(5);
  static const double tabFsRatio = 15.0 / kCanvasH;

  // Content area
  static const contentArea = FigmaBox(240.0, 168.0, 996.0, 580.0);
  static const double _cx = 240.0;
  static const double _cy = 168.0;
  static const double _cw = 996.0;
  static const double _ch = 580.0;
  static const double ovGap = 12.0;

  static const ovAiCard = FigmaBox(_cx, _cy, _cw, 140.0);
  static const ovKeyCard = FigmaBox(_cx, _cy + 140.0 + ovGap, _cw, 158.0);

  static const double _r3y = _cy + 140.0 + ovGap + 158.0 + ovGap;
  static const double _r3h = _ch - (_r3y - _cy);
  static const double _r3HalfW = (_cw - ovGap) / 2;
  static const ovActionsCard = FigmaBox(_cx, _r3y, _r3HalfW, _r3h);
  static const ovDecisionsCard =
      FigmaBox(_cx + _r3HalfW + ovGap, _r3y, _r3HalfW, _r3h);

  static const fullTabCard = FigmaBox(_cx, _cy, _cw, _ch);

  // Footer
  static const footerLeft = FigmaBox(24.0, 764.0, 540.0, 20.0);
  static const footerRight = FigmaBox(924.0, 764.0, 312.0, 20.0);
  static const double footerFsRatio = 12.0 / kCanvasH;

  // Typography
  static const double sectionTitleFsRatio = 13.0 / kCanvasH;
  static const double sectionBodyFsRatio = 15.0 / kCanvasH;
  static const double sectionHintFsRatio = 12.0 / kCanvasH;

  // Colours
  static const bg = Color(0xFFF2F2F7);
  static const cardFill = Color(0xFFFFFFFF);
  static const cardBorder = Color(0xFFE5E5EA);
  static const double cardRadius = 16.0;
  static const sidebarFill = Color(0xFFFFFFFF);
  static const sidebarBorder = Color(0xFFE5E5EA);
  static const tabActiveFill = Color(0x1A007AFF);
  static const tabActiveBorder = Color(0x59007AFF);
  static const double tabActiveRadius = 10.0;
  static const progTrackFill = Color(0xFFE5E5EA);
  static const progFill = Color(0xFF007AFF);
  static const double progRadius = 4.0;
  static const accentBlue = Color(0xFF007AFF);
  static const colWhite = Color(0xFF1C1C1E);
  static const colMuted = Color(0xFF1C1C1E);
  static const colHint = Color(0xFF8E8E93);
  static const colAccent = accentBlue;

  static const double contentPadX = 28.0;
  static const double contentPadTop = 24.0;
  static const double contentPadBot = 24.0;
}
