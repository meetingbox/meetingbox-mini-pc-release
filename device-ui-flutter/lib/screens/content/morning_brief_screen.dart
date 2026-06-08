import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';

// ── Colours — ported 1:1 from screens/morning_brief.py ──────────────────────
const _cBg = Color(0xFF01081A);
const _cWhite = Color(0xFFFFFFFF);
const _cMuted = Color(0xFFB6BAF2);
const _cDim = Color(0xFF9BA2B2);
const _cBlue = Color(0xFF006BF9);
const _cBlue2 = Color(0xFF3481F1);
const _cGreen = Color(0xFF19D385);
const _cPurple = Color(0xFFA971D4);
const _cCardTop = Color(0xFF02123C);
const _cCardBot = Color(0xFF000A26);
const _cSchTop = Color(0xFF011137);
const _cBdr = Color(0xFF3F4253);
const _cDot = Color(0xFF467DFE);
const _cDivider = Color(0xD902174D); // #02174D @ 0.85

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// Morning Brief — rebuilt to match `screens/morning_brief.py` (Figma 927:220,
/// 1260×800). Header greeting, weather card, today's schedule, tasks overview,
/// and a recent-emails row, wired to GET /api/briefing/context.
class MorningBriefScreen extends StatefulWidget {
  const MorningBriefScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<MorningBriefScreen> createState() => _MorningBriefScreenState();
}

class _MorningBriefScreenState extends State<MorningBriefScreen> {
  static const _canvas = Size(1260, 800);

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

  Map<String, dynamic> _mock() {
    final today = DateTime.now();
    final iso = _isoDate(today);
    return {
      'greeting': 'Good morning',
      'user_display_name': 'J. K',
      'today': iso,
      'days': {
        iso: {
          'meetings': [
            {'title': 'Product Sync', 'start': '${iso}T10:00:00', 'duration': 1800},
            {'title': 'Design Review', 'start': '${iso}T14:00:00', 'duration': 3600},
          ],
        },
      },
      'commitments': [
        {'title': 'Send Q3 roadmap', 'status': 'active', 'due_at': '${iso}T17:00:00'},
        {'title': 'Review onboarding spec', 'status': 'active', 'due_at': _isoDate(today.add(const Duration(days: 2)))},
        {'title': 'Book room', 'status': 'active'},
      ],
      'gmail_preview': {
        'connected': true,
        'top': {'from': 'Alex Rivera <alex@acme.io>', 'subject': 'Q3 roadmap review', 'snippet': 'Here is the draft', 'date': '9:24 AM'},
      },
    };
  }

  static String _isoDate(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  static String _firstName(String? dn) {
    final s = (dn ?? '').trim();
    if (s.isEmpty) return 'there';
    return s.split(RegExp(r'\s+')).first;
  }

  static String _ampm(DateTime dt) {
    final am = dt.hour < 12 ? 'AM' : 'PM';
    var h = dt.hour % 12;
    if (h == 0) h = 12;
    return '$h:${dt.minute.toString().padLeft(2, '0')} $am';
  }

  static DateTime? _parse(String? s) {
    if (s == null || s.isEmpty) return null;
    try {
      return DateTime.parse(s.replaceAll('Z', '+00:00')).toLocal();
    } catch (_) {
      return null;
    }
  }

  // ── Derived data ──────────────────────────────────────────────────────────

  String get _greetingText {
    final greet = (_ctx['greeting'] ?? 'Hello').toString().trim();
    return '$greet, ${_firstName(_ctx['user_display_name']?.toString())}';
  }

  String get _subtitleText {
    var todayS = (_ctx['today'] ?? '').toString().trim();
    if (todayS.isEmpty) todayS = _isoDate(DateTime.now());
    String nice;
    try {
      final td = DateTime.parse(todayS);
      nice = '${td.day} ${_months[td.month - 1]}';
    } catch (_) {
      nice = todayS;
    }
    return "Here's your overview for today, $nice";
  }

  List<Map<String, dynamic>> get _meetings {
    final todayS = (_ctx['today'] ?? '').toString();
    final days = (_ctx['days'] as Map?) ?? {};
    final day = (days[todayS] as Map?) ?? {};
    final m = (day['meetings'] as List?) ?? [];
    return m.cast<Map<String, dynamic>>();
  }

  /// Returns (dueToday, upcoming, unplanned, nextTitle).
  (int, int, int, String) get _taskCounts {
    final todayS = (_ctx['today'] ?? _isoDate(DateTime.now())).toString();
    DateTime today;
    try {
      today = DateTime.parse(todayS);
    } catch (_) {
      today = DateTime.now();
    }
    final todayD = DateTime(today.year, today.month, today.day);
    var due = 0, up = 0, un = 0;
    var next = 'No upcoming';
    for (final r in ((_ctx['commitments'] as List?) ?? [])) {
      if (r is! Map) continue;
      final status = (r['status'] ?? '').toString();
      if (status != 'active' && status != 'snoozed') continue;
      final da = (r['due_at'] ?? r['remind_at'] ?? '').toString().trim();
      if (da.isEmpty) {
        un++;
        continue;
      }
      DateTime? dp;
      try {
        dp = da.contains('T')
            ? DateTime.parse(da.replaceAll('Z', '+00:00')).toLocal()
            : DateTime.parse(da.substring(0, 10));
      } catch (_) {
        un++;
        continue;
      }
      final dpd = DateTime(dp.year, dp.month, dp.day);
      if (dpd == todayD) {
        due++;
      } else if (dpd.isAfter(todayD)) {
        up++;
        if (next == 'No upcoming') {
          next = (r['title'] ?? 'Task').toString();
        }
      } else {
        up++;
      }
    }
    return (due, up, un, next);
  }

  Map<String, dynamic>? get _topEmail {
    final g = (_ctx['gmail_preview'] as Map?) ?? {};
    final top = g['top'];
    return top is Map ? top.cast<String, dynamic>() : null;
  }

  bool get _gmailConnected {
    final g = (_ctx['gmail_preview'] as Map?) ?? {};
    return g['connected'] == true;
  }

  // ── Build ───────────────────────────────────────────────────────────────

  double ff(double x) => x * 1.2;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _cBg,
      body: Center(
        child: FittedBox(
          fit: BoxFit.contain,
          child: SizedBox.fromSize(
            size: _canvas,
            child: Stack(
              children: [
                const ColoredBox(color: _cBg),
                // Back button
                _pos(24.02, 21.19, 76.28, 76.28,
                    GestureDetector(
                      onTap: () => context.canPop()
                          ? context.pop()
                          : context.go('/home'),
                      child: _asset('assets/calendar/figma/btn_back.png'),
                    )),
                _txt(118.66, 21.19, 320, 50, 'Morning Brief',
                    ff(38.14), _cWhite, FontWeight.w600),
                _txt(118.66, 63, 380, 32, _greetingText, 22.6, _cBlue2,
                    FontWeight.w600),
                _txt(118.66, 98, 700, 32,
                    _loading ? 'Loading your overview…' : _subtitleText,
                    ff(21.19), _cMuted, FontWeight.w600),
                _weatherCard(),
                _scheduleCard(),
                _tasksCard(),
                _emailCard(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── Weather card ──────────────────────────────────────────────────────────
  Widget _weatherCard() {
    const cx = 22.6, cy = 132.78, cw = 1214.8, ch = 185.04;
    return _card(cx, cy, cw, ch, ff(22.6), _cCardTop, _cCardBot,
      children: [
        _txt(35.31, 20, 220, 32, 'Weather Update', ff(21.19), _cWhite,
            FontWeight.w600),
        _pos(29.66, 72.04, 79.1, 79.1,
            _asset('assets/brief/figma/weather_cloud.png')),
        _txt(128.54, 62.15, 100, 42, '—°', ff(35.31), _cWhite, FontWeight.w700),
        _txt(128.54, 104.53, 200, 32, '…', ff(21.19), _cDim, FontWeight.w600),
        _pos(128.54, 137.01, 19.78, 19.78,
            _asset('assets/brief/figma/icon_location.png')),
        _txt(151.14, 134.19, 240, 32, '—', ff(21.19), _cMuted, FontWeight.w600),
        for (final dx in [387.04, 591.86, 796.68, 1001.5])
          _pos(dx, 35.32, 2.83, 115.83, const ColoredBox(color: _cDivider)),
        // High / Low
        _pos(413.88, 64.98, 31.08, 31.08,
            _asset('assets/brief/figma/icon_temperature.png')),
        _txt(450.61, 63.57, 140, 38, '— / —', ff(26.84), _cWhite,
            FontWeight.w700),
        _txt(463.32, 103.12, 90, 26, 'High / Low', ff(16.95), _cMuted,
            FontWeight.w600),
        // Humidity
        _pos(644.13, 66.39, 28.25, 28.25,
            _asset('assets/brief/figma/icon_humidity.png')),
        _txt(678.03, 63.57, 90, 38, '—%', ff(26.84), _cWhite, FontWeight.w700),
        _txt(658.26, 103.12, 90, 26, 'Humidity', ff(16.95), _cMuted,
            FontWeight.w600),
        // Wind
        _pos(827.76, 64.28, 35.31, 35.31,
            _asset('assets/brief/figma/icon_wind.png')),
        _txt(875.08, 63.57, 130, 38, '—', ff(26.84), _cWhite, FontWeight.w700),
        _txt(896.27, 103.12, 60, 26, 'Wind', ff(16.95), _cMuted,
            FontWeight.w600),
        // AQI
        _txt(1063.66, 66.39, 150, 38, 'AQI —', ff(26.84), _cWhite,
            FontWeight.w700),
        _txt(1091.91, 105.94, 90, 26, '—', ff(16.95), _cMuted,
            FontWeight.w600),
      ],
    );
  }

  // ── Today's schedule card ──────────────────────────────────────────────────
  Widget _scheduleCard() {
    const cx = 29.66, cy = 324.89, cw = 639.89, ch = 327.71;
    final meetings = _meetings;
    // Row baselines (Figma): (time/title y, dot y)
    const rows = [(111.59, 118.65), (193.52, 200.58), (271.21, 278.27)];
    final rowWidgets = <Widget>[];
    for (var i = 0; i < 3; i++) {
      final (rowY, dotY) = rows[i];
      String time = '—', title = '', dur = '';
      if (i < meetings.length) {
        final ev = meetings[i];
        final sdt = _parse((ev['start'] ?? ev['start_time'])?.toString());
        time = sdt != null ? _ampm(sdt) : '—';
        title = (ev['title'] ?? '—').toString();
        final d = int.tryParse((ev['duration'] ?? 0).toString()) ?? 0;
        dur = d > 0 ? '${(d ~/ 60).clamp(1, 100000)} min' : '—';
      } else if (i == 0) {
        title = _loading ? 'Loading...' : 'Free';
      }
      rowWidgets.addAll([
        _txt(15, rowY.toDouble(), 145, 32, time, ff(21.19), _cBlue,
            FontWeight.w500),
        _pos(158.2, dotY.toDouble(), 11.3, 11.3,
            const DecoratedBox(decoration: BoxDecoration(
                color: _cDot, shape: BoxShape.circle))),
        _txt(182.22, rowY.toDouble(), 360, 32, title, ff(21.19), _cWhite,
            FontWeight.w600),
        _txt(548.07, rowY.toDouble(), 80, 32, dur, ff(21.19), _cMuted,
            FontWeight.w600),
      ]);
    }
    return _card(cx, cy, cw, ch, ff(16.95), _cSchTop, _cCardBot,
      children: [
        _pos(24.02, 25.43, 36.98, 33.39,
            _asset('assets/brief/figma/icon_calendar.png')),
        _txt(70.63, 26, 200, 32, "Today's Schedule", ff(21.19), _cWhite,
            FontWeight.w600),
        _txt(402.58, 26, 185, 32, 'View full calender', ff(21.19), _cBlue,
            FontWeight.w600),
        _pos(395, 18, 220, 44,
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => context.push('/calendar'),
            )),
        for (final dy in [81.93, 162.44, 242.96])
          _pos(24.02, dy, 593.27, 2.83, const ColoredBox(color: _cDivider)),
        ...rowWidgets,
      ],
    );
  }

  // ── Tasks overview card ─────────────────────────────────────────────────────
  Widget _tasksCard() {
    const cx = 676.62, cy = 324.89, cw = 553.72, ch = 327.71;
    final (due, up, un, next) = _taskCounts;
    final specs = [
      ('assets/brief/figma/icon_task_1.png', '$due', _cBlue, 'Due Today',
          '$due due today', 93.23, 103.12, 98.88),
      ('assets/brief/figma/icon_task_2.png', '$up', _cPurple, 'Upcoming',
          'Next: $next', 173.74, 183.63, 179.39),
      ('assets/brief/figma/icon_task_3.png', '$un', _cGreen, 'Unplanned',
          '$un without date', 252.85, 262.73, 259.91),
    ];
    final rowWidgets = <Widget>[];
    for (final s in specs) {
      rowWidgets.addAll([
        _pos(31.08, s.$6, 70.63, 62.15, _asset(s.$1)),
        _txt(120, s.$7, 40, 48, s.$2, ff(35.31), s.$3, FontWeight.w700,
            align: TextAlign.center),
        _txt(217.53, s.$8, 200, 32, s.$4, ff(21.19), _cWhite, FontWeight.w600),
        _txt(217.53, s.$8 + 31.07, 300, 26, s.$5, ff(16.95), _cMuted,
            FontWeight.w500),
      ]);
    }
    return _card(cx, cy, cw, ch, ff(16.95), _cSchTop, _cCardBot,
      children: [
        _pos(21.19, 21.19, 42.38, 42.38,
            _asset('assets/brief/figma/icon_tick.png')),
        _txt(70.63, 26, 180, 32, 'Tasks Overview', ff(21.19), _cWhite,
            FontWeight.w600),
        _txt(360.2, 26, 160, 32, 'View full tasks', ff(21.19), _cBlue,
            FontWeight.w600),
        _pos(352, 18, 200, 44,
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => context.push('/tasks'),
            )),
        for (final dy in [81.93, 162.44, 242.96])
          _pos(24.02, dy, 505.68, 2.83, const ColoredBox(color: _cDivider)),
        ...rowWidgets,
      ],
    );
  }

  // ── Recent emails card ──────────────────────────────────────────────────────
  Widget _emailCard() {
    const cx = 22.6, cy = 659.66, cw = 1214.8, ch = 113.0;
    final top = _topEmail;
    String sender = '—', subject = '—', time = '—';
    if (top != null) {
      sender = (top['from'] ?? '—').toString().split('<').first.trim();
      subject = (top['subject'] ?? top['preview'] ?? top['snippet'] ?? '—')
          .toString();
      time = (top['time'] ?? top['date'] ?? '—').toString();
    } else if (!_loading) {
      sender = 'No recent mail';
      subject = _gmailConnected ? '—' : 'Connect Gmail in settings';
      time = '';
    }
    return _card(cx, cy, cw, ch, ff(24.01), _cCardTop, _cCardBot,
      children: [
        _pos(46.62, 14.13, 33.9, 33.9,
            _asset('assets/brief/figma/icon_email.png')),
        _txt(87.58, 14, 200, 32, 'Recent Emails', ff(21.19), _cWhite,
            FontWeight.w600),
        _txt(1001.5, 11, 200, 40, 'Go to emails  ›', ff(21.19), _cBlue,
            FontWeight.w600),
        _pos(995, 11, 220, 40,
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => context.push('/emails'),
            )),
        _pos(29.66, 55.09, 1155.47, 2.83, const ColoredBox(color: _cDivider)),
        _pos(59.33, 80.51, 11.3, 11.3,
            const DecoratedBox(decoration: BoxDecoration(
                color: _cDot, shape: BoxShape.circle))),
        _txt(93.23, 70, 260, 30, sender, ff(21.19), _cWhite, FontWeight.w600),
        _txt(372.91, 73, 600, 28, subject, ff(18.36), _cMuted,
            FontWeight.w500),
        _txt(1084.84, 73, 130, 28, time, ff(18.36), _cMuted, FontWeight.w500),
      ],
    );
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  Widget _card(double x, double y, double w, double h, double radius,
      Color top, Color bot, {required List<Widget> children}) {
    return Positioned(
      left: x,
      top: y,
      width: w,
      height: h,
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [top, bot],
          ),
          borderRadius: BorderRadius.circular(radius),
          border: Border.all(color: _cBdr),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(radius),
          child: Stack(children: children),
        ),
      ),
    );
  }

  static Widget _pos(double x, double y, double w, double h, Widget child) =>
      Positioned(left: x, top: y, width: w, height: h, child: child);

  static Widget _txt(double x, double y, double w, double h, String text,
      double fs, Color color, FontWeight weight,
      {TextAlign align = TextAlign.left}) {
    return Positioned(
      left: x,
      top: y,
      width: w,
      height: h,
      child: Align(
        alignment: align == TextAlign.center
            ? Alignment.center
            : Alignment.centerLeft,
        child: Text(
          text,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: align,
          style: TextStyle(
              color: color, fontSize: fs, fontWeight: weight, height: 1.0),
        ),
      ),
    );
  }

  static Widget _asset(String path) => Image.asset(path,
      fit: BoxFit.contain,
      errorBuilder: (_, __, ___) => const SizedBox.shrink());
}
