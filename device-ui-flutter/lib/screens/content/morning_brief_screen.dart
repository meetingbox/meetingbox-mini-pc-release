import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Morning brief, ported from `screens/morning_brief.py`. Pulls the briefing
/// context (calendar slice, tasks, gmail preview) and renders a daily summary.
class MorningBriefScreen extends StatefulWidget {
  const MorningBriefScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<MorningBriefScreen> createState() => _MorningBriefScreenState();
}

class _MorningBriefScreenState extends State<MorningBriefScreen> {
  Map<String, dynamic> _ctx = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final ctx = widget.config.mockBackend
        ? _mock()
        : await widget.api.getBriefingContext(daysAhead: 1);
    if (!mounted) return;
    setState(() {
      _ctx = ctx;
      _loading = false;
    });
  }

  Map<String, dynamic> _mock() => {
        'weather': {'temp': '21°', 'condition': 'Partly cloudy', 'humidity': '54%', 'wind': '12 km/h'},
        'meetings': [
          {'title': 'Product Sync', 'start': '10:00'},
          {'title': 'Design Review', 'start': '14:00'},
        ],
        'tasks': [
          {'title': 'Send Q3 roadmap'},
          {'title': 'Review onboarding spec'},
        ],
        'emails': [
          {'from': 'Alex Rivera', 'subject': 'Q3 roadmap review'},
          {'from': 'Sam Park', 'subject': 'Design review notes'},
        ],
      };

  String get _greeting {
    final h = DateTime.now().hour;
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DeviceBackground(
        child: SafeArea(
          child: Column(
            children: [
              StatusBar(
                deviceName: 'Morning Brief',
                backButton: true,
                showSettings: false,
                onBack: () =>
                    context.canPop() ? context.pop() : context.go('/home'),
              ),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : ListView(
                        padding: const EdgeInsets.all(Spacing.screenPadding),
                        children: [
                          Text(_greeting,
                              style: const TextStyle(
                                  color: AppColors.white,
                                  fontSize: 28,
                                  fontWeight: FontWeight.w700)),
                          const SizedBox(height: 4),
                          Text(_today(),
                              style: const TextStyle(
                                  color: AppColors.gray400, fontSize: 14)),
                          const SizedBox(height: 16),
                          _weatherCard(),
                          const SizedBox(height: 12),
                          _listCard('TODAY\'S MEETINGS',
                              (_ctx['meetings'] as List?) ?? [],
                              (m) => '${(m['start'] ?? '').toString()}  ${(m['title'] ?? '').toString()}'),
                          const SizedBox(height: 12),
                          _listCard('TASKS', (_ctx['tasks'] as List?) ?? [],
                              (t) => (t['title'] ?? '').toString()),
                          const SizedBox(height: 12),
                          _listCard('RECENT EMAILS',
                              (_ctx['emails'] as List?) ?? [],
                              (e) => '${(e['from'] ?? '').toString()} — ${(e['subject'] ?? '').toString()}'),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _today() {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    final n = DateTime.now();
    return '${months[n.month - 1]} ${n.day}, ${n.year}';
  }

  Widget _card({required Widget child}) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xDB1F2A3B),
          borderRadius: BorderRadius.circular(Layout.borderRadius),
        ),
        child: child,
      );

  Widget _weatherCard() {
    final w = (_ctx['weather'] as Map?) ?? {};
    if (w.isEmpty) return const SizedBox.shrink();
    return _card(
      child: Row(
        children: [
          Text((w['temp'] ?? '--').toString(),
              style: const TextStyle(
                  color: AppColors.white,
                  fontSize: 40,
                  fontWeight: FontWeight.w700)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text((w['condition'] ?? '').toString(),
                    style: const TextStyle(
                        color: AppColors.white, fontSize: 16)),
                const SizedBox(height: 4),
                Text(
                  'Humidity ${(w['humidity'] ?? '--').toString()}  ·  Wind ${(w['wind'] ?? '--').toString()}',
                  style: const TextStyle(
                      color: AppColors.gray400, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _listCard(
      String title, List items, String Function(dynamic) format) {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: AppColors.gray400,
                  fontSize: FontSizes.small,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2)),
          const SizedBox(height: 10),
          if (items.isEmpty)
            const Text('Nothing scheduled',
                style: TextStyle(color: AppColors.gray500, fontSize: 14))
          else
            ...items.map((it) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('•  ',
                          style: TextStyle(
                              color: AppColors.primaryStart, fontSize: 15)),
                      Expanded(
                        child: Text(format(it),
                            style: const TextStyle(
                                color: AppColors.gray300, fontSize: 14)),
                      ),
                    ],
                  ),
                )),
        ],
      ),
    );
  }
}
