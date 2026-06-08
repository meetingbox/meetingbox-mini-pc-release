import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';
import 'package:meetingbox_device_ui/widgets/onboarding_scaffold.dart';

/// Ported from `screens/wifi_connected.py`.
class WifiConnectedScreen extends StatefulWidget {
  const WifiConnectedScreen({
    super.key,
    required this.config,
    required this.api,
    required this.onboarding,
  });

  final AppConfig config;
  final ApiClient api;
  final OnboardingState onboarding;

  @override
  State<WifiConnectedScreen> createState() => _WifiConnectedScreenState();
}

class _WifiConnectedScreenState extends State<WifiConnectedScreen> {
  String _ip = 'Loading...';

  bool get _ethernet => widget.onboarding.setupNetworkIsEthernet;

  @override
  void initState() {
    super.initState();
    _loadIp();
  }

  Future<void> _loadIp() async {
    var ip = '';
    if (!widget.config.mockBackend) {
      try {
        final info = await widget.api.getSystemInfo();
        ip = (info['ip_address'] ?? '').toString().trim();
      } catch (_) {}
    } else {
      ip = '192.168.1.42';
    }
    if (mounted) setState(() => _ip = ip.isEmpty ? 'Not available' : ip);
  }

  @override
  Widget build(BuildContext context) {
    final subtitle = _ethernet
        ? 'Using wired Ethernet. Continue when this device can reach the network.'
        : 'Your MeetingBox is now connected and ready to use.';
    return OnboardingScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 12),
          Center(
            child: Container(
              width: 92,
              height: 92,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.green.withValues(alpha: 0.16),
                border: Border.all(color: AppColors.green, width: 3),
              ),
              child: const Icon(Icons.wifi, color: AppColors.green, size: 40),
            ),
          ),
          const SizedBox(height: 14),
          const Text(
            "You're connected",
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppColors.white,
              fontSize: FontSizes.huge,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.gray400, fontSize: FontSizes.body),
          ),
          const SizedBox(height: 16),
          Center(
            child: Container(
              width: 660,
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(Layout.borderRadius),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                children: [
                  _row('Local IP Address', _ip, AppColors.white),
                  const Divider(color: AppColors.gray800, height: 1),
                  _row('Access URL', widget.config.dashboardUrl, AppColors.blue),
                ],
              ),
            ),
          ),
          const Spacer(),
          Center(
            child: SizedBox(
              width: 230,
              child: AppButton.primary(
                label: 'Continue setup',
                onPressed: () => context.push('/pair-device'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value, Color valueColor) {
    return SizedBox(
      height: 42,
      child: Row(
        children: [
          Expanded(
            flex: 55,
            child: Text(label,
                style: const TextStyle(color: AppColors.gray500, fontSize: FontSizes.small)),
          ),
          Expanded(
            flex: 45,
            child: Text(
              value,
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: valueColor, fontSize: FontSizes.medium),
            ),
          ),
        ],
      ),
    );
  }
}
