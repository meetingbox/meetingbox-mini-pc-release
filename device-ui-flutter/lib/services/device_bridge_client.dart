import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:meetingbox_device_ui/config/app_config.dart';

/// Local Python bridge (`mini-pc/device-services`) for WiFi, brightness, audio, etc.
class DeviceBridgeClient {
  DeviceBridgeClient(this.config, {http.Client? client})
      : _client = client ?? http.Client();

  final AppConfig config;
  final http.Client _client;

  Uri _uri(String path) => Uri.parse('${config.deviceBridgeUrl}$path');

  Future<bool> isHealthy() async {
    try {
      final resp = await _client
          .get(_uri('/health'))
          .timeout(const Duration(seconds: 3));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<List<Map<String, dynamic>>> scanWifi() async {
    final resp = await _client
        .get(_uri('/v1/wifi/scan'))
        .timeout(const Duration(seconds: 30));
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('WiFi scan failed: HTTP ${resp.statusCode}');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    return (body['networks'] as List? ?? []).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> connectWifi(String ssid, String password) async {
    final resp = await _client
        .post(
          _uri('/v1/wifi/connect'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'ssid': ssid, 'password': password}),
        )
        .timeout(const Duration(seconds: 45));
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('WiFi connect failed: HTTP ${resp.statusCode}');
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _get(String path,
      {Duration timeout = const Duration(seconds: 10)}) async {
    final resp = await _client.get(_uri(path)).timeout(timeout);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('GET $path failed: HTTP ${resp.statusCode}');
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body,
      {Duration timeout = const Duration(seconds: 15)}) async {
    final resp = await _client
        .post(
          _uri(path),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(timeout);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('POST $path failed: HTTP ${resp.statusCode}');
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  // --- Brightness ---------------------------------------------------------
  Future<int?> getBrightness() async {
    final b = await _get('/v1/brightness');
    return (b['percent'] as num?)?.toInt();
  }

  Future<void> setBrightness(int percent) =>
      _post('/v1/brightness', {'percent': percent},
          timeout: const Duration(seconds: 5));

  // --- WiFi radio + saved -------------------------------------------------
  Future<Map<String, dynamic>> wifiStatus() => _get('/v1/wifi/status');

  Future<void> setWifiRadio(bool on) => _post('/v1/wifi/radio', {'on': on});

  Future<void> forgetWifi(String ssid) => _post('/v1/wifi/forget', {'ssid': ssid});

  // --- Bluetooth ----------------------------------------------------------
  Future<Map<String, dynamic>> bluetoothStatus() => _get('/v1/bluetooth/status');

  Future<void> setBluetoothPower(bool on) =>
      _post('/v1/bluetooth/power', {'on': on});

  Future<List<Map<String, dynamic>>> scanBluetooth({int seconds = 7}) async {
    final b = await _get('/v1/bluetooth/scan?seconds=$seconds',
        timeout: Duration(seconds: seconds + 8));
    return (b['devices'] as List? ?? []).cast<Map<String, dynamic>>();
  }

  Future<void> pairBluetooth(String mac) => _post('/v1/bluetooth/pair', {'mac': mac});

  Future<void> connectBluetooth(String mac) =>
      _post('/v1/bluetooth/connect', {'mac': mac});

  Future<void> removeBluetooth(String mac) =>
      _post('/v1/bluetooth/remove', {'mac': mac});

  // --- Audio --------------------------------------------------------------
  Future<Map<String, dynamic>> audioDevices() => _get('/v1/audio/devices');

  Future<int?> getVolume() async {
    final b = await _get('/v1/audio/volume');
    return (b['percent'] as num?)?.toInt();
  }

  Future<void> setVolume(int percent, {String target = 'speech'}) =>
      _post('/v1/audio/volume', {'target': target, 'percent': percent});

  Future<void> setDefaultSink(String id) =>
      _post('/v1/audio/default-sink', {'id': id});

  Future<void> setDefaultSource(String id) =>
      _post('/v1/audio/default-source', {'id': id});

  // --- Display + power + system ------------------------------------------
  Future<void> setDisplay(bool on) => _post('/v1/display', {'on': on});

  Future<void> powerAction(String action) => _post('/v1/power', {'action': action});

  Future<List<String>> usbDevices() async {
    final b = await _get('/v1/system/usb');
    return (b['devices'] as List? ?? []).cast<String>();
  }

  void dispose() => _client.close();
}
