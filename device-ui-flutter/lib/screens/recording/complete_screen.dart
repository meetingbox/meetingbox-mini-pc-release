import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Ported from `screens/complete.py`. Confirmation + auto-return to home.
class CompleteScreen extends StatefulWidget {
  const CompleteScreen({
    super.key,
    required this.config,
    required this.api,
    this.meetingId,
  });

  final AppConfig config;
  final ApiClient api;
  final String? meetingId;

  @override
  State<CompleteScreen> createState() => _CompleteScreenState();
}

class _CompleteScreenState extends State<CompleteScreen> {
  String _info = '';
  String _stats = '';

  @override
  void initState() {
    super.initState();
    _load();
    Future<void>.delayed(Motion.autoReturn, _goHome);
  }

  Future<void> _load() async {
    if (widget.meetingId == null || widget.config.mockBackend) return;
    final m = await widget.api.getMeetingDetail(widget.meetingId!);
    if (!mounted || m.isEmpty) return;
    final title = (m['title'] ?? 'Untitled').toString();
    final dur = ((m['duration'] as num?) ?? 0) ~/ 60;
    final summary = m['summary'] as Map<String, dynamic>? ?? {};
    final ac = (summary['action_items'] as List?)?.length ?? 0;
    final dc = (summary['decisions'] as List?)?.length ?? 0;
    setState(() {
      _info = '$title · $dur minutes';
      _stats = [
        if (ac > 0) '• $ac action item${ac != 1 ? 's' : ''}',
        if (dc > 0) '• $dc decision${dc != 1 ? 's' : ''} made',
        '• Meeting report ready',
      ].join('\n');
    });
  }

  void _goHome() {
    if (mounted) context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: GestureDetector(
        onTap: _goHome,
        child: DeviceBackground(
          child: Column(
            children: [
              const StatusBar(
                statusText: 'COMPLETE',
                statusColor: AppColors.green,
                showSettings: true,
              ),
              const Spacer(flex: 1),
              const Icon(Icons.check_circle, color: AppColors.green, size: 72),
              const SizedBox(height: 12),
              const Text(
                'Meeting Saved!',
                style: TextStyle(
                  color: AppColors.white,
                  fontSize: FontSizes.large,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (_info.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  _info,
                  style: const TextStyle(
                    color: AppColors.white,
                    fontSize: FontSizes.medium,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const SizedBox(height: 12),
              Text(
                _stats,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.gray500, fontSize: FontSizes.small + 2),
              ),
              const Spacer(flex: 2),
            ],
          ),
        ),
      ),
    );
  }
}
