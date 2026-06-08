import 'dart:io' show Platform;

/// Linux desktop: read env vars set by the launcher / systemd unit.
String? readPlatformEnv(String key) => Platform.environment[key];
