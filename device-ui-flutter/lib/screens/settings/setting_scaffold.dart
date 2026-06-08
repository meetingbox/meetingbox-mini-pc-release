import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Common chrome for every settings sub-screen: dark background, back-titled
/// status bar, and a padded content area. Mirrors the Kivy settings sub-screen
/// layout (`screens/settings.py` + base screen background).
class SettingScaffold extends StatelessWidget {
  const SettingScaffold({
    super.key,
    required this.title,
    required this.child,
  });

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DeviceBackground(
        child: SafeArea(
          child: Column(
            children: [
              StatusBar(
                deviceName: title,
                backButton: true,
                showSettings: false,
                onBack: () =>
                    context.canPop() ? context.pop() : context.go('/settings'),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(Spacing.screenPadding),
                  child: child,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
