import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Weekly calendar, ported from `screens/calendar.py`. Shows a 7-day selector
/// and the meetings for the selected day from GET /api/calendar/week.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  static const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  late DateTime _weekStart;
  late DateTime _selected;
  Map<String, List<Map<String, dynamic>>> _byDate = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _weekStart = now.subtract(Duration(days: now.weekday - 1));
    _selected = DateTime(now.year, now.month, now.day);
    _load();
  }

  String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _load() async {
    setState(() => _loading = true);
    final end = _weekStart.add(const Duration(days: 6));
    final Map<String, dynamic> data = widget.config.mockBackend
        ? _mock()
        : await widget.api.getCalendarWeek(_iso(_weekStart), _iso(end));
    final days = (data['days'] as Map?) ?? {};
    final parsed = <String, List<Map<String, dynamic>>>{};
    days.forEach((k, v) {
      final meetings = (v is Map ? v['meetings'] : v) as List? ?? [];
      parsed[k.toString()] = meetings.cast<Map<String, dynamic>>();
    });
    if (!mounted) return;
    setState(() {
      _byDate = parsed;
      _loading = false;
    });
  }

  Map<String, dynamic> _mock() {
    final today = DateTime.now();
    return {
      'days': {
        _iso(DateTime(today.year, today.month, today.day)): {
          'meetings': [
            {'title': 'Product Sync', 'start': '10:00', 'end': '10:30'},
            {'title': 'Design Review', 'start': '14:00', 'end': '15:00'},
          ],
        },
        _iso(today.add(const Duration(days: 1))): {
          'meetings': [
            {'title': '1:1 with Sam', 'start': '11:00', 'end': '11:30'},
          ],
        },
      },
    };
  }

  void _shiftWeek(int weeks) {
    setState(() => _weekStart = _weekStart.add(Duration(days: 7 * weeks)));
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final meetings = _byDate[_iso(_selected)] ?? [];
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DeviceBackground(
        child: SafeArea(
          child: Column(
            children: [
              StatusBar(
                deviceName: 'Calendar',
                backButton: true,
                showSettings: false,
                onBack: () =>
                    context.canPop() ? context.pop() : context.go('/home'),
              ),
              _weekHeader(),
              _daySelector(),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : meetings.isEmpty
                        ? const Center(
                            child: Text('No meetings this day',
                                style: TextStyle(
                                    color: AppColors.gray400, fontSize: 16)))
                        : ListView.separated(
                            padding:
                                const EdgeInsets.all(Spacing.screenPadding),
                            itemCount: meetings.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 8),
                            itemBuilder: (_, i) => _meetingRow(meetings[i]),
                          ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _weekHeader() {
    final end = _weekStart.add(const Duration(days: 6));
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          IconButton(
            onPressed: () => _shiftWeek(-1),
            icon: const Icon(Icons.chevron_left, color: AppColors.white),
          ),
          Expanded(
            child: Text(
              '${_weekStart.day}/${_weekStart.month} – ${end.day}/${end.month}',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.white,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          IconButton(
            onPressed: () => _shiftWeek(1),
            icon: const Icon(Icons.chevron_right, color: AppColors.white),
          ),
        ],
      ),
    );
  }

  Widget _daySelector() {
    return SizedBox(
      height: 70,
      child: Row(
        children: List.generate(7, (i) {
          final day = _weekStart.add(Duration(days: i));
          final active = _iso(day) == _iso(_selected);
          final has = (_byDate[_iso(day)] ?? []).isNotEmpty;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _selected = day),
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 3),
                decoration: BoxDecoration(
                  color: active ? AppColors.primaryStart : const Color(0xDB1F2A3B),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(_weekdays[i],
                        style: TextStyle(
                            color: active ? Colors.white : AppColors.gray400,
                            fontSize: 12)),
                    const SizedBox(height: 4),
                    Text('${day.day}',
                        style: TextStyle(
                            color: active ? Colors.white : AppColors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Container(
                      width: 5,
                      height: 5,
                      decoration: BoxDecoration(
                        color: has
                            ? (active ? Colors.white : AppColors.primaryStart)
                            : Colors.transparent,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _meetingRow(Map<String, dynamic> m) {
    final start = (m['start'] ?? '').toString();
    final end = (m['end'] ?? '').toString();
    final time = end.isEmpty ? start : '$start – $end';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xDB1F2A3B),
        borderRadius: BorderRadius.circular(Layout.borderRadius),
        border: const Border(
          left: BorderSide(color: AppColors.primaryStart, width: 4),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text((m['title'] ?? 'Untitled').toString(),
                    style: const TextStyle(
                        color: AppColors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600)),
                if (time.trim().isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(time,
                      style: const TextStyle(
                          color: AppColors.gray300, fontSize: 13)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
