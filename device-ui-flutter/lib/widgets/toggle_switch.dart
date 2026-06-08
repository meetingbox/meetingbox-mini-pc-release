import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';

/// iOS-style toggle, ported from `components/toggle_switch.py`.
class ToggleSwitch extends StatelessWidget {
  const ToggleSwitch({
    super.key,
    required this.active,
    this.onToggle,
    this.width = 52,
    this.height = 30,
  });

  final bool active;
  final ValueChanged<bool>? onToggle;
  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    final knobD = height - 4;
    return GestureDetector(
      onTap: onToggle == null ? null : () => onToggle!(!active),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: active ? AppColors.blue : AppColors.gray700,
          borderRadius: BorderRadius.circular(height / 2),
        ),
        child: Stack(
          children: [
            AnimatedAlign(
              duration: const Duration(milliseconds: 150),
              alignment: active ? Alignment.centerRight : Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.all(2),
                child: Container(
                  width: knobD,
                  height: knobD,
                  decoration: const BoxDecoration(
                    color: AppColors.white,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
