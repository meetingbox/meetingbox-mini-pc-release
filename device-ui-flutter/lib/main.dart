import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/app.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/services/device_auth_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();
  final authStore = DeviceAuthStore();
  await authStore.load(configFallback: config.deviceAuthToken);
  runApp(MeetingBoxDeviceApp(config: config, authStore: authStore));
}
