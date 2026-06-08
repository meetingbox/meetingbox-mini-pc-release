import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';
import 'package:meetingbox_device_ui/widgets/onboarding_scaffold.dart';

const _suggestedNames = [
  'Boardroom',
  'Conference Room 1',
  'Meeting Room A',
  'War Room',
  'Huddle Space',
];

/// Ported from `screens/room_name.py`.
class RoomNameScreen extends StatefulWidget {
  const RoomNameScreen({super.key, required this.api, required this.onboarding});

  final ApiClient api;
  final OnboardingState onboarding;

  @override
  State<RoomNameScreen> createState() => _RoomNameScreenState();
}

class _RoomNameScreenState extends State<RoomNameScreen> {
  final _controller = TextEditingController();

  @override
  void initState() {
    super.initState();
    _controller.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _valid => _controller.text.trim().isNotEmpty;

  void _onNext() {
    final name = _controller.text.trim();
    if (name.isEmpty) return;
    widget.onboarding.setDeviceName(name);
    widget.api.setDeviceName(name);
    context.push('/network-choice');
  }

  @override
  Widget build(BuildContext context) {
    return OnboardingScaffold(
      showBrand: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'MeetingBox setup',
            style: TextStyle(
              color: AppColors.blue,
              fontSize: FontSizes.small,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Name this room',
            style: TextStyle(
              color: AppColors.white,
              fontSize: FontSizes.huge,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          OnboardingCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'This name appears on the home screen, recordings, and device pairing.',
                  style: TextStyle(color: AppColors.gray300, fontSize: FontSizes.body),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _controller,
                  style: const TextStyle(color: AppColors.white, fontSize: FontSizes.medium),
                  onSubmitted: (_) => _valid ? _onNext() : null,
                  decoration: InputDecoration(
                    hintText: 'e.g. Boardroom A',
                    hintStyle: const TextStyle(color: AppColors.gray500),
                    filled: true,
                    fillColor: const Color(0xFF293548),
                    contentPadding: const EdgeInsets.all(16),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                const Text(
                  'SUGGESTED NAMES',
                  style: TextStyle(
                    color: AppColors.gray500,
                    fontSize: FontSizes.tiny,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (final name in _suggestedNames)
                      SizedBox(
                        height: 48,
                        child: AppButton.secondary(
                          label: name,
                          fontSize: FontSizes.small,
                          onPressed: () => _controller.text = name,
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          const Spacer(),
          Row(
            children: [
              SizedBox(
                width: 112,
                child: AppButton.secondary(
                  label: 'Back',
                  onPressed: () => context.pop(),
                ),
              ),
              const Spacer(),
              SizedBox(
                width: 160,
                child: AppButton.primary(
                  label: 'Continue',
                  onPressed: _valid ? _onNext : null,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
