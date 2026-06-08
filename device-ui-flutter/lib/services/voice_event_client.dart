import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';

/// Voice assistant UI states, mirroring the Kivy voice runtime callbacks.
enum VoiceState { idle, listening, thinking, speaking, error }

VoiceState _parseState(String? s) {
  switch (s) {
    case 'listening':
      return VoiceState.listening;
    case 'thinking':
    case 'processing':
      return VoiceState.thinking;
    case 'speaking':
      return VoiceState.speaking;
    case 'error':
      return VoiceState.error;
    default:
      return VoiceState.idle;
  }
}

/// Subscribes to the Python bridge event stream (`/v1/events`) and exposes
/// voice/audio/recording UI state to the Flutter overlays. Python keeps owning
/// Vosk, realtime audio, and echo cancellation; this only renders state.
class VoiceEventClient extends ChangeNotifier {
  VoiceEventClient(this.config);

  final AppConfig config;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Timer? _reconnect;
  bool _disposed = false;

  VoiceState _state = VoiceState.idle;
  double _audioLevel = 0;
  double _micTestLevel = 0;
  String _caption = '';
  bool _recording = false;

  VoiceState get state => _state;
  double get audioLevel => _audioLevel;
  double get micTestLevel => _micTestLevel;
  String get caption => _caption;
  bool get recording => _recording;

  Uri get _wsUri {
    final base = config.deviceBridgeUrl;
    final ws = base.replaceFirst(RegExp(r'^http'), 'ws');
    return Uri.parse('$ws/v1/events');
  }

  void connect() {
    if (_disposed) return;
    try {
      _channel = WebSocketChannel.connect(_wsUri);
      _sub = _channel!.stream.listen(
        _onMessage,
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _sub?.cancel();
    _sub = null;
    _channel = null;
    if (_disposed) return;
    _reconnect?.cancel();
    _reconnect = Timer(const Duration(seconds: 3), connect);
  }

  void _onMessage(dynamic raw) {
    Map<String, dynamic> event;
    try {
      event = jsonDecode(raw as String) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final type = event['type'];
    switch (type) {
      case 'voice_state':
        _state = _parseState(event['state'] as String?);
        if (event['text'] is String) _caption = event['text'] as String;
        break;
      case 'audio_level':
        _audioLevel = (event['level'] as num?)?.toDouble() ?? 0;
        break;
      case 'mic_test_level':
        _micTestLevel = (event['level'] as num?)?.toDouble() ?? 0;
        break;
      case 'recording_state':
        _recording = event['state'] == 'recording' || event['state'] == 'started';
        break;
      case 'error':
        _state = VoiceState.error;
        _caption = (event['detail'] ?? event['text'] ?? 'Error').toString();
        break;
      default:
        return;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _reconnect?.cancel();
    _sub?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}
