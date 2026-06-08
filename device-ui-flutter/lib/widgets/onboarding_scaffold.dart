import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';

/// Shared chrome for onboarding screens: appliance background + a MeetingBox
/// brand header (logo + wordmark), mirroring the Kivy onboarding screens.
class OnboardingScaffold extends StatelessWidget {
  const OnboardingScaffold({
    super.key,
    required this.child,
    this.showBrand = true,
    this.padding = const EdgeInsets.fromLTRB(24, 14, 24, 16),
  });

  final Widget child;
  final bool showBrand;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DeviceBackground(
        child: SafeArea(
          child: Padding(
            padding: padding,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (showBrand) const _BrandHeader(),
                if (showBrand) const SizedBox(height: 12),
                Expanded(child: child),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  const _BrandHeader();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Image.asset(
          'assets/welcome/LOGO.png',
          width: 30,
          height: 30,
          errorBuilder: (_, __, ___) =>
              const Icon(Icons.mic_rounded, color: AppColors.blue, size: 28),
        ),
        const SizedBox(width: 10),
        const Text(
          'MeetingBox',
          style: TextStyle(
            color: AppColors.white,
            fontSize: FontSizes.title,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

/// A rounded glass card used across onboarding screens (attach_card_bg).
class OnboardingCard extends StatelessWidget {
  const OnboardingCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
  });

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: const Color(0xE01A263D), // (0.10,0.15,0.24,0.88)
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: AppColors.border),
      ),
      child: child,
    );
  }
}
