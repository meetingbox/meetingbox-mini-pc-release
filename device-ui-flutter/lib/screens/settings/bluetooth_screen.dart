import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/screens/settings/setting_scaffold.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';

/// Bluetooth scan / pair / connect / remove, ported from the Kivy
/// `bluetooth_screen`. Talks to the local Python bridge.
class BluetoothScreen extends StatefulWidget {
  const BluetoothScreen({super.key, required this.bridge});

  final DeviceBridgeClient bridge;

  @override
  State<BluetoothScreen> createState() => _BluetoothScreenState();
}

class _BluetoothScreenState extends State<BluetoothScreen> {
  bool _powerOn = false;
  bool _scanning = false;
  String? _error;
  List<Map<String, dynamic>> _paired = [];
  List<Map<String, dynamic>> _nearby = [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final s = await widget.bridge.bluetoothStatus();
      if (!mounted) return;
      setState(() {
        _powerOn = s['power_on'] == true;
        _paired = (s['paired'] as List? ?? []).cast<Map<String, dynamic>>();
        _error = s['available'] == false ? 'Bluetooth not available' : null;
      });
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  Future<void> _togglePower(bool on) async {
    setState(() => _powerOn = on);
    try {
      await widget.bridge.setBluetoothPower(on);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
    _refresh();
  }

  Future<void> _scan() async {
    setState(() {
      _scanning = true;
      _error = null;
    });
    try {
      final found = await widget.bridge.scanBluetooth();
      if (mounted) setState(() => _nearby = found);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  Future<void> _action(Future<void> Function() fn) async {
    try {
      await fn();
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return SettingScaffold(
      title: 'Bluetooth',
      child: ListView(
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('Bluetooth',
                    style: TextStyle(color: AppColors.white, fontSize: 16)),
              ),
              Switch(value: _powerOn, onChanged: _togglePower),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: AppColors.red)),
          ],
          const SizedBox(height: 16),
          _header('PAIRED'),
          if (_paired.isEmpty)
            _hint('No paired devices')
          else
            ..._paired.map((d) => _deviceRow(d, paired: true)),
          const SizedBox(height: 16),
          Row(
            children: [
              _header('NEARBY'),
              const Spacer(),
              TextButton(
                onPressed: _scanning || !_powerOn ? null : _scan,
                child: Text(_scanning ? 'Scanning…' : 'Scan'),
              ),
            ],
          ),
          if (_nearby.isEmpty)
            _hint(_powerOn ? 'Tap Scan to find devices' : 'Turn Bluetooth on')
          else
            ..._nearby.map((d) => _deviceRow(d, paired: false)),
        ],
      ),
    );
  }

  Widget _header(String t) => Text(
        t,
        style: const TextStyle(
          color: AppColors.gray400,
          fontSize: FontSizes.small,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
        ),
      );

  Widget _hint(String t) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(t, style: const TextStyle(color: AppColors.gray500)),
      );

  Widget _deviceRow(Map<String, dynamic> d, {required bool paired}) {
    final mac = (d['mac'] ?? '').toString();
    final name = (d['name'] ?? mac).toString();
    final connected = d['connected'] == true;
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xDB1F2A3B),
        borderRadius: BorderRadius.circular(Layout.borderRadius),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: const TextStyle(color: AppColors.white, fontSize: 15)),
                Text(connected ? 'Connected' : mac,
                    style: const TextStyle(color: AppColors.gray400, fontSize: 12)),
              ],
            ),
          ),
          if (paired) ...[
            TextButton(
              onPressed: () => _action(() => widget.bridge.connectBluetooth(mac)),
              child: const Text('Connect'),
            ),
            IconButton(
              onPressed: () => _action(() => widget.bridge.removeBluetooth(mac)),
              icon: const Icon(Icons.delete_outline, color: AppColors.gray400),
            ),
          ] else
            TextButton(
              onPressed: () => _action(() => widget.bridge.pairBluetooth(mac)),
              child: const Text('Pair'),
            ),
        ],
      ),
    );
  }
}
