/// Design tokens ported from `device-ui/src/config.py`.
///
/// Font sizes, button/spacing presets, radii, layout constants, and animation
/// timings live here so screens reference shared values instead of magic
/// numbers — matching the Kivy `FONT_SIZES`, `SPACING`, etc.
abstract final class FontSizes {
  static const double huge = 32; // timer, large numbers
  static const double large = 22; // titles, primary buttons
  static const double title = 20; // settings title
  static const double medium = 17; // body text, standard buttons
  static const double body = 16; // regular body text
  static const double small = 13; // secondary text, captions
  static const double tiny = 11; // footer, helper text
}

abstract final class ButtonSizes {
  static const primary = (240.0, 60.0);
  static const secondary = (180.0, 60.0);
  static const small = (140.0, 50.0);
}

abstract final class Spacing {
  static const double screenPadding = 16;
  static const double buttonSpacing = 12;
  static const double sectionSpacing = 20;
  static const double listItemSpacing = 8;
}

abstract final class Layout {
  static const double borderRadius = 14;
  static const double statusBarHeight = 44;
  static const double footerHeight = 20;
  static const double contentPaddingH = 16;
  static const double contentPaddingV = 12;
}

abstract final class Motion {
  static const fast = Duration(milliseconds: 150);
  static const normal = Duration(milliseconds: 300);
  static const slow = Duration(milliseconds: 500);

  // Boot flow timings
  static const splash = Duration(milliseconds: 2000);
  static const allSet = Duration(seconds: 10);
  static const autoReturn = Duration(seconds: 5);
}

abstract final class FontFamilies {
  static const sans = 'AstaSans';
}
