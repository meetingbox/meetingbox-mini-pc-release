import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';

/// Ported from `screens/all_set.py`. Auto-advances to home after 10s or on tap.
class AllSetScreen extends StatefulWidget {
  const AllSetScreen({super.key, required this.config});

  final AppConfig config;

  @override
  State<AllSetScreen> createState() => _AllSetScreenState();
}

class _AllSetScreenState extends State<AllSetScreen> {
  @override
  void initState() {
    super.initState();
    Future<void>.delayed(Motion.allSet, _goHome);
  }

  void _goHome() {
    if (mounted) context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: GestureDetector(
        onTap: _goHome,
        child: DeviceBackground(
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.check_circle, color: AppColors.green, size: 60),
                const SizedBox(height: 12),
                const Text(
                  "You're All Set!",
                  style: TextStyle(
                    color: AppColors.white,
                    fontSize: FontSizes.large,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Create your account at:',
                  style: TextStyle(color: AppColors.gray400, fontSize: FontSizes.body),
                ),
                Text(
                  widget.config.dashboardUrl,
                  style: const TextStyle(
                    color: AppColors.blue,
                    fontSize: FontSizes.medium,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(6),
                  color: AppColors.black,
                  child: QrImageView(
                    data: widget.config.dashboardUrl,
                    size: 100,
                    backgroundColor: AppColors.black,
                    eyeStyle: const QrEyeStyle(
                        eyeShape: QrEyeShape.square, color: AppColors.white),
                    dataModuleStyle: const QrDataModuleStyle(
                        dataModuleShape: QrDataModuleShape.square,
                        color: AppColors.white),
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Tap anywhere to continue',
                  style: TextStyle(color: AppColors.gray600, fontSize: FontSizes.tiny),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
