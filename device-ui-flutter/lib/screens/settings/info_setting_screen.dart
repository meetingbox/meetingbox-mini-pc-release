import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';

/// Read-only info sub-screen. Renders either key/value rows or plain text
/// lines loaded from an async source (e.g. USB list, diagnostics, about).
/// Used for the Kivy info sub-screens that just display device state.
class InfoSettingScreen extends StatefulWidget {
  const InfoSettingScreen({
    super.key,
    required this.title,
    this.rows = const [],
    this.loadLines,
    this.emptyText = 'Nothing to show.',
  });

  final String title;
  final List<({String label, String value})> rows;
  final Future<List<String>> Function()? loadLines;
  final String emptyText;

  @override
  State<InfoSettingScreen> createState() => _InfoSettingScreenState();
}

class _InfoSettingScreenState extends State<InfoSettingScreen> {
  List<String>? _lines;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.loadLines != null) _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final l = await widget.loadLines!();
      if (mounted) setState(() => _lines = l);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: widget.title,
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                for (final r in widget.rows) _kv(r.label, r.value),
                if (_error != null)
                  Text(_error!, style: const TextStyle(color: AppColors.red)),
                if (_lines != null)
                  if (_lines!.isEmpty)
                    Text(widget.emptyText,
                        style: const TextStyle(color: AppColors.gray500))
                  else
                    ..._lines!.map(_line),
              ],
            ),
    );
  }

  Widget _kv(String label, String value) => Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xDB1F2A3B),
          borderRadius: BorderRadius.circular(Layout.borderRadius),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(label,
                  style: const TextStyle(color: AppColors.gray300, fontSize: 15)),
            ),
            Text(value,
                style: const TextStyle(
                    color: AppColors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w600)),
          ],
        ),
      );

  Widget _line(String t) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Text(t,
            style: const TextStyle(
                color: AppColors.gray300,
                fontSize: 13,
                fontFamily: 'monospace')),
      );
}
