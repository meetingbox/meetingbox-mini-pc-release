import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/app.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();
  runApp(MeetingBoxDeviceApp(config: config));
}
