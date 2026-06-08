import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/services/voice_event_client.dart';

/// Global voice assistant overlay, ported from the Kivy voice UI states in
/// `voice_assistant.py` / `realtime_voice_session.py`. Renders wake / listen /
/// think / speak / error surfaces above the active screen. Hidden while idle.
class VoiceOverlay extends StatelessWidget {
  const VoiceOverlay({super.key, required this.client});

  final VoiceEventClient client;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: client,
      builder: (context, _) {
        if (client.state == VoiceState.idle) {
          return const SizedBox.shrink();
        }
        return Positioned.fill(
          child: IgnorePointer(
            child: Container(
              color: Colors.black.withValues(alpha: 0.45),
              alignment: Alignment.center,
              child: _Orb(state: client.state, level: client.audioLevel, caption: client.caption),
            ),
          ),
        );
      },
    );
  }
}

class _Orb extends StatefulWidget {
  const _Orb({required this.state, required this.level, required this.caption});

  final VoiceState state;
  final double level;
  final String caption;

  @override
  State<_Orb> createState() => _OrbState();
}

class _OrbState extends State<_Orb> with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  Color get _color {
    switch (widget.state) {
      case VoiceState.listening:
        return AppColors.primaryStart;
      case VoiceState.thinking:
        return const Color(0xFF8552EB);
      case VoiceState.speaking:
        return AppColors.green;
      case VoiceState.error:
        return AppColors.red;
      case VoiceState.idle:
        return AppColors.gray500;
    }
  }

  String get _label {
    switch (widget.state) {
      case VoiceState.listening:
        return 'Listening…';
      case VoiceState.thinking:
        return 'Thinking…';
      case VoiceState.speaking:
        return 'Speaking…';
      case VoiceState.error:
        return widget.caption.isEmpty ? 'Something went wrong' : widget.caption;
      case VoiceState.idle:
        return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedBuilder(
          animation: _pulse,
          builder: (context, _) {
            const base = 120.0;
            final reactive = widget.state == VoiceState.listening
                ? widget.level.clamp(0, 1) * 40
                : 0;
            final breathe = math.sin(_pulse.value * math.pi) * 14;
            final size = base + reactive + breathe;
            return Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [_color, _color.withValues(alpha: 0.25)],
                ),
                boxShadow: [
                  BoxShadow(
                    color: _color.withValues(alpha: 0.5),
                    blurRadius: 40,
                    spreadRadius: 6,
                  ),
                ],
              ),
              child: Icon(
                widget.state == VoiceState.error
                    ? Icons.error_outline
                    : Icons.mic,
                color: Colors.white,
                size: 44,
              ),
            );
          },
        ),
        const SizedBox(height: 24),
        if (widget.caption.isNotEmpty && widget.state != VoiceState.error)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              widget.caption,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.white, fontSize: 18),
            ),
          ),
        Text(
          _label,
          style: TextStyle(
            color: _color,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}
