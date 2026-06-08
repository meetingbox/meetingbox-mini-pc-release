import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_theme.dart';
import 'package:meetingbox_device_ui/routing/app_router.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/services/setup_state.dart';
import 'package:meetingbox_device_ui/services/voice_event_client.dart';
import 'package:meetingbox_device_ui/widgets/voice_overlay.dart';

class MeetingBoxDeviceApp extends StatefulWidget {
  const MeetingBoxDeviceApp({super.key, required this.config});

  final AppConfig config;

  @override
  State<MeetingBoxDeviceApp> createState() => _MeetingBoxDeviceAppState();
}

class _MeetingBoxDeviceAppState extends State<MeetingBoxDeviceApp> {
  late final ApiClient _api;
  late final DeviceBridgeClient _bridge;
  late final SetupState _setupState;
  late final OnboardingState _onboarding;
  late final VoiceEventClient _voice;
  late final GoRouterHolder _router;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(widget.config);
    _bridge = DeviceBridgeClient(widget.config);
    _setupState = SetupState();
    _onboarding = OnboardingState();
    _voice = VoiceEventClient(widget.config)..connect();
    _router = GoRouterHolder(
      createAppRouter(
        config: widget.config,
        api: _api,
        bridge: _bridge,
        setupState: _setupState,
        onboarding: _onboarding,
      ),
    );
  }

  @override
  void dispose() {
    _voice.dispose();
    _api.dispose();
    _bridge.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'MeetingBox',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark(),
      routerConfig: _router.router,
      builder: (context, child) => Stack(
        children: [
          child ?? const SizedBox.shrink(),
          VoiceOverlay(client: _voice),
        ],
      ),
    );
  }
}

/// Keeps router alive across rebuilds.
class GoRouterHolder {
  GoRouterHolder(this.router);
  final GoRouter router;
}
