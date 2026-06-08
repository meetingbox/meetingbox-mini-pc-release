import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';
import 'package:meetingbox_device_ui/core/layout/summary_layout.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';

/// Meeting summary review, ported from `screens/summary_review.py` +
/// `summary_layout.py`. Light theme, sidebar tab navigation, content area.
class SummaryReviewScreen extends StatefulWidget {
  const SummaryReviewScreen({
    super.key,
    required this.config,
    required this.api,
    this.meetingId,
  });

  final AppConfig config;
  final ApiClient api;
  final String? meetingId;

  @override
  State<SummaryReviewScreen> createState() => _SummaryReviewScreenState();
}

class _SummaryReviewScreenState extends State<SummaryReviewScreen> {
  static const _tabs = [
    'Overview',
    'Action Items',
    'Key Points',
    'Decisions',
    'Transcript',
    'Participants',
  ];

  int _tab = 0;
  Map<String, dynamic> _meeting = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final m = widget.config.mockBackend || widget.meetingId == null
        ? _mock()
        : await widget.api.getMeetingDetail(widget.meetingId!);
    if (!mounted) return;
    setState(() {
      _meeting = m;
      _loading = false;
    });
  }

  Map<String, dynamic> _mock() => {
        'title': 'Product Sync',
        'date': 'Today, 10:00 AM',
        'summary': {
          'overview': 'The team aligned on the Q3 roadmap and prioritized the '
              'onboarding revamp ahead of the analytics work.',
          'key_points': ['Q3 roadmap locked', 'Onboarding revamp first', 'Analytics deferred'],
          'action_items': [
            {'task': 'Draft onboarding spec', 'assignee': 'Alex', 'due_date': 'Fri'},
            {'task': 'Schedule design review', 'assignee': 'Sam'},
          ],
          'decisions': ['Ship onboarding before analytics', 'Weekly syncs on Monday'],
        },
        'participants': ['Alex', 'Sam', 'Jordan'],
      };

  Map<String, dynamic> get _summary =>
      (_meeting['summary'] as Map<String, dynamic>?) ?? {};

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        backgroundColor: SummaryLayout.bg,
        body: Center(child: CircularProgressIndicator()),
      );
    }
    final title = (_meeting['title'] ?? 'Meeting summary').toString();
    final date = (_meeting['date'] ?? '').toString();

    return Scaffold(
      backgroundColor: SummaryLayout.bg,
      body: FigmaCanvas(
        background: SummaryLayout.bg,
        children: [
          // Topbar
          FigmaChild.widget(
            SummaryLayout.topbar,
            const ColoredBox(color: SummaryLayout.cardFill),
          ),
          FigmaChild.widget(
            SummaryLayout.backBtn,
            GestureDetector(
              onTap: () => context.canPop() ? context.pop() : context.go('/home'),
              child: const Icon(Icons.arrow_back, color: SummaryLayout.colWhite),
            ),
          ),
          FigmaChild(SummaryLayout.pageTitle, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Meeting Summary',
                  style: TextStyle(
                    color: SummaryLayout.colWhite,
                    fontSize: s.font(SummaryLayout.pageTitleFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          // Meta card
          FigmaChild.widget(
            SummaryLayout.metaCard,
            const DecoratedBox(
              decoration: BoxDecoration(
                color: SummaryLayout.cardFill,
                border: Border(bottom: BorderSide(color: SummaryLayout.cardBorder)),
              ),
            ),
          ),
          FigmaChild.widget(
            SummaryLayout.metaFileIcon,
            const Icon(Icons.description, color: SummaryLayout.accentBlue, size: 40),
          ),
          FigmaChild(SummaryLayout.metaTitle, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  title,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: SummaryLayout.colWhite,
                    fontSize: s.font(SummaryLayout.metaTitleFsRatio),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              )),
          FigmaChild(SummaryLayout.metaDate, (_, s) => Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  date,
                  style: TextStyle(
                    color: SummaryLayout.colHint,
                    fontSize: s.font(SummaryLayout.metaDateFsRatio),
                  ),
                ),
              )),
          // Sidebar
          FigmaChild.widget(
            SummaryLayout.sidebarCard,
            Container(
              decoration: BoxDecoration(
                color: SummaryLayout.sidebarFill,
                borderRadius: BorderRadius.circular(SummaryLayout.cardRadius),
                border: Border.all(color: SummaryLayout.sidebarBorder),
              ),
            ),
          ),
          for (var i = 0; i < _tabs.length; i++)
            FigmaChild(SummaryLayout.tab(i), (_, s) => _tabButton(i, s)),
          // Content
          FigmaChild.widget(
            SummaryLayout.fullTabCard,
            Container(
              decoration: BoxDecoration(
                color: SummaryLayout.cardFill,
                borderRadius: BorderRadius.circular(SummaryLayout.cardRadius),
                border: Border.all(color: SummaryLayout.cardBorder),
              ),
              padding: const EdgeInsets.all(24),
              child: _content(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _tabButton(int i, FigmaScale s) {
    final active = i == _tab;
    return GestureDetector(
      onTap: () => setState(() => _tab = i),
      child: Container(
        decoration: BoxDecoration(
          color: active ? SummaryLayout.tabActiveFill : null,
          borderRadius: BorderRadius.circular(SummaryLayout.tabActiveRadius),
          border: active ? Border.all(color: SummaryLayout.tabActiveBorder) : null,
        ),
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Text(
          _tabs[i],
          style: TextStyle(
            color: active ? SummaryLayout.accentBlue : SummaryLayout.colWhite,
            fontSize: s.font(SummaryLayout.tabFsRatio),
            fontWeight: active ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _content() {
    switch (_tab) {
      case 1:
        return _actionItemsView();
      case 2:
        return _bulletView('Key Points', (_summary['key_points'] as List?) ?? []);
      case 3:
        return _bulletView('Decisions', (_summary['decisions'] as List?) ?? []);
      case 4:
        return _textView('Transcript',
            (_meeting['transcript'] ?? 'Transcript not available.').toString());
      case 5:
        return _bulletView('Participants', (_meeting['participants'] as List?) ?? []);
      default:
        return _overviewView();
    }
  }

  Widget _sectionTitle(String t) => Text(
        t,
        style: const TextStyle(
          color: SummaryLayout.colWhite,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
      );

  Widget _overviewView() {
    final overview = (_summary['overview'] ?? 'No summary available.').toString();
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionTitle('AI Summary'),
          const SizedBox(height: 8),
          Text(overview, style: const TextStyle(color: SummaryLayout.colMuted, fontSize: 15)),
          const SizedBox(height: 20),
          _sectionTitle('Key Points'),
          const SizedBox(height: 8),
          ...(((_summary['key_points'] as List?) ?? []).map(_bullet)),
          const SizedBox(height: 20),
          _sectionTitle('Action Items'),
          const SizedBox(height: 8),
          _actionItemsView(),
        ],
      ),
    );
  }

  Widget _actionItemsView() {
    final items = (_summary['action_items'] as List?) ?? [];
    if (items.isEmpty) {
      return const Text('No action items.', style: TextStyle(color: SummaryLayout.colHint));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final it in items)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.check_box_outline_blank,
                    color: SummaryLayout.accentBlue, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _actionText(it),
                    style: const TextStyle(color: SummaryLayout.colMuted, fontSize: 15),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  String _actionText(dynamic it) {
    if (it is Map) {
      final task = (it['task'] ?? '').toString();
      final who = (it['assignee'] ?? '').toString();
      final due = (it['due_date'] ?? '').toString();
      final meta = [if (who.isNotEmpty) who, if (due.isNotEmpty) due].join(' · ');
      return meta.isEmpty ? task : '$task  ($meta)';
    }
    return it.toString();
  }

  Widget _bulletView(String title, List items) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionTitle(title),
          const SizedBox(height: 8),
          if (items.isEmpty)
            const Text('Nothing here yet.', style: TextStyle(color: SummaryLayout.colHint))
          else
            ...items.map(_bullet),
        ],
      ),
    );
  }

  Widget _bullet(dynamic v) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('•  ', style: TextStyle(color: SummaryLayout.accentBlue, fontSize: 15)),
            Expanded(
              child: Text(v.toString(),
                  style: const TextStyle(color: SummaryLayout.colMuted, fontSize: 15)),
            ),
          ],
        ),
      );

  Widget _textView(String title, String body) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionTitle(title),
          const SizedBox(height: 8),
          Text(body, style: const TextStyle(color: SummaryLayout.colMuted, fontSize: 15)),
        ],
      ),
    );
  }
}
