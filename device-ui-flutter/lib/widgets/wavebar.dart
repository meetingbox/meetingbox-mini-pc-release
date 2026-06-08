import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Voice waveform indicator ported from the `_Wavebar` class in
/// `screens/recording.py` (Figma Group 46). Draws [nBars] vertical rounded
/// bars that react to live mic levels fed via [WavebarController.feedLevel],
/// with a bell-shaped voice envelope and a flat hairline when silent.
class WavebarController extends ChangeNotifier {
  double _latest = 0;
  bool active = false;

  void feedLevel(double level) {
    final v = level.clamp(0.0, 1.0);
    _latest = math.max(_latest * 0.55, v);
    notifyListeners();
  }

  double consume() {
    final v = _latest;
    _latest *= 0.93;
    return v;
  }
}

class Wavebar extends StatefulWidget {
  const Wavebar({
    super.key,
    required this.controller,
    this.nBars = 21,
    this.color = const Color(0xFF006BF9),
  });

  final WavebarController controller;
  final int nBars;
  final Color color;

  @override
  State<Wavebar> createState() => _WavebarState();
}

class _WavebarState extends State<Wavebar> with SingleTickerProviderStateMixin {
  static const _silence = 0.04;
  static const _flat = 0.012;

  late final AnimationController _ticker = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 33),
  )..addStatusListener(_loop);

  late final List<double> _levels = List.filled(widget.nBars, _flat, growable: false);
  late final List<double> _jitter =
      List.generate(widget.nBars, (_) => 0.65 + math.Random().nextDouble() * 0.35);
  final _rng = math.Random();

  @override
  void initState() {
    super.initState();
    _ticker.forward();
  }

  void _loop(AnimationStatus s) {
    if (s == AnimationStatus.completed && mounted) {
      _tick();
      _ticker.forward(from: 0);
    }
  }

  void _tick() {
    final n = widget.nBars;
    final centre = (n - 1) / 2.0;
    final amp = widget.controller.consume();
    final voicePresent = widget.controller.active && amp > _silence;
    for (var i = 0; i < n; i++) {
      double target;
      if (voicePresent) {
        final d = (i - centre) / centre;
        final bell = math.max(0.0, math.cos(d * math.pi / 2.0));
        target = math.max(_flat, amp * (0.35 + 0.65 * bell) * _jitter[i]);
      } else {
        target = _flat;
      }
      _levels[i] += (target - _levels[i]) * 0.4;
    }
    if (voicePresent && _rng.nextDouble() < 0.18) {
      _jitter[_rng.nextInt(n)] = 0.55 + _rng.nextDouble() * 0.45;
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _WavebarPainter(_levels, widget.color),
      size: Size.infinite,
    );
  }
}

class _WavebarPainter extends CustomPainter {
  _WavebarPainter(this.levels, this.color);

  final List<double> levels;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final n = levels.length;
    if (n == 0 || size.width <= 0) return;
    final barW = math.max(1.0, (size.width * 0.45) / n);
    final gap = (size.width - barW * n) / math.max(1, n - 1);
    final maxH = size.height * 0.96;
    final cy = size.height / 2;
    final paint = Paint()..color = color;
    for (var i = 0; i < n; i++) {
      final barH = math.max(2.0, maxH * levels[i]);
      final x = i * (barW + gap);
      final rrect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x, cy - barH / 2, barW, barH),
        Radius.circular(barW / 2),
      );
      canvas.drawRRect(rrect, paint);
    }
  }

  @override
  bool shouldRepaint(_WavebarPainter old) => true;
}
