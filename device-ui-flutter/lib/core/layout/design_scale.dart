import 'package:flutter/widgets.dart';

/// Scales Figma coordinates (1260×800) to the current viewport.
class DesignScale {
  DesignScale(this.size, {this.figmaWidth = 1260, this.figmaHeight = 800});

  final Size size;
  final double figmaWidth;
  final double figmaHeight;

  double get scale => (size.width / figmaWidth).clamp(0.5, 2.0);

  double x(double px) => px * size.width / figmaWidth;
  double y(double px) => px * size.height / figmaHeight;
  double sp(double px) => (px * scale).clamp(8, 48);
}
