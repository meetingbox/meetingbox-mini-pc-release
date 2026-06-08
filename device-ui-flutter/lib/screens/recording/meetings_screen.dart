import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/meeting_card.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Ported from `screens/meetings.py`. Meeting library list.
class MeetingsScreen extends StatefulWidget {
  const MeetingsScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<MeetingsScreen> createState() => _MeetingsScreenState();
}

class _MeetingsScreenState extends State<MeetingsScreen> {
  List<Map<String, dynamic>> _meetings = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final m = widget.config.mockBackend
        ? _mock()
        : await widget.api.listMeetings(limit: 20);
    if (!mounted) return;
    setState(() {
      _meetings = m;
      _loading = false;
    });
  }

  List<Map<String, dynamic>> _mock() => [
        {
          'id': '1',
          'title': 'Product Sync',
          'start_time': DateTime.now().subtract(const Duration(hours: 1)).toIso8601String(),
          'duration': 1920,
          'pending_actions': 2,
        },
        {
          'id': '2',
          'title': 'Design Review',
          'start_time': DateTime.now().subtract(const Duration(days: 1)).toIso8601String(),
          'duration': 2700,
          'pending_actions': 0,
        },
      ];

  String _meta(Map<String, dynamic> m) {
    final raw = (m['start_time'] ?? m['created_at'] ?? '').toString();
    String ago = '';
    try {
      final start = DateTime.parse(raw.endsWith('Z')
              ? raw.replaceFirst('Z', '+00:00')
              : raw)
          .toLocal();
      final delta = DateTime.now().difference(start);
      if (delta.inHours < 1) {
        ago = '${delta.inMinutes} min ago';
      } else if (delta.inDays < 1) {
        ago = '${delta.inHours} hr ago';
      } else {
        ago = '${delta.inDays} days ago';
      }
    } catch (_) {
      ago = DateFormat('MMM d').format(DateTime.now());
    }
    final dur = (m['duration'] as num?)?.toInt() ?? 0;
    return dur > 0 ? '$ago · ${dur ~/ 60} min' : ago;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DeviceBackground(
        child: Column(
          children: [
            StatusBar(
              statusText: 'Meetings',
              deviceName: 'Meeting Library',
              backButton: true,
              onBack: () => context.pop(),
              onSettings: () => context.push('/settings'),
            ),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _meetings.isEmpty
                      ? const Center(
                          child: Text(
                            'No meetings yet. Start a recording to create one.',
                            style: TextStyle(color: AppColors.gray300),
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.all(16),
                          itemCount: _meetings.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 8),
                          itemBuilder: (_, i) {
                            final m = _meetings[i];
                            return MeetingCard(
                              title: (m['title'] ?? 'Untitled').toString(),
                              meta: _meta(m),
                              pendingActions:
                                  (m['pending_actions'] as num?)?.toInt() ?? 0,
                              onPressed: () => context.push(
                                '/meeting-detail',
                                extra: (m['id'] ?? '').toString(),
                              ),
                            );
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
