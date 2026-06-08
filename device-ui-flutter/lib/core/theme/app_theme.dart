import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';

abstract final class AppTheme {
  static ThemeData dark() {
    const base = TextTheme(
      headlineLarge: TextStyle(
        fontSize: FontSizes.huge,
        fontWeight: FontWeight.w700,
        color: AppColors.white,
        letterSpacing: -0.5,
      ),
      headlineMedium: TextStyle(
        fontSize: FontSizes.large,
        fontWeight: FontWeight.w600,
        color: AppColors.white,
      ),
      titleLarge: TextStyle(
        fontSize: FontSizes.title,
        fontWeight: FontWeight.w600,
        color: AppColors.white,
      ),
      titleMedium: TextStyle(
        fontSize: FontSizes.medium,
        fontWeight: FontWeight.w500,
        color: AppColors.white,
      ),
      bodyMedium: TextStyle(
        fontSize: FontSizes.body,
        color: AppColors.muted,
      ),
      labelSmall: TextStyle(
        fontSize: FontSizes.tiny,
        color: AppColors.muted,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: FontFamilies.sans,
      scaffoldBackgroundColor: AppColors.welcomeBg,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.blue,
        surface: AppColors.surface,
        onSurface: AppColors.white,
      ),
      textTheme: base,
      splashFactory: InkRipple.splashFactory,
    );
  }
}
