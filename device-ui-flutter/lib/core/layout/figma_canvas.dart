import 'package:flutter/widgets.dart';

/// Shared Figma coordinate system used by the device screens.
///
/// The Kivy UI is authored on a fixed 1260×800 canvas (see
/// `frame19_layout.py`, `processing_layout.py`, `summary_layout.py`,
/// `home.py`). Layers are positioned with absolute pixel coordinates and the
/// whole canvas is scaled to the panel with `min(sw/cw, sh/ch)` so the design
/// proportions survive on any display. This file reproduces that math in Dart.
const double kCanvasW = 1260.0;
const double kCanvasH = 800.0;

/// A rectangle in absolute Figma pixels measured from the top-left of the
/// 1260×800 canvas.
@immutable
class FigmaBox {
  const FigmaBox(this.x, this.yTop, this.w, this.h);

  /// Build a box from a ratio box (`x`, `y_top`, `w`, `h` as 0..1 fractions)
  /// matching the Python `canvas_box()` helper output.
  factory FigmaBox.fromRatio({
    required double x,
    required double yTop,
    required double w,
    required double h,
  }) =>
      FigmaBox(x * kCanvasW, yTop * kCanvasH, w * kCanvasW, h * kCanvasH);

  final double x;
  final double yTop;
  final double w;
  final double h;

  double get right => x + w;
  double get bottom => yTop + h;
  double get centerX => x + w / 2;
  double get centerY => yTop + h / 2;
}

/// Maps Figma px to device px for the current scaled canvas.
class FigmaScale {
  const FigmaScale(this.scale);

  /// Aspect-preserving scale for a viewport, mirroring `scaled_canvas()`.
  factory FigmaScale.forSize(Size size, {double canvasW = kCanvasW, double canvasH = kCanvasH}) {
    if (size.width <= 0 || size.height <= 0) return const FigmaScale(1);
    return FigmaScale((size.width / canvasW).clamp(0.0, double.infinity) <
            (size.height / canvasH)
        ? size.width / canvasW
        : size.height / canvasH);
  }

  final double scale;

  double px(double v) => v * scale;

  /// Font size for a Figma `fs_ratio` (`px / CANVAS_H`) at the scaled canvas
  /// height, mirroring `font_px()`.
  double font(double fsRatio, {double minPx = 10, double maxPx = 96}) {
    final raw = fsRatio * kCanvasH * scale;
    return raw.clamp(minPx, maxPx);
  }
}

/// Lays children out on a centered, aspect-preserved 1260×800 canvas.
///
/// Pass [FigmaChild]ren with absolute boxes; the canvas scales and positions
/// them exactly like the Kivy `pos_hint`/`size_hint` layout.
class FigmaCanvas extends StatelessWidget {
  const FigmaCanvas({
    super.key,
    required this.children,
    this.background,
    this.canvasW = kCanvasW,
    this.canvasH = kCanvasH,
    this.clip = true,
  });

  final List<FigmaChild> children;
  final Color? background;
  final double canvasW;
  final double canvasH;
  final bool clip;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        final scale = FigmaScale.forSize(size, canvasW: canvasW, canvasH: canvasH).scale;
        final canvas = SizedBox(
          width: canvasW * scale,
          height: canvasH * scale,
          child: Stack(
            clipBehavior: clip ? Clip.hardEdge : Clip.none,
            children: [
              for (final child in children)
                Positioned(
                  left: child.box.x * scale,
                  top: child.box.yTop * scale,
                  width: child.box.w * scale,
                  height: child.box.h * scale,
                  child: child.builder(context, FigmaScale(scale)),
                ),
            ],
          ),
        );
        return Container(
          color: background,
          alignment: Alignment.center,
          child: canvas,
        );
      },
    );
  }
}

/// A child placed at a [FigmaBox]. The builder receives the active scale so it
/// can size its own fonts/strokes consistently.
class FigmaChild {
  const FigmaChild(this.box, this.builder);

  /// Convenience for a static widget that does not need the scale.
  FigmaChild.widget(this.box, Widget child)
      : builder = ((_, __) => child);

  final FigmaBox box;
  final Widget Function(BuildContext context, FigmaScale scale) builder;
}
