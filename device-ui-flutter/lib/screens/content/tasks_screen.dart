import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/action_item.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Tasks / commitments screen, ported from `screens/tasks.py`.
/// Groups commitments into Today, Upcoming, and Unplanned, with completion
/// toggles backed by PATCH /api/commitments/{id}.
class TasksScreen extends StatefulWidget {
  const TasksScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends State<TasksScreen> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final items = widget.config.mockBackend
        ? _mock()
        : await widget.api.getCommitments(limit: 100);
    if (!mounted) return;
    setState(() {
      _items = items;
      _loading = false;
    });
  }

  List<Map<String, dynamic>> _mock() => [
        {'id': '1', 'title': 'Send Q3 roadmap to leadership', 'due_date': 'today', 'status': 'active'},
        {'id': '2', 'title': 'Review onboarding spec', 'due_date': 'tomorrow', 'status': 'active'},
        {'id': '3', 'title': 'Book design review room', 'due_date': '', 'status': 'active'},
        {'id': '4', 'title': 'Reply to vendor email', 'due_date': 'today', 'status': 'completed'},
      ];

  bool _isToday(Map<String, dynamic> m) {
    final d = (m['due_date'] ?? '').toString().toLowerCase();
    return d.contains('today');
  }

  bool _isUpcoming(Map<String, dynamic> m) {
    final d = (m['due_date'] ?? '').toString();
    return d.isNotEmpty && !_isToday(m);
  }

  Future<void> _toggle(Map<String, dynamic> m, bool done) async {
    setState(() => m['status'] = done ? 'completed' : 'active');
    if (!widget.config.mockBackend) {
      await widget.api.patchCommitment(
        (m['id'] ?? '').toString(),
        status: done ? 'completed' : 'active',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final today = _items.where(_isToday).toList();
    final upcoming = _items.where(_isUpcoming).toList();
    final unplanned = _items
        .where((m) => !_isToday(m) && !_isUpcoming(m))
        .toList();

    return Scaffold(
      backgroundColor: AppColors.background,
      body: DeviceBackground(
        child: SafeArea(
          child: Column(
            children: [
              StatusBar(
                deviceName: 'Tasks',
                backButton: true,
                showSettings: false,
                onBack: () =>
                    context.canPop() ? context.pop() : context.go('/home'),
              ),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : _items.isEmpty
                        ? _empty()
                        : ListView(
                            padding: const EdgeInsets.all(Spacing.screenPadding),
                            children: [
                              _group('TODAY', today),
                              _group('UPCOMING', upcoming),
                              _group('UNPLANNED', unplanned),
                            ],
                          ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _empty() => const Center(
        child: Text('No tasks yet',
            style: TextStyle(color: AppColors.gray400, fontSize: 18)),
      );

  Widget _group(String title, List<Map<String, dynamic>> items) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 16, bottom: 8, left: 4),
          child: Text(
            title,
            style: const TextStyle(
              color: AppColors.gray400,
              fontSize: FontSizes.small,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.4,
            ),
          ),
        ),
        for (final m in items)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: const Color(0xDB1F2A3B),
              borderRadius: BorderRadius.circular(Layout.borderRadius),
            ),
            child: ActionItemWidget(
              task: (m['title'] ?? '').toString(),
              dueDate: (m['due_date'] ?? '').toString(),
              completed: (m['status'] ?? '') == 'completed',
              textColor: AppColors.white,
              onToggle: (v) => _toggle(m, v),
            ),
          ),
      ],
    );
  }
}
