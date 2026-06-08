import 'package:meetingbox_device_ui/config/platform_env.dart';

/// Runtime configuration — mirrors `device-ui/src/config.py` env vars.
class AppConfig {
  AppConfig({
    required this.backendUrl,
    required this.backendWsUrl,
    required this.deviceBridgeUrl,
    required this.displayWidth,
    required this.displayHeight,
    required this.fullscreen,
    required this.mockBackend,
    required this.dashboardUrl,
    this.deviceAuthToken = '',
  });

  final String backendUrl;
  final String backendWsUrl;
  final String deviceBridgeUrl;
  final int displayWidth;
  final int displayHeight;
  final bool fullscreen;
  final bool mockBackend;
  final String dashboardUrl;
  final String deviceAuthToken;

  static const splashDuration = Duration(seconds: 2);

  /// Load from process env (launcher/systemd) with `--dart-define` fallback.
  factory AppConfig.fromEnvironment() {
    String env(String key, {required String defaultValue}) {
      final runtime = readPlatformEnv(key)?.trim();
      if (runtime != null && runtime.isNotEmpty) return runtime;
      return String.fromEnvironment(key, defaultValue: defaultValue);
    }

    bool envBool(String key, {required String defaultValue}) {
      return env(key, defaultValue: defaultValue) == '1';
    }

    int envInt(String key, {required String defaultValue}) {
      return int.tryParse(env(key, defaultValue: defaultValue)) ??
          int.parse(defaultValue);
    }

    String stripApi(String url) {
      final u = url.trim().replaceAll(RegExp(r'/+$'), '');
      if (u.toLowerCase().endsWith('/api')) {
        return u.substring(0, u.length - 4).replaceAll(RegExp(r'/+$'), '');
      }
      return u;
    }

    String deriveWs(String httpUrl) {
      final u = httpUrl.trim().replaceAll(RegExp(r'/+$'), '');
      if (u.startsWith('https://')) return 'wss://${u.substring(8)}/ws';
      if (u.startsWith('http://')) return 'ws://${u.substring(7)}/ws';
      return 'ws://localhost:8000/ws';
    }

    final backend = stripApi(
      env('BACKEND_URL', defaultValue: 'http://localhost:8000'),
    );
    final wsEnv = env('BACKEND_WS_URL', defaultValue: '');
    final ws = wsEnv.isNotEmpty ? wsEnv : deriveWs(backend);

    return AppConfig(
      backendUrl: backend,
      backendWsUrl: ws,
      deviceBridgeUrl: env('DEVICE_BRIDGE_URL', defaultValue: 'http://127.0.0.1:8765'),
      displayWidth: envInt('DISPLAY_WIDTH', defaultValue: '1260'),
      displayHeight: envInt('DISPLAY_HEIGHT', defaultValue: '800'),
      fullscreen: envBool('FULLSCREEN', defaultValue: '0'),
      mockBackend: envBool('MOCK_BACKEND', defaultValue: '0'),
      dashboardUrl: env('DASHBOARD_PUBLIC_URL', defaultValue: 'http://meetingbox.local'),
      deviceAuthToken: env('DEVICE_AUTH_TOKEN', defaultValue: ''),
    );
  }
}
