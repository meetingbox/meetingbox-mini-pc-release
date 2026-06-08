import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';

enum AppButtonVariant { primary, secondary, danger }

/// Premium buttons ported from `components/button.py`:
/// - primary: blue two-tone gradient + soft shadow
/// - danger: red two-tone gradient
/// - secondary: frosted dark surface + hairline border
class AppButton extends StatefulWidget {
  const AppButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.width,
    this.height = 60,
    this.fontSize = FontSizes.medium,
  });

  const AppButton.primary({
    super.key,
    required this.label,
    required this.onPressed,
    this.width,
    this.height = 60,
    this.fontSize = FontSizes.medium,
  }) : variant = AppButtonVariant.primary;

  const AppButton.secondary({
    super.key,
    required this.label,
    required this.onPressed,
    this.width,
    this.height = 60,
    this.fontSize = FontSizes.medium,
  }) : variant = AppButtonVariant.secondary;

  const AppButton.danger({
    super.key,
    required this.label,
    required this.onPressed,
    this.width,
    this.height = 60,
    this.fontSize = FontSizes.medium,
  }) : variant = AppButtonVariant.danger;

  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final double? width;
  final double height;
  final double fontSize;

  @override
  State<AppButton> createState() => _AppButtonState();
}

class _AppButtonState extends State<AppButton> {
  bool _pressed = false;

  bool get _secondary => widget.variant == AppButtonVariant.secondary;

  (Color, Color) get _gradient => switch (widget.variant) {
        AppButtonVariant.primary => (AppColors.primaryStart, AppColors.primaryEnd),
        AppButtonVariant.danger => (const Color(0xFFFF4D42), const Color(0xFFEC3D33)),
        AppButtonVariant.secondary => (AppColors.surfaceLight, AppColors.surfaceLight),
      };

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final (start, end) = _gradient;
    final darken = _pressed ? 0.08 : 0.0;

    return Opacity(
      opacity: enabled ? 1.0 : 0.5,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _pressed = true) : null,
        onTapUp: enabled ? (_) => setState(() => _pressed = false) : null,
        onTapCancel: enabled ? () => setState(() => _pressed = false) : null,
        onTap: widget.onPressed,
        child: Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(Layout.borderRadius),
            gradient: _secondary
                ? null
                : LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [_shift(start, darken), _shift(end, darken)],
                  ),
            color: _secondary
                ? (_pressed ? AppColors.gray700 : AppColors.surfaceLight)
                : null,
            border: _secondary
                ? Border.all(color: AppColors.gray600)
                : null,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: _secondary ? 0.15 : 0.30),
                blurRadius: _secondary ? 8 : 14,
                offset: Offset(1, _secondary ? 2 : 4),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Text(
            widget.label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppColors.white,
              fontSize: widget.fontSize,
              fontWeight: _secondary ? FontWeight.w400 : FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }

  static Color _shift(Color c, double amount) {
    if (amount == 0) return c;
    return Color.fromARGB(
      (c.a * 255).round(),
      ((c.r * 255) - amount * 255).clamp(0, 255).round(),
      ((c.g * 255) - amount * 255).clamp(0, 255).round(),
      ((c.b * 255) - amount * 255).clamp(0, 255).round(),
    );
  }
}
