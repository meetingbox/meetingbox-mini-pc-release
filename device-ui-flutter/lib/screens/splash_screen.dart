import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/setup_state.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({
    super.key,
    required this.config,
    required this.api,
    required this.setupState,
  });

  final AppConfig config;
  final ApiClient api;
  final SetupState setupState;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fade;

  @override
  void initState() {
    super.initState();
    _fade = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    )..forward();
    _scheduleAdvance();
  }

  Future<void> _scheduleAdvance() async {
    await Future<void>.delayed(AppConfig.splashDuration);
    if (!mounted) return;

    var needSetup = await widget.setupState.needsSetup();

    if (!widget.config.mockBackend) {
      try {
        final info = await widget.api.getSystemInfo();
        final serverFlag = info['setup_complete'];
        if (serverFlag == false) {
          await widget.setupState.clearLocalMarkers();
          needSetup = true;
        } else if (serverFlag == true) {
          needSetup = false;
        }
      } catch (_) {}
    } else {
      needSetup = await widget.setupState.needsSetup();
    }

    if (!mounted) return;
    context.go(needSetup ? '/welcome' : '/home');
  }

  @override
  void dispose() {
    _fade.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.black,
      body: Center(
        child: FadeTransition(
          opacity: _fade,
          child: const Text(
            'MeetingBox AI',
            style: TextStyle(
              color: AppColors.white,
              fontSize: 36,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.5,
            ),
          ),
        ),
      ),
    );
  }
}
