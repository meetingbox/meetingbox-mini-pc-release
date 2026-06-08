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

  /// Load from `--dart-define` flags (set in systemd or launch script).
  factory AppConfig.fromEnvironment() {
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
      const String.fromEnvironment('BACKEND_URL', defaultValue: 'http://localhost:8000'),
    );
    const wsEnv = String.fromEnvironment('BACKEND_WS_URL', defaultValue: '');
    final ws = wsEnv.isNotEmpty ? wsEnv : deriveWs(backend);

    return AppConfig(
      backendUrl: backend,
      backendWsUrl: ws,
      deviceBridgeUrl: const String.fromEnvironment(
        'DEVICE_BRIDGE_URL',
        defaultValue: 'http://127.0.0.1:8765',
      ),
      displayWidth: int.tryParse(
            const String.fromEnvironment('DISPLAY_WIDTH', defaultValue: '1260'),
          ) ??
          1260,
      displayHeight: int.tryParse(
            const String.fromEnvironment('DISPLAY_HEIGHT', defaultValue: '800'),
          ) ??
          800,
      fullscreen: const String.fromEnvironment('FULLSCREEN', defaultValue: '0') == '1',
      mockBackend: const String.fromEnvironment('MOCK_BACKEND', defaultValue: '0') == '1',
      dashboardUrl: const String.fromEnvironment(
        'DASHBOARD_PUBLIC_URL',
        defaultValue: 'http://meetingbox.local',
      ),
      deviceAuthToken: const String.fromEnvironment('DEVICE_AUTH_TOKEN', defaultValue: ''),
    );
  }
}
