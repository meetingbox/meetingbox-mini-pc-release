import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';

/// Persistent top status bar, ported from `components/status_bar.py`.
///
/// Two modes: a status dot + label (default) or a back button with centred
/// title. An optional settings gear sits on the right.
class StatusBar extends StatefulWidget {
  const StatusBar({
    super.key,
    this.statusText = 'READY',
    this.statusColor = AppColors.green,
    this.deviceName = 'MeetingBox',
    this.pulsing = false,
    this.showSettings = true,
    this.backButton = false,
    this.onBack,
    this.onSettings,
  });

  final String statusText;
  final Color statusColor;
  final String deviceName;
  final bool pulsing;
  final bool showSettings;
  final bool backButton;
  final VoidCallback? onBack;
  final VoidCallback? onSettings;

  @override
  State<StatusBar> createState() => _StatusBarState();
}

class _StatusBarState extends State<StatusBar>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 800),
  );

  @override
  void initState() {
    super.initState();
    if (widget.pulsing && !widget.backButton) {
      _pulse.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 54,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: const BoxDecoration(
        color: Color(0xE00F141F), // (0.06,0.08,0.13,0.88)
        border: Border(bottom: BorderSide(color: Color(0x14FFFFFF))),
      ),
      child: widget.backButton ? _buildBack() : _buildStatus(),
    );
  }

  Widget _buildBack() {
    return Row(
      children: [
        SizedBox(
          width: 118,
          child: GestureDetector(
            onTap: widget.onBack,
            child: const Text(
              '‹  BACK',
              style: TextStyle(
                color: AppColors.gray300,
                fontSize: FontSizes.small + 1,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
        Expanded(
          child: Text(
            widget.deviceName,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.white,
              fontSize: FontSizes.title,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        _gear(width: 118),
      ],
    );
  }

  Widget _buildStatus() {
    return Row(
      children: [
        Expanded(
          flex: 35,
          child: Row(
            children: [
              FadeTransition(
                opacity: widget.pulsing
                    ? Tween(begin: 1.0, end: 0.3).animate(_pulse)
                    : const AlwaysStoppedAnimation(1.0),
                child: Icon(Icons.circle, size: 12, color: widget.statusColor),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  widget.statusText,
                  style: const TextStyle(
                    color: AppColors.white,
                    fontSize: FontSizes.medium,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          flex: 40,
          child: Text(
            widget.deviceName,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.gray400,
              fontSize: FontSizes.small,
            ),
          ),
        ),
        Expanded(flex: 25, child: _gear()),
      ],
    );
  }

  Widget _gear({double? width}) {
    if (!widget.showSettings) return SizedBox(width: width);
    return Align(
      alignment: Alignment.centerRight,
      child: IconButton(
        onPressed: widget.onSettings,
        icon: const Icon(Icons.settings, color: AppColors.gray500, size: 24),
      ),
    );
  }
}
