import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';

/// Generic 0-100 slider sub-screen used by brightness / volumes / mic gain.
/// Ports the Kivy `brightness_slider` and `*_volume_picker` behavior.
class SliderSettingScreen extends StatefulWidget {
  const SliderSettingScreen({
    super.key,
    required this.title,
    required this.label,
    this.initial = 50,
    this.onLoad,
    this.onChanged,
  });

  final String title;
  final String label;
  final int initial;

  /// Optional async loader for the current value (e.g. bridge.getBrightness).
  final Future<int?> Function()? onLoad;

  /// Applies the value live (e.g. bridge.setBrightness).
  final Future<void> Function(int percent)? onChanged;

  @override
  State<SliderSettingScreen> createState() => _SliderSettingScreenState();
}

class _SliderSettingScreenState extends State<SliderSettingScreen> {
  late double _value = widget.initial.toDouble();

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  Future<void> _loadInitial() async {
    if (widget.onLoad == null) return;
    try {
      final v = await widget.onLoad!();
      if (v != null && mounted) setState(() => _value = v.toDouble());
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: widget.title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.label,
            style: const TextStyle(color: AppColors.gray300, fontSize: 16),
          ),
          const SizedBox(height: 8),
          Text(
            '${_value.round()}%',
            style: const TextStyle(
              color: AppColors.white,
              fontSize: 40,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 24),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: AppColors.primaryStart,
              thumbColor: AppColors.primaryStart,
              inactiveTrackColor: AppColors.gray600,
              trackHeight: 8,
            ),
            child: Slider(
              value: _value,
              max: 100,
              onChanged: (v) => setState(() => _value = v),
              onChangeEnd: (v) async {
                if (widget.onChanged != null) {
                  try {
                    await widget.onChanged!(v.round());
                  } catch (_) {}
                }
              },
            ),
          ),
        ],
      ),
    );
  }
}
