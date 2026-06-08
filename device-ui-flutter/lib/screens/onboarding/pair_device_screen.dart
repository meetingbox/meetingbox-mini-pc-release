import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';
import 'package:meetingbox_device_ui/widgets/modal_dialog.dart';
import 'package:meetingbox_device_ui/widgets/onboarding_scaffold.dart';

/// Ported from `screens/pair_device.py`.
class PairDeviceScreen extends StatefulWidget {
  const PairDeviceScreen({
    super.key,
    required this.config,
    required this.api,
    required this.onboarding,
  });

  final AppConfig config;
  final ApiClient api;
  final OnboardingState onboarding;

  @override
  State<PairDeviceScreen> createState() => _PairDeviceScreenState();
}

class _PairDeviceScreenState extends State<PairDeviceScreen> {
  final _codeController = TextEditingController();
  bool _linking = false;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _onLink() async {
    final name = widget.onboarding.deviceName.trim();
    if (name.isEmpty) {
      await showModalDialog(context,
          title: 'Room name',
          message: 'Go back in setup and choose a room name first.',
          confirmText: 'OK',
          cancelText: '');
      return;
    }
    final code = _codeController.text.replaceAll(' ', '').trim();
    if (code.length < 6 || code.length > 8) {
      await showModalDialog(context,
          title: 'Pairing code',
          message: 'Enter the 6-character code from the web app.',
          confirmText: 'OK',
          cancelText: '');
      return;
    }

    setState(() => _linking = true);
    try {
      if (widget.config.mockBackend) {
        await Future<void>.delayed(const Duration(milliseconds: 600));
        widget.onboarding.setPairedOwner('owner@example.com');
      } else {
        final data = await widget.api.claimDevice(code, deviceName: name);
        final dev = data['device'] as Map<String, dynamic>? ?? {};
        widget.onboarding.setDeviceName((dev['device_name'] ?? name).toString());
        widget.onboarding
            .setPairedOwner((data['owner_email'] ?? '').toString().trim());
      }
      if (!mounted) return;
      context.push('/meetingbox-ready');
    } on ApiException catch (e) {
      if (!mounted) return;
      await showModalDialog(context,
          title: 'Could not link', message: e.message, confirmText: 'OK', cancelText: '');
    } catch (e) {
      if (!mounted) return;
      await showModalDialog(context,
          title: 'Could not link',
          message: 'Link failed. Check your connection and try again.',
          confirmText: 'OK',
          cancelText: '');
    } finally {
      if (mounted) setState(() => _linking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return OnboardingScaffold(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  const Text(
                    'Link this MeetingBox',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.white,
                      fontSize: FontSizes.huge,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Sign in on the dashboard (scan the QR code), open Settings → Devices, '
                    'and generate a pairing code. Enter it below.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.gray300, fontSize: FontSizes.small),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'SCAN OR OPEN WEB DASHBOARD',
                    style: TextStyle(
                      color: AppColors.gray500,
                      fontSize: FontSizes.small,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(8),
                    color: AppColors.black,
                    child: QrImageView(
                      data: widget.config.dashboardUrl,
                      size: 116,
                      backgroundColor: AppColors.black,
                      eyeStyle: const QrEyeStyle(
                        eyeShape: QrEyeShape.square,
                        color: AppColors.white,
                      ),
                      dataModuleStyle: const QrDataModuleStyle(
                        dataModuleShape: QrDataModuleShape.square,
                        color: AppColors.white,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    widget.config.dashboardUrl,
                    style: const TextStyle(color: AppColors.gray600, fontSize: FontSizes.tiny),
                  ),
                  const SizedBox(height: 16),
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Pairing code',
                      style: TextStyle(
                        color: AppColors.white,
                        fontSize: FontSizes.small,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _codeController,
                    style: const TextStyle(color: AppColors.white, fontSize: FontSizes.medium),
                    onSubmitted: (_) => _onLink(),
                    decoration: InputDecoration(
                      hintText: '6-digit code from web',
                      hintStyle: const TextStyle(color: AppColors.gray600),
                      filled: true,
                      fillColor: const Color(0xFF293548),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  AppButton.primary(
                    label: _linking ? 'Linking…' : 'Link device',
                    height: 52,
                    onPressed: _linking ? null : _onLink,
                  ),
                ],
              ),
            ),
          ),
          Align(
            alignment: Alignment.centerLeft,
            child: SizedBox(
              width: 100,
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
