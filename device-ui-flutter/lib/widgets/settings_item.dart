import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/toggle_switch.dart';

enum SettingsItemMode { arrow, toggle, info }

/// Settings list row, ported from `components/settings_item.py`.
class SettingsItem extends StatefulWidget {
  const SettingsItem({
    super.key,
    required this.title,
    this.subtitle = '',
    this.mode = SettingsItemMode.arrow,
    this.active = false,
    this.onPressed,
    this.onToggle,
  });

  final String title;
  final String subtitle;
  final SettingsItemMode mode;
  final bool active;
  final VoidCallback? onPressed;
  final ValueChanged<bool>? onToggle;

  @override
  State<SettingsItem> createState() => _SettingsItemState();
}

class _SettingsItemState extends State<SettingsItem> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final tappable = widget.mode == SettingsItemMode.arrow;
    return GestureDetector(
      onTapDown: tappable ? (_) => setState(() => _pressed = true) : null,
      onTapUp: tappable ? (_) => setState(() => _pressed = false) : null,
      onTapCancel: tappable ? () => setState(() => _pressed = false) : null,
      onTap: widget.onPressed,
      child: Container(
        height: 68,
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        decoration: BoxDecoration(
          color: _pressed
              ? const Color(0xF52E3D57)
              : const Color(0xDB1F2A3B),
          borderRadius: BorderRadius.circular(Layout.borderRadius),
          boxShadow: const [
            BoxShadow(color: Color(0x24000000), blurRadius: 6, offset: Offset(1, 2)),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.white,
                      fontSize: FontSizes.small + 2,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (widget.subtitle.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      widget.subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.gray300,
                        fontSize: FontSizes.small,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (widget.mode == SettingsItemMode.toggle)
              ToggleSwitch(active: widget.active, onToggle: widget.onToggle)
            else if (widget.mode == SettingsItemMode.arrow)
              const Icon(Icons.chevron_right, color: AppColors.gray400, size: 24),
          ],
        ),
      ),
    );
  }
}
