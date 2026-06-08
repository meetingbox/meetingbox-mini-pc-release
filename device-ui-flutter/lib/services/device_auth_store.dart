import 'package:meetingbox_device_ui/config/device_auth_file.dart';
import 'package:meetingbox_device_ui/config/platform_env.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persists the paired-device API token (`mbd_…`) for REST + audio capture.
/// Mirrors `device-ui/src/config.py::get_device_auth_token` / `persist_device_auth_token`.
class DeviceAuthStore {
  static const _prefsKey = 'meetingbox.device_auth_token';

  String _token = '';
  String get token => _token;

  List<String> _tokenFilePaths() {
    final paths = <String>[];
    void add(String? raw) {
      final p = raw?.trim();
      if (p != null && p.isNotEmpty && !paths.contains(p)) paths.add(p);
    }

    add(readPlatformEnv('DEVICE_AUTH_TOKEN_FILE'));
    final dataRoot = readPlatformEnv('MEETINGBOX_DATA_ROOT')?.trim();
    if (dataRoot != null && dataRoot.isNotEmpty) {
      add('$dataRoot/data/config/device_auth_token');
    }
    add('/data/config/device_auth_token');
    add('/opt/meetingbox/data/config/device_auth_token');
    return paths;
  }

  Future<void> load({String configFallback = ''}) async {
    for (final path in _tokenFilePaths()) {
      final fromFile = await readTokenFile(path);
      if (fromFile.isNotEmpty) {
        _token = fromFile;
        return;
      }
    }
    final prefs = await SharedPreferences.getInstance();
    _token = (prefs.getString(_prefsKey) ?? configFallback).trim();
  }

  Future<bool> persist(String token) async {
    final t = token.trim();
    if (t.isEmpty) return false;
    _token = t;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, t);
    var wroteFile = false;
    for (final path in _tokenFilePaths()) {
      if (await writeTokenFile(path, t)) wroteFile = true;
    }
    return wroteFile || _token.isNotEmpty;
  }

  Future<void> clear() async {
    _token = '';
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefsKey);
  }
}
