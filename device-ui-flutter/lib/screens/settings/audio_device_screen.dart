import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';

/// Audio output / input device picker, ported from the Kivy
/// `audio_output_picker` / `audio_input_picker`. Lists Pulse devices from the
/// bridge and sets the default sink/source.
class AudioDeviceScreen extends StatefulWidget {
  const AudioDeviceScreen({
    super.key,
    required this.bridge,
    required this.isInput,
  });

  final DeviceBridgeClient bridge;
  final bool isInput;

  @override
  State<AudioDeviceScreen> createState() => _AudioDeviceScreenState();
}

class _AudioDeviceScreenState extends State<AudioDeviceScreen> {
  List<Map<String, dynamic>> _devices = [];
  String? _selectedId;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final b = await widget.bridge.audioDevices();
      final key = widget.isInput ? 'inputs' : 'outputs';
      if (mounted) {
        setState(() {
          _devices = (b[key] as List? ?? []).cast<Map<String, dynamic>>();
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          _loading = false;
        });
      }
    }
  }

  Future<void> _select(String id) async {
    setState(() => _selectedId = id);
    try {
      if (widget.isInput) {
        await widget.bridge.setDefaultSource(id);
      } else {
        await widget.bridge.setDefaultSink(id);
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: widget.isInput ? 'Audio input' : 'Audio output',
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Text(_error!, style: const TextStyle(color: AppColors.red))
              : _devices.isEmpty
                  ? const Text('No devices found.',
                      style: TextStyle(color: AppColors.gray500))
                  : ListView.separated(
                      itemCount: _devices.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (_, i) {
                        final d = _devices[i];
                        final id = (d['id'] ?? '').toString();
                        final active = id == _selectedId;
                        return GestureDetector(
                          onTap: () => _select(id),
                          child: Container(
                            height: 60,
                            padding: const EdgeInsets.symmetric(horizontal: 18),
                            decoration: BoxDecoration(
                              color: const Color(0xDB1F2A3B),
                              borderRadius:
                                  BorderRadius.circular(Layout.borderRadius),
                              border: active
                                  ? Border.all(
                                      color: AppColors.primaryStart, width: 2)
                                  : null,
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    (d['name'] ?? id).toString(),
                                    style: const TextStyle(
                                        color: AppColors.white, fontSize: 15),
                                  ),
                                ),
                                if (active)
                                  const Icon(Icons.check,
                                      color: AppColors.primaryStart),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
    );
  }
}
