import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';

/// Single-field text editor sub-screen, used for Device Name / Room label.
/// Ports the Kivy text-input settings flow.
class TextEditSettingScreen extends StatefulWidget {
  const TextEditSettingScreen({
    super.key,
    required this.title,
    required this.label,
    this.initial = '',
    this.onSave,
  });

  final String title;
  final String label;
  final String initial;
  final Future<void> Function(String value)? onSave;

  @override
  State<TextEditSettingScreen> createState() => _TextEditSettingScreenState();
}

class _TextEditSettingScreenState extends State<TextEditSettingScreen> {
  late final TextEditingController _controller =
      TextEditingController(text: widget.initial);
  bool _saving = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await widget.onSave?.call(_controller.text.trim());
      if (mounted && context.canPop()) context.pop();
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: widget.title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.label,
              style: const TextStyle(color: AppColors.gray300, fontSize: 15)),
          const SizedBox(height: 12),
          TextField(
            controller: _controller,
            autofocus: true,
            style: const TextStyle(color: AppColors.white, fontSize: 18),
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xDB1F2A3B),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: AppColors.gray700),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: AppColors.primaryStart),
              ),
            ),
          ),
          const SizedBox(height: 24),
          AppButton(
            label: _saving ? 'Saving…' : 'Save',
            onPressed: _saving ? null : _save,
          ),
        ],
      ),
    );
  }
}
