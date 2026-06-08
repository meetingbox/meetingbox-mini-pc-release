import 'package:flutter/material.dart';

/// Palette ported 1:1 from `device-ui/src/config.py` COLORS plus the Figma
/// constants used by the home / recording / processing / summary layouts.
abstract final class AppColors {
  // Primary blue gradient endpoints
  static const primaryStart = Color(0xFF3888FA); // #3888FA bright blue
  static const primaryEnd = Color(0xFF2273F5); // #2273F5 deep blue
  static const blueBright = primaryStart;
  static const blueDeep = primaryEnd;

  // iOS-style status colors
  static const green = Color(0xFF34C759);
  static const red = Color(0xFFFF453A);
  static const yellow = Color(0xFFFFD60A);
  static const blue = Color(0xFF3888FA);

  // Surfaces
  static const background = Color(0xFF1C1C1E);
  static const surface = Color(0xFF2C2C2E);
  static const surfaceLight = Color(0xFF38383A);
  static const black = Color(0xFF000000);

  // Neutrals
  static const white = Color(0xFFFFFFFF);
  static const gray300 = Color(0xFFC7C7CC);
  static const gray400 = Color(0xFFAEAEB2);
  static const gray500 = Color(0xFF8E8E93);
  static const gray600 = Color(0xFF6E6E73);
  static const gray700 = Color(0xFF545458);
  static const gray800 = Color(0xFF3A3A3C);
  static const gray900 = Color(0xFF111214);

  // Shadows / overlays
  static const shadow = Color(0x4D000000); // black 0.30
  static const shadowLight = Color(0x26000000); // black 0.15
  static const overlay = Color(0x80000000); // black 0.50
  static const overlayRed = Color(0x804C0000); // (0.3,0,0,0.5)

  // Border
  static const border = Color(0x1AFFFFFF); // white 0.10

  // ---- Figma device-screen specific (home / recording / processing) ----
  static const screenBg = Color(0xFF01081A); // #01081A appliance bg
  static const welcomeBg = Color(0xFF0B0D11);
  static const muted = Color(0xFFB6BAF2); // #B6BAF2
  static const deviceBlue = Color(0xFF006BF9); // #006BF9
  static const blue2 = Color(0xFF3481F1); // next-up section
  static const grey = Color(0xFFA4A4AC); // section headers

  // Card gradients / borders (home.py)
  static const cardTop = Color(0xFF011137);
  static const cardBottom = Color(0xFF000A26);
  static const cardBorder = Color(0xFF232942);
  static const heroBg = Color(0xFF010C25);
  static const rowBg = Color(0xFF010B26);
  static const rowBorder = Color(0xFF1B2336);
  static const recTop = Color(0xFF0038B6);
  static const recBottom = Color(0xFF002376);

  // make_dark_bg() base + glows
  static const darkBase = Color(0xFF090D16); // (0.035,0.050,0.085)
  static const glowBlue = Color(0x3319579B); // (0.10,0.34,0.70,0.20)
  static const glowViolet = Color(0x1F8552EB); // (0.52,0.32,0.92,0.12)

  // Glass card (attach_card_bg default)
  static const glassFill = Color(0xD11F2A3B); // (0.12,0.16,0.23,0.82)
}
