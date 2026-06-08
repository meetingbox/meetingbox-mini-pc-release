import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';

/// Meeting list card, ported from `components/meeting_card.py`.
class MeetingCard extends StatefulWidget {
  const MeetingCard({
    super.key,
    required this.title,
    required this.meta,
    this.pendingActions = 0,
    this.onPressed,
  });

  final String title;
  final String meta;
  final int pendingActions;
  final VoidCallback? onPressed;

  @override
  State<MeetingCard> createState() => _MeetingCardState();
}

class _MeetingCardState extends State<MeetingCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.onPressed,
      child: Container(
        height: 86,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: _pressed ? const Color(0xFA2E3D57) : const Color(0xEB222B3D),
          borderRadius: BorderRadius.circular(Layout.borderRadius),
          boxShadow: const [
            BoxShadow(color: Color(0x2E000000), blurRadius: 8, offset: Offset(1, 3)),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              widget.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.white,
                fontSize: FontSizes.medium + 1,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              widget.meta,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.gray300,
                fontSize: FontSizes.small,
              ),
            ),
            if (widget.pendingActions > 0) ...[
              const SizedBox(height: 2),
              Text(
                '\u26A1 ${widget.pendingActions} pending '
                'action${widget.pendingActions > 1 ? 's' : ''}',
                style: const TextStyle(
                  color: AppColors.yellow,
                  fontSize: FontSizes.small,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
