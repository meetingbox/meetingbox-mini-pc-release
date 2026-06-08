import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';

/// Forget saved WiFi networks, ported from the Kivy `wifi_forget_screen`.
class WifiForgetScreen extends StatefulWidget {
  const WifiForgetScreen({super.key, required this.bridge});

  final DeviceBridgeClient bridge;

  @override
  State<WifiForgetScreen> createState() => _WifiForgetScreenState();
}

class _WifiForgetScreenState extends State<WifiForgetScreen> {
  List<String> _saved = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final s = await widget.bridge.wifiStatus();
      if (mounted) {
        setState(() {
          _saved = (s['saved'] as List? ?? []).cast<String>();
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          _loading = false;
        });
      }
    }
  }

  Future<void> _forget(String ssid) async {
    try {
      await widget.bridge.forgetWifi(ssid);
      setState(() => _saved.remove(ssid));
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: 'Saved networks',
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Text(_error!, style: const TextStyle(color: AppColors.red))
              : _saved.isEmpty
                  ? const Text('No saved networks.',
                      style: TextStyle(color: AppColors.gray500))
                  : ListView.separated(
                      itemCount: _saved.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (_, i) {
                        final ssid = _saved[i];
                        return Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 18, vertical: 12),
                          decoration: BoxDecoration(
                            color: const Color(0xDB1F2A3B),
                            borderRadius:
                                BorderRadius.circular(Layout.borderRadius),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(ssid,
                                    style: const TextStyle(
                                        color: AppColors.white, fontSize: 15)),
                              ),
                              TextButton(
                                onPressed: () => _forget(ssid),
                                child: const Text('Forget',
                                    style: TextStyle(color: AppColors.red)),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
    );
  }
}
