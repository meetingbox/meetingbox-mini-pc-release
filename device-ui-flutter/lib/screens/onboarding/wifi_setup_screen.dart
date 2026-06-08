import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';
import 'package:meetingbox_device_ui/widgets/modal_dialog.dart';
import 'package:meetingbox_device_ui/widgets/onboarding_scaffold.dart';
import 'package:meetingbox_device_ui/widgets/wifi_network_item.dart';

/// Ported from `screens/wifi_setup.py` + `wifi_figma_ui.py` (behavioral parity:
/// scan networks via the device bridge, pick one, enter a password, connect).
class WifiSetupScreen extends StatefulWidget {
  const WifiSetupScreen({
    super.key,
    required this.config,
    required this.bridge,
    required this.onboarding,
  });

  final AppConfig config;
  final DeviceBridgeClient bridge;
  final OnboardingState onboarding;

  @override
  State<WifiSetupScreen> createState() => _WifiSetupScreenState();
}

class _WifiSetupScreenState extends State<WifiSetupScreen> {
  List<Map<String, dynamic>> _networks = [];
  bool _scanning = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _scan();
  }

  Future<void> _scan() async {
    setState(() {
      _scanning = true;
      _error = null;
    });
    try {
      if (widget.config.mockBackend) {
        await Future<void>.delayed(const Duration(milliseconds: 600));
        _networks = [
          {'ssid': 'Office WiFi', 'signal_strength': 88, 'connected': false, 'secure': true},
          {'ssid': 'Guest Network', 'signal_strength': 64, 'connected': false, 'secure': true},
          {'ssid': 'Conference 5G', 'signal_strength': 42, 'connected': false, 'secure': false},
        ];
      } else {
        _networks = await widget.bridge.scanWifi();
      }
    } catch (e) {
      _error = 'Could not scan for networks. Is the device bridge running?';
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  Future<void> _connect(Map<String, dynamic> net) async {
    final ssid = (net['ssid'] ?? '').toString();
    if (ssid.isEmpty) return;
    final secure = net['secure'] != false;
    var password = '';
    if (secure) {
      final result = await _promptPassword(ssid);
      if (result == null) return;
      password = result;
    }
    if (!mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      if (!widget.config.mockBackend) {
        await widget.bridge.connectWifi(ssid, password);
      } else {
        await Future<void>.delayed(const Duration(milliseconds: 700));
      }
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss spinner
      widget.onboarding.setWifi(ssid);
      context.push('/wifi-connected');
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop();
      await showModalDialog(
        context,
        title: 'Could not connect',
        message: 'Failed to join "$ssid". Check the password and try again.',
        confirmText: 'OK',
        cancelText: '',
      );
    }
  }

  Future<String?> _promptPassword(String ssid) {
    final controller = TextEditingController();
    var obscure = true;
    return showDialog<String>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSt) => Center(
          child: Container(
            width: 440,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(Layout.borderRadius),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  ssid,
                  style: const TextStyle(
                    color: AppColors.white,
                    fontSize: FontSizes.large,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: controller,
                  obscureText: obscure,
                  autofocus: true,
                  style: const TextStyle(color: AppColors.white),
                  onSubmitted: (v) => Navigator.of(ctx).pop(v),
                  decoration: InputDecoration(
                    hintText: 'Password',
                    hintStyle: const TextStyle(color: AppColors.gray500),
                    filled: true,
                    fillColor: AppColors.surfaceLight,
                    suffixIcon: IconButton(
                      icon: Icon(obscure ? Icons.visibility : Icons.visibility_off,
                          color: AppColors.gray400),
                      onPressed: () => setSt(() => obscure = !obscure),
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: AppButton.secondary(
                        label: 'CANCEL',
                        height: 48,
                        onPressed: () => Navigator.of(ctx).pop(),
                      ),
                    ),
                    const SizedBox(width: Spacing.buttonSpacing),
                    Expanded(
                      child: AppButton.primary(
                        label: 'CONNECT',
                        height: 48,
                        onPressed: () => Navigator.of(ctx).pop(controller.text),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return OnboardingScaffold(
      showBrand: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Expanded(
                child: Text(
                  'Choose a Wi-Fi network',
                  style: TextStyle(
                    color: AppColors.white,
                    fontSize: FontSizes.huge,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              IconButton(
                onPressed: _scanning ? null : _scan,
                icon: const Icon(Icons.refresh, color: AppColors.gray300),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: _scanning
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Text(
                          _error!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: AppColors.gray400),
                        ),
                      )
                    : ListView.separated(
                        itemCount: _networks.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (_, i) {
                          final net = _networks[i];
                          return WiFiNetworkItem(
                            ssid: (net['ssid'] ?? '').toString(),
                            signalStrength:
                                (net['signal_strength'] as num?)?.toInt() ?? 0,
                            connected: net['connected'] == true,
                            onPressed: () => _connect(net),
                          );
                        },
                      ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: SizedBox(
              width: 120,
              child: AppButton.secondary(
                label: 'Back',
                onPressed: () => context.pop(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
