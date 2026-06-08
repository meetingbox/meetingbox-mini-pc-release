import 'dart:async';

import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';

/// Ported from `screens/setup_progress.py`. Waiting state with animated dots.
class SetupProgressScreen extends StatefulWidget {
  const SetupProgressScreen({super.key});

  @override
  State<SetupProgressScreen> createState() => _SetupProgressScreenState();
}

class _SetupProgressScreenState extends State<SetupProgressScreen> {
  int _dot = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (mounted) setState(() => _dot = (_dot + 1) % 3);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dots = List.generate(3, (i) => i == _dot ? '●' : '○').join('  ');
    return Scaffold(
      body: DeviceBackground(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Setting up your MeetingBox...',
                style: TextStyle(
                  color: AppColors.white,
                  fontSize: FontSizes.medium,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Waiting for WiFi configuration',
                style: TextStyle(color: AppColors.gray400, fontSize: FontSizes.body),
              ),
              const SizedBox(height: 24),
              Text(
                dots,
                style: const TextStyle(color: AppColors.gray500, fontSize: FontSizes.large),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
