import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';

/// Premium appliance background ported from `BaseScreen.make_dark_bg()`:
/// a deep navy base with two soft blue/violet radial glows in the top-left
/// and bottom-right corners. Used as the global page background.
class DeviceBackground extends StatelessWidget {
  const DeviceBackground({super.key, this.child});

  final Widget? child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        const ColoredBox(color: AppColors.darkBase),
        // Top-left blue glow
        const Positioned(
          left: -80,
          top: -60,
          child: _Glow(
            size: 360,
            color: Color(0x3319579B),
          ),
        ),
        // Bottom-right violet glow
        const Positioned(
          right: -120,
          bottom: -140,
          child: _Glow(
            size: 420,
            color: Color(0x1F8552EB),
          ),
        ),
        if (child != null) child!,
      ],
    );
  }
}

class _Glow extends StatelessWidget {
  const _Glow({required this.size, required this.color});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [color, color.withValues(alpha: 0)],
        ),
      ),
    );
  }
}
