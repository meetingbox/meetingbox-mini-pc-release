import 'package:shared_preferences/shared_preferences.dart';

/// Local first-boot marker — mirrors `.setup_complete` file checks in Kivy app.
class SetupState {
  static const _key = 'meetingbox.setup_complete';

  Future<bool> needsSetup() async {
    final prefs = await SharedPreferences.getInstance();
    return !(prefs.getBool(_key) ?? false);
  }

  Future<void> markSetupComplete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key, true);
  }

  Future<void> clearLocalMarkers() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
