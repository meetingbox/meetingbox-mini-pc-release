import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';

/// Single-choice list sub-screen used by timezone / auto-delete / update
/// channel / idle timeout pickers. Ports the Kivy `*_picker` screens.
class PickerSettingScreen extends StatefulWidget {
  const PickerSettingScreen({
    super.key,
    required this.title,
    required this.options,
    this.selected,
    this.onSelected,
  });

  final String title;
  final List<String> options;
  final String? selected;
  final ValueChanged<String>? onSelected;

  @override
  State<PickerSettingScreen> createState() => _PickerSettingScreenState();
}

class _PickerSettingScreenState extends State<PickerSettingScreen> {
  late String? _selected = widget.selected;

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: widget.title,
      child: ListView.separated(
        itemCount: widget.options.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (_, i) {
          final opt = widget.options[i];
          final active = opt == _selected;
          return GestureDetector(
            onTap: () {
              setState(() => _selected = opt);
              widget.onSelected?.call(opt);
            },
            child: Container(
              height: 60,
              padding: const EdgeInsets.symmetric(horizontal: 18),
              decoration: BoxDecoration(
                color: const Color(0xDB1F2A3B),
                borderRadius: BorderRadius.circular(Layout.borderRadius),
                border: active
                    ? Border.all(color: AppColors.primaryStart, width: 2)
                    : null,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      opt,
                      style: const TextStyle(
                        color: AppColors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (active)
                    const Icon(Icons.check, color: AppColors.primaryStart, size: 22),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
