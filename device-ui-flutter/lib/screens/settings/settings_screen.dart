import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/settings_item.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Device settings hub, ported from `screens/settings.py`. Sections and rows
/// mirror the Kivy ordering: DEVICE, NETWORK, STORAGE, SYSTEM, PRIVACY,
/// DISPLAY, AUDIO, MAINTENANCE, SUPPORT. Hardware toggles call the local
/// bridge; app-level toggles persist to shared preferences.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.config,
    required this.api,
    required this.bridge,
  });

  final AppConfig config;
  final ApiClient api;
  final DeviceBridgeClient bridge;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  SharedPreferences? _prefs;
  Map<String, dynamic> _info = {};

  bool _wifiRadio = true;
  bool _bluetooth = false;

  // App-level toggles (persisted locally).
  final Map<String, bool> _toggles = {
    'auto_update': true,
    'privacy': true,
    'auto_record': false,
    'auto_summarize': true,
    'save_transcripts': true,
    'consent_reminder': true,
  };

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    _prefs = await SharedPreferences.getInstance();
    for (final k in _toggles.keys.toList()) {
      _toggles[k] = _prefs?.getBool('set_$k') ?? _toggles[k]!;
    }
    if (mounted) setState(() {});
    _loadInfo();
    _loadRadios();
  }

  Future<void> _loadInfo() async {
    if (widget.config.mockBackend) return;
    try {
      final info = await widget.api.getSystemInfo();
      if (mounted) setState(() => _info = info);
    } catch (_) {}
  }

  Future<void> _loadRadios() async {
    try {
      final w = await widget.bridge.wifiStatus();
      if (mounted) setState(() => _wifiRadio = w['radio_on'] != false);
    } catch (_) {}
    try {
      final b = await widget.bridge.bluetoothStatus();
      if (mounted) setState(() => _bluetooth = b['power_on'] == true);
    } catch (_) {}
  }

  Future<void> _setToggle(String key, bool v) async {
    setState(() => _toggles[key] = v);
    await _prefs?.setBool('set_$key', v);
  }

  String _infoStr(String key, String fallback) =>
      (_info[key] ?? fallback).toString();

  void _go(String path) => context.push(path);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DeviceBackground(
        child: SafeArea(
          child: Column(
            children: [
              StatusBar(
                deviceName: 'Settings',
                backButton: true,
                showSettings: false,
                onBack: () =>
                    context.canPop() ? context.pop() : context.go('/home'),
              ),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(Spacing.screenPadding),
                  children: [
                    _section('DEVICE'),
                    SettingsItem(
                      title: 'Device Name',
                      subtitle: _infoStr('device_name', 'MeetingBox'),
                      onPressed: () => _go('/settings/device-name'),
                    ),
                    SettingsItem(
                      title: 'Model / Serial',
                      subtitle: _infoStr('model', 'MeetingBox'),
                      mode: SettingsItemMode.info,
                    ),
                    SettingsItem(
                      title: 'Room / Location',
                      onPressed: () => _go('/settings/room-label'),
                    ),
                    _section('ACCOUNT'),
                    SettingsItem(
                      title: 'Pair / link account',
                      subtitle:
                          'Enter a pairing code to link this device to your account',
                      onPressed: () => _go('/pair-device'),
                    ),
                    _section('NETWORK'),
                    SettingsItem(
                      title: 'WiFi',
                      mode: SettingsItemMode.toggle,
                      active: _wifiRadio,
                      onToggle: (v) async {
                        setState(() => _wifiRadio = v);
                        try {
                          await widget.bridge.setWifiRadio(v);
                        } catch (_) {}
                      },
                    ),
                    SettingsItem(
                      title: 'WiFi network',
                      subtitle: _infoStr('wifi_ssid', 'Not connected'),
                      onPressed: () => _go('/settings/wifi'),
                    ),
                    SettingsItem(
                      title: 'Forget saved networks',
                      onPressed: () => _go('/settings/wifi-forget'),
                    ),
                    SettingsItem(
                      title: 'Bluetooth',
                      mode: SettingsItemMode.toggle,
                      active: _bluetooth,
                      onToggle: (v) async {
                        setState(() => _bluetooth = v);
                        try {
                          await widget.bridge.setBluetoothPower(v);
                        } catch (_) {}
                      },
                    ),
                    SettingsItem(
                      title: 'Bluetooth devices',
                      subtitle: 'Scan, pair & manage',
                      onPressed: () => _go('/settings/bluetooth'),
                    ),
                    _section('STORAGE'),
                    SettingsItem(
                      title: 'Storage',
                      subtitle: _infoStr('storage', 'Available'),
                      mode: SettingsItemMode.info,
                    ),
                    SettingsItem(
                      title: 'Auto-delete old meetings',
                      subtitle: _prefs?.getString('set_auto_delete') ?? 'Never',
                      onPressed: () => _go('/settings/auto-delete'),
                    ),
                    SettingsItem(
                      title: 'Storage breakdown',
                      subtitle: 'Recordings · transcripts · cache',
                      onPressed: () => _go('/settings/storage-breakdown'),
                    ),
                    _section('SYSTEM'),
                    SettingsItem(
                      title: 'Firmware Version',
                      subtitle: _infoStr('firmware', '1.0.0'),
                      mode: SettingsItemMode.info,
                    ),
                    SettingsItem(
                      title: 'Check for Updates',
                      onPressed: () => _go('/settings/update-check'),
                    ),
                    SettingsItem(
                      title: 'Auto-update',
                      subtitle: 'Keep firmware up to date automatically',
                      mode: SettingsItemMode.toggle,
                      active: _toggles['auto_update']!,
                      onToggle: (v) => _setToggle('auto_update', v),
                    ),
                    SettingsItem(
                      title: 'Update channel',
                      subtitle: _prefs?.getString('set_update_channel') ?? 'Stable',
                      onPressed: () => _go('/settings/update-channel'),
                    ),
                    SettingsItem(
                      title: 'Date & Time',
                      onPressed: () => _go('/settings/datetime'),
                    ),
                    SettingsItem(
                      title: 'Timezone',
                      subtitle: _prefs?.getString('set_timezone') ?? '',
                      onPressed: () => _go('/settings/timezone'),
                    ),
                    SettingsItem(
                      title: 'Diagnostic logs',
                      subtitle: 'View system log output',
                      onPressed: () => _go('/settings/diagnostics'),
                    ),
                    _section('PRIVACY'),
                    SettingsItem(
                      title: 'Privacy Mode',
                      subtitle: 'All processing happens locally',
                      mode: SettingsItemMode.toggle,
                      active: _toggles['privacy']!,
                      onToggle: (v) => _setToggle('privacy', v),
                    ),
                    SettingsItem(
                      title: 'Auto-start from calendar',
                      subtitle: 'Start recording when a meeting is scheduled',
                      mode: SettingsItemMode.toggle,
                      active: _toggles['auto_record']!,
                      onToggle: (v) => _setToggle('auto_record', v),
                    ),
                    SettingsItem(
                      title: 'Auto-summarize meetings',
                      subtitle: 'Generate summary after each recording',
                      mode: SettingsItemMode.toggle,
                      active: _toggles['auto_summarize']!,
                      onToggle: (v) => _setToggle('auto_summarize', v),
                    ),
                    SettingsItem(
                      title: 'Save transcripts',
                      subtitle: 'Store transcript text on device',
                      mode: SettingsItemMode.toggle,
                      active: _toggles['save_transcripts']!,
                      onToggle: (v) => _setToggle('save_transcripts', v),
                    ),
                    SettingsItem(
                      title: 'Recording consent reminder',
                      subtitle: 'Show reminder when recording starts',
                      mode: SettingsItemMode.toggle,
                      active: _toggles['consent_reminder']!,
                      onToggle: (v) => _setToggle('consent_reminder', v),
                    ),
                    _section('DISPLAY'),
                    SettingsItem(
                      title: 'Brightness',
                      onPressed: () => _go('/settings/brightness'),
                    ),
                    SettingsItem(
                      title: 'Idle timeout',
                      subtitle: _prefs?.getString('set_idle_timeout') ?? '5 minutes',
                      onPressed: () => _go('/settings/idle-timeout'),
                    ),
                    _section('AUDIO'),
                    SettingsItem(
                      title: 'Speech volume',
                      onPressed: () => _go('/settings/speech-volume'),
                    ),
                    SettingsItem(
                      title: 'Notification volume',
                      onPressed: () => _go('/settings/notification-volume'),
                    ),
                    SettingsItem(
                      title: 'Microphone gain',
                      onPressed: () => _go('/settings/mic-gain'),
                    ),
                    SettingsItem(
                      title: 'Audio output',
                      onPressed: () => _go('/settings/audio-output'),
                    ),
                    SettingsItem(
                      title: 'Audio input',
                      onPressed: () => _go('/settings/audio-input'),
                    ),
                    _section('MAINTENANCE'),
                    SettingsItem(
                      title: 'Connectivity check',
                      onPressed: () => _go('/settings/connectivity'),
                    ),
                    SettingsItem(
                      title: 'USB devices',
                      onPressed: () => _go('/settings/usb'),
                    ),
                    SettingsItem(
                      title: 'Restart device',
                      subtitle: 'Reboot the MeetingBox',
                      onPressed: _confirmReboot,
                    ),
                    _section('SUPPORT'),
                    SettingsItem(
                      title: 'About',
                      onPressed: () => _go('/settings/about'),
                    ),
                    SettingsItem(
                      title: 'Send feedback',
                      onPressed: () => _go('/settings/feedback'),
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _confirmReboot() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Restart device?',
            style: TextStyle(color: AppColors.white)),
        content: const Text('The MeetingBox will reboot now.',
            style: TextStyle(color: AppColors.gray300)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Restart')),
        ],
      ),
    );
    if (ok == true) {
      try {
        await widget.bridge.powerAction('reboot');
      } catch (_) {}
    }
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8, left: 4),
        child: Text(
          title,
          style: const TextStyle(
            color: AppColors.gray400,
            fontSize: FontSizes.small,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.4,
          ),
        ),
      );
}
