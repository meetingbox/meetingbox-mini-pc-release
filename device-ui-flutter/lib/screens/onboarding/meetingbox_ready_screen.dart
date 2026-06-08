import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/services/setup_state.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';
import 'package:meetingbox_device_ui/widgets/modal_dialog.dart';
import 'package:meetingbox_device_ui/widgets/onboarding_scaffold.dart';

/// Ported from `screens/meetingbox_ready.py`. Writes the local setup marker,
/// notifies the backend, then enters home.
class MeetingBoxReadyScreen extends StatefulWidget {
  const MeetingBoxReadyScreen({
    super.key,
    required this.config,
    required this.api,
    required this.onboarding,
    required this.setupState,
  });

  final AppConfig config;
  final ApiClient api;
  final OnboardingState onboarding;
  final SetupState setupState;

  @override
  State<MeetingBoxReadyScreen> createState() => _MeetingBoxReadyScreenState();
}

class _MeetingBoxReadyScreenState extends State<MeetingBoxReadyScreen> {
  bool _busy = false;

  Future<void> _getStarted() async {
    setState(() => _busy = true);
    final wifi = widget.onboarding.connectedWifiSsid;
    var apiOk = true;
    if (!widget.config.mockBackend) {
      apiOk = await widget.api.postSetupComplete(wifi: wifi);
    }
    var localOk = false;
    try {
      await widget.setupState.markSetupComplete();
      localOk = true;
    } catch (_) {
      localOk = false;
    }
    if (!mounted) return;
    if (apiOk || localOk) {
      context.go('/home');
    } else {
      setState(() => _busy = false);
      await showModalDialog(context,
          title: 'Could not finish setup',
          message:
              'Setup could not be saved. Check the web service and storage, then try again.',
          confirmText: 'OK',
          cancelText: '');
    }
  }

  @override
  Widget build(BuildContext context) {
    final o = widget.onboarding;
    return OnboardingScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 8),
          Center(
            child: Container(
              width: 88,
              height: 88,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  colors: [AppColors.primaryStart, AppColors.primaryEnd],
                ),
              ),
              child: const Icon(Icons.check, color: AppColors.white, size: 44),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'MeetingBox is ready.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppColors.white,
              fontSize: FontSizes.huge,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          Center(
            child: Container(
              width: 620,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(Layout.borderRadius),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                children: [
                  _row('Room Name', o.deviceName),
                  const Divider(color: AppColors.gray800, height: 1),
                  _row('Google account',
                      o.pairedOwnerEmail.isEmpty ? '—' : o.pairedOwnerEmail),
                  const Divider(color: AppColors.gray800, height: 1),
                  _row('Language', '🌐 ${o.setupLanguage}'),
                  const Divider(color: AppColors.gray800, height: 1),
                  _row('WiFi',
                      '📶 ${o.connectedWifiSsid.isEmpty ? '—' : o.connectedWifiSsid}'),
                ],
              ),
            ),
          ),
          const Spacer(),
          Row(
            children: [
              SizedBox(
                width: 100,
                child: AppButton.secondary(
                  label: 'Back',
                  onPressed: () => context.pop(),
                ),
              ),
              const Spacer(),
              SizedBox(
                width: 220,
                child: AppButton.primary(
                  label: _busy ? 'Finishing…' : 'Get started',
                  onPressed: _busy ? null : _getStarted,
                ),
              ),
              const Spacer(),
            ],
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          Expanded(
            flex: 42,
            child: Text(label,
                style: const TextStyle(color: AppColors.gray500, fontSize: FontSizes.small)),
          ),
          Expanded(
            flex: 58,
            child: Text(
              value,
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.white,
                fontSize: FontSizes.medium,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
