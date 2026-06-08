import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';
import 'package:meetingbox_device_ui/core/layout/frame19_layout.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/modal_dialog.dart';
import 'package:meetingbox_device_ui/widgets/wavebar.dart';

/// Recording screen ported from `screens/recording.py` + `frame19_layout.py`.
/// The ring/vector graphics, timer, status dot, wavebar, and bottom controls
/// are placed on the shared 1260×800 canvas using exact Figma coordinates.
class RecordingScreen extends StatefulWidget {
  const RecordingScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends State<RecordingScreen> {
  final _wave = WavebarController();
  Timer? _timer;
  int _elapsed = 0;
  bool _paused = false;
  String? _sessionId;
  late final String _startedAt;

  @override
  void initState() {
    super.initState();
    _startedAt = DateFormat('h:mm a').format(DateTime.now());
    _wave.active = true;
    _start();
  }

  Future<void> _start() async {
    if (!widget.config.mockBackend) {
      final result = await widget.api.startRecording();
      final sid = (result['session_id'] ?? '').toString();
      if (sid.isNotEmpty) _sessionId = sid;
    }
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!_paused && mounted) setState(() => _elapsed++);
      // Idle ripple so the wavebar shows we're listening (real levels come
      // from the device bridge audio event stream in the voice phase).
      if (!_paused) _wave.feedLevel(0.15 + (_elapsed % 3) * 0.12);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _wave.dispose();
    super.dispose();
  }

  String get _hms {
    final h = _elapsed ~/ 3600;
    final m = (_elapsed % 3600) ~/ 60;
    final s = _elapsed % 60;
    String two(int v) => v.toString().padLeft(2, '0');
    return '${two(h)} : ${two(m)} : ${two(s)}';
  }

  Future<void> _onPause() async {
    setState(() {
      _paused = true;
      _wave.active = false;
    });
    await showModalDialog(
      context,
      title: 'Recording paused',
      message: 'Choose to continue the session or stop recording.',
      confirmText: 'Continue recording',
      cancelText: 'Stop recording',
      onConfirm: () => setState(() {
        _paused = false;
        _wave.active = true;
      }),
      onCancel: _stop,
    );
  }

  Future<void> _stop() async {
    _timer?.cancel();
    Map<String, dynamic> result = {};
    if (!widget.config.mockBackend) {
      result = await widget.api.stopRecording();
    }
    if (!mounted) return;
    final id = (result['meeting_id'] ??
            result['session_id'] ??
            _sessionId ??
            result['id'] ??
            '')
        .toString();
    context.go('/processing', extra: id.isEmpty ? null : id);
  }

  @override
  Widget build(BuildContext context) {
    Widget img(String name) => Image.asset(
          'assets/recording/figma/$name',
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) => const SizedBox.shrink(),
        );

    return Scaffold(
      backgroundColor: Frame19Layout.bg,
      body: FigmaCanvas(
        background: Frame19Layout.bg,
        children: [
          // Centre Frame 19 graphic (back → front)
          FigmaChild.widget(Frame19Layout.ringGlow, img('frame19_ring_glow.png')),
          FigmaChild.widget(Frame19Layout.ringDark, img('frame19_ring_dark.png')),
          FigmaChild.widget(Frame19Layout.ringGradient, img('frame19_ring_gradient.png')),
          FigmaChild.widget(Frame19Layout.leftVec, img('frame19_vector_left.png')),
          FigmaChild.widget(Frame19Layout.rightVec, img('frame19_vector_right.png')),
          // Voice wavebar
          FigmaChild.widget(Frame19Layout.wavebar, Wavebar(controller: _wave)),
          // Timer
          FigmaChild(Frame19Layout.timer, (_, s) => Center(
                child: Text(
                  _hms,
                  style: TextStyle(
                    color: Frame19Layout.colWhite,
                    fontSize: s.font(Frame19Layout.timerFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          // Status caption
          FigmaChild(Frame19Layout.status, (_, s) => Center(
                child: Text(
                  _paused ? 'Recording paused' : 'Recording in progress',
                  style: TextStyle(
                    color: Frame19Layout.colMuted,
                    fontSize: s.font(Frame19Layout.statusFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          // Back button
          FigmaChild.widget(
            Frame19Layout.backBtn,
            GestureDetector(onTap: () => context.go('/home'), child: img('btn_back.png')),
          ),
          // Recording status dot
          FigmaChild(Frame19Layout.recDot, (_, __) => _StatusDot(recording: !_paused)),
          // "Recording..." label
          FigmaChild(Frame19Layout.recLabel, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _paused ? 'Paused' : 'Recording...',
                  style: TextStyle(
                    color: Frame19Layout.colWhite,
                    fontSize: s.font(Frame19Layout.recLabelFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          // "Started at ..." label
          FigmaChild(Frame19Layout.startedLabel, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Started at $_startedAt',
                  style: TextStyle(
                    color: Frame19Layout.colMuted,
                    fontSize: s.font(Frame19Layout.startedFsRatio),
                  ),
                ),
              )),
          // Bottom controls
          FigmaChild.widget(
            Frame19Layout.btnPause,
            GestureDetector(onTap: _onPause, child: img('btn_pause.png')),
          ),
          FigmaChild.widget(
            Frame19Layout.stopPill,
            GestureDetector(onTap: _stop, child: img('stop_recording_pill.png')),
          ),
          FigmaChild.widget(
            Frame19Layout.btnSettings,
            GestureDetector(
                onTap: () => context.push('/settings'), child: img('btn_settings.png')),
          ),
        ],
      ),
    );
  }
}

class _StatusDot extends StatefulWidget {
  const _StatusDot({required this.recording});
  final bool recording;

  @override
  State<_StatusDot> createState() => _StatusDotState();
}

class _StatusDotState extends State<_StatusDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _blink = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _blink.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.recording) {
      return const DecoratedBox(
        decoration: BoxDecoration(
          color: Frame19Layout.colRecDotGrey,
          shape: BoxShape.circle,
        ),
      );
    }
    return FadeTransition(
      opacity: Tween(begin: 0.45, end: 1.0).animate(_blink),
      child: const DecoratedBox(
        decoration: BoxDecoration(
          color: Frame19Layout.colRecDotRed,
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
