import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';

/// Action item row with checkbox, ported from `components/action_item.py`.
class ActionItemWidget extends StatefulWidget {
  const ActionItemWidget({
    super.key,
    required this.task,
    this.assignee,
    this.dueDate,
    this.completed = false,
    this.onToggle,
    this.textColor = AppColors.gray900,
  });

  final String task;
  final String? assignee;
  final String? dueDate;
  final bool completed;
  final ValueChanged<bool>? onToggle;
  final Color textColor;

  @override
  State<ActionItemWidget> createState() => _ActionItemWidgetState();
}

class _ActionItemWidgetState extends State<ActionItemWidget> {
  late bool _completed = widget.completed;

  @override
  Widget build(BuildContext context) {
    final meta = [
      if (widget.assignee != null && widget.assignee!.isNotEmpty) widget.assignee!,
      if (widget.dueDate != null && widget.dueDate!.isNotEmpty) widget.dueDate!,
    ].join('  |  ');

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 40,
          child: Checkbox(
            value: _completed,
            onChanged: (v) {
              setState(() => _completed = v ?? false);
              widget.onToggle?.call(_completed);
            },
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.task,
                style: TextStyle(
                  color: widget.textColor,
                  fontSize: FontSizes.small,
                  decoration: _completed ? TextDecoration.lineThrough : null,
                ),
              ),
              if (meta.isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(
                  meta,
                  style: const TextStyle(
                    color: AppColors.gray500,
                    fontSize: FontSizes.tiny,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
