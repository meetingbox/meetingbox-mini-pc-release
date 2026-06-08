import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';
import 'package:meetingbox_device_ui/widgets/modal_dialog.dart';
import 'package:meetingbox_device_ui/widgets/onboarding_scaffold.dart';

/// Ported from `screens/network_choice.py`.
class NetworkChoiceScreen extends StatelessWidget {
  const NetworkChoiceScreen({
    super.key,
    required this.api,
    required this.onboarding,
  });

  final ApiClient api;
  final OnboardingState onboarding;

  Future<void> _onEthernet(BuildContext context) async {
    final ok = await api.healthCheck();
    if (!context.mounted) return;
    if (!ok) {
      await showModalDialog(
        context,
        title: 'Cannot reach MeetingBox',
        message:
            'Check the cable, router, and backend, then try again or use Wi-Fi.',
        confirmText: 'OK',
        cancelText: '',
      );
      return;
    }
    onboarding.setWifi('Wired Ethernet', ethernet: true);
    if (context.mounted) context.push('/wifi-connected');
  }

  @override
  Widget build(BuildContext context) {
    return OnboardingScaffold(
      showBrand: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'SETUP · NETWORK',
            style: TextStyle(
              color: AppColors.blue,
              fontSize: FontSizes.tiny,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Connect to the internet',
            style: TextStyle(
              color: AppColors.white,
              fontSize: FontSizes.huge,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          OnboardingCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Use Wi-Fi, or skip if this MeetingBox already has working wired Ethernet.',
                  style: TextStyle(color: AppColors.gray300, fontSize: FontSizes.body),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Choose the most reliable connection for meeting capture and cloud sync.',
                  style: TextStyle(color: AppColors.green, fontSize: FontSizes.small),
                ),
                const SizedBox(height: 12),
                AppButton.primary(
                  label: 'Set up Wi-Fi',
                  height: 58,
                  onPressed: () {
                    onboarding.setWifi('');
                    context.push('/wifi-setup');
                  },
                ),
                const SizedBox(height: 12),
                AppButton.secondary(
                  label: 'Use wired Ethernet',
                  height: 58,
                  onPressed: () => _onEthernet(context),
                ),
              ],
            ),
          ),
          const Spacer(),
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
