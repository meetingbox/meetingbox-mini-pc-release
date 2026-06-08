import 'package:flutter_test/flutter_test.dart';
import 'package:meetingbox_device_ui/app.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('app boots to splash', (tester) async {
    SharedPreferences.setMockInitialValues({});

    final config = AppConfig(
      backendUrl: 'http://localhost:8000',
      backendWsUrl: 'ws://localhost:8000/ws',
      deviceBridgeUrl: 'http://127.0.0.1:8765',
      displayWidth: 1260,
      displayHeight: 800,
      fullscreen: false,
      mockBackend: true,
      dashboardUrl: 'http://meetingbox.local',
    );

    await tester.pumpWidget(MeetingBoxDeviceApp(config: config));
    await tester.pump();

    expect(find.text('MeetingBox AI'), findsOneWidget);

    // Drain the splash advance timer + fade so no timers leak at teardown.
    await tester.pump(AppConfig.splashDuration + const Duration(seconds: 1));
    await tester.pumpAndSettle();
  });
}
