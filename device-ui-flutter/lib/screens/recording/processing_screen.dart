import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';
import 'package:meetingbox_device_ui/core/layout/processing_layout.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';

/// Processing screen ported from `screens/processing.py` + `processing_layout.py`.
/// Polls the backend for the meeting summary; the three stage rows tick through
/// and the bottom bar flips to a "View Meeting Summary" CTA when ready.
class ProcessingScreen extends StatefulWidget {
  const ProcessingScreen({
    super.key,
    required this.config,
    required this.api,
    this.meetingId,
  });

  final AppConfig config;
  final ApiClient api;
  final String? meetingId;

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen> {
  static const _stages = [
    'Extracting key points',
    'Identifying action items',
    'Structuring summary',
  ];

  Timer? _poll;
  int _activeStage = 0;
  bool _ready = false;
  String _title = 'Your meeting';
  String _duration = '';

  @override
  void initState() {
    super.initState();
    _tickStages();
    _startPolling();
  }

  void _tickStages() {
    _poll = Timer.periodic(const Duration(seconds: 2), (t) {
      if (!mounted) return;
      setState(() {
        if (_activeStage < _stages.length - 1) _activeStage++;
      });
    });
  }

  Future<void> _startPolling() async {
    if (widget.config.mockBackend || widget.meetingId == null) {
      await Future<void>.delayed(const Duration(seconds: 6));
      if (mounted) setState(() => _ready = true);
      return;
    }
    Timer.periodic(const Duration(seconds: 3), (t) async {
      final detail = await widget.api.getMeetingDetail(widget.meetingId!);
      if (!mounted) return;
      final summary = detail['summary'];
      final title = detail['title'];
      if (title is String && title.isNotEmpty) _title = title;
      final dur = detail['duration'];
      if (dur is num && dur > 0) _duration = '${dur ~/ 60}min';
      if (summary is Map && summary.isNotEmpty) {
        t.cancel();
        setState(() => _ready = true);
      } else {
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Widget _img(String name) => Image.asset(
        'assets/processing/figma/$name',
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
      );

  List<FigmaChild> _stageRows() {
    final rows = <FigmaChild>[];
    for (var i = 0; i < _stages.length; i++) {
      final (icon, label, status) = ProcessingLayout.stageRow(i);
      final done = i < _activeStage || _ready;
      final active = i == _activeStage && !_ready;
      rows.add(FigmaChild.widget(
        icon,
        _img(done
            ? 'icon_step_done.png'
            : active
                ? 'icon_step_active.png'
                : 'icon_step_pending.png'),
      ));
      rows.add(FigmaChild(label, (_, s) => Align(
            alignment: Alignment.centerLeft,
            child: Text(
              _stages[i],
              style: TextStyle(
                color: done || active
                    ? ProcessingLayout.colWhite
                    : ProcessingLayout.colHint,
                fontSize: s.font(ProcessingLayout.stageFsRatio),
              ),
            ),
          )));
      rows.add(FigmaChild.widget(
        status,
        done
            ? _img('icon_check_tick.png')
            : active
                ? _img('icon_loading.png')
                : const SizedBox.shrink(),
      ));
    }
    return rows;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProcessingLayout.bg,
      body: FigmaCanvas(
        background: ProcessingLayout.bg,
        children: [
          FigmaChild.widget(
            ProcessingLayout.backBtn,
            GestureDetector(onTap: () => context.go('/home'), child: _img('btn_back.png')),
          ),
          FigmaChild.widget(
            ProcessingLayout.settingsBtn,
            GestureDetector(onTap: () => context.push('/settings'), child: _img('btn_settings.png')),
          ),
          // Orb
          FigmaChild.widget(ProcessingLayout.glowOuter, _img('glow_orb_outer.png')),
          FigmaChild.widget(ProcessingLayout.ringSolid, _img('ring_solid.png')),
          FigmaChild.widget(ProcessingLayout.ringOuter, _img('ring_outer.png')),
          // Header
          FigmaChild.widget(ProcessingLayout.checkBadge, _img('check_badge.png')),
          FigmaChild(ProcessingLayout.headlineLabel, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Recording complete',
                  style: TextStyle(
                    color: ProcessingLayout.colWhite,
                    fontSize: s.font(ProcessingLayout.headlineFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          FigmaChild(ProcessingLayout.titleLabel, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _title,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: ProcessingLayout.colWhite,
                    fontSize: s.font(ProcessingLayout.titleFsRatio),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              )),
          if (_duration.isNotEmpty)
            FigmaChild(ProcessingLayout.durationLabel, (_, s) => Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    _duration,
                    style: TextStyle(
                      color: ProcessingLayout.colMuted,
                      fontSize: s.font(ProcessingLayout.durationFsRatio),
                    ),
                  ),
                )),
          // Bottom captions
          FigmaChild(ProcessingLayout.headlineBottom, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _ready ? 'Summary ready' : 'Summarizing your meeting…',
                  style: TextStyle(
                    color: ProcessingLayout.colWhite,
                    fontSize: s.font(ProcessingLayout.headlineFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          FigmaChild(ProcessingLayout.subtitleBottom, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _ready ? 'Tap below to review' : 'This may take a few seconds',
                  style: TextStyle(
                    color: ProcessingLayout.colMuted,
                    fontSize: s.font(ProcessingLayout.subtitleFsRatio),
                  ),
                ),
              )),
          // Steps card + rows
          FigmaChild.widget(ProcessingLayout.stepsCard, _img('steps_card.png')),
          ..._stageRows(),
          // Notify bar / CTA
          FigmaChild.widget(
            ProcessingLayout.notifyBar,
            GestureDetector(
              onTap: _ready
                  ? () => context.go('/summary-review', extra: widget.meetingId)
                  : null,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  _img('notify_bar.png'),
                  Center(
                    child: Text(
                      _ready ? 'View Meeting Summary' : "We'll notify you when it's ready",
                      style: TextStyle(
                        color: _ready ? ProcessingLayout.colWhite : ProcessingLayout.colHint,
                        fontSize: 22,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
