import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';

// ── Colours — ported 1:1 from screens/calendar.py ───────────────────────────
const _cBg = Color(0xFF01081A);
const _cWhite = Color(0xFFFFFFFF);
const _cMuted = Color(0xFFB6BAF2);
const _cBdot = Color(0xFF4098FC);
const _cBlueA = Color(0xFF006BF9);
const _cToday = Color(0xFF0484FF);
const _cCardTop = Color(0xFF02123C);
const _cCardBot = Color(0xFF000A26);
const _cBdrCard = Color(0xFF3F4253);
const _cBdrMtg = Color(0xFF21284B);
const _cBdrBtn = Color(0xFF3F8CFF);
const _cMtgTop = Color(0xFF011137);
const _cMtgBot = Color(0xFF000A26);
const _cSep = Color(0x999ABDFF); // #9ABDFF @ 0.6
const _cTodayFill = Color(0x61042842); // ~(0.016,0.082,0.259,0.38)

const _dayAbbr = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
const _dayFull = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
  'Saturday', 'Sunday'];
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Grid geometry (Figma)
const _gx = 24.02, _gy = 105.94, _gw = 1210.56, _gh = 151.14;

/// Calendar — rebuilt to match `screens/calendar.py` (Figma 927:61, 1260×800).
/// Header with day heading + busy/free summary, a 7-day week grid with
/// meeting-count dots, a free-time status card, and a scrollable timeline of
/// the selected day's meetings. Data: GET /api/calendar/week.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  static const _canvas = Size(1260, 800);

  late DateTime _weekMon;
  late DateTime _selected;
  Map<String, List<Map<String, dynamic>>> _byDate = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    _weekMon = today.subtract(Duration(days: today.weekday - 1));
    _selected = today;
    _load();
  }

  static String _iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  static DateTime get _today {
    final n = DateTime.now();
    return DateTime(n.year, n.month, n.day);
  }

  List<DateTime> get _colDates =>
      List.generate(7, (i) => _weekMon.add(Duration(days: i)));

  Future<void> _load() async {
    setState(() => _loading = true);
    final end = _weekMon.add(const Duration(days: 6));
    final data = widget.config.mockBackend
        ? _mock()
        : await widget.api.getCalendarWeek(_iso(_weekMon), _iso(end));
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
    final t = _today;
    return {
      'days': {
        _iso(t): {
          'meetings': [
            {'title': 'Product Sync', 'start': '${_iso(t)}T10:00:00', 'duration': 1800},
            {'title': 'Design Review', 'start': '${_iso(t)}T14:00:00', 'duration': 3600},
          ],
        },
        _iso(t.add(const Duration(days: 1))): {
          'meetings': [
            {'title': '1:1 with Sam', 'start': '${_iso(t.add(const Duration(days: 1)))}T11:00:00', 'duration': 1800},
          ],
        },
      },
    };
  }

  void _navWeek(int delta) {
    setState(() {
      _weekMon = _weekMon.add(Duration(days: 7 * delta));
      _byDate = {};
      final cols = _colDates;
      _selected = cols.contains(_today) ? _today : _weekMon;
    });
    _load();
  }

  void _selectDay(DateTime d) => setState(() => _selected = d);

  List<Map<String, dynamic>> get _selMeetings {
    final list = List<Map<String, dynamic>>.from(_byDate[_iso(_selected)] ?? []);
    list.sort((a, b) =>
        (a['start'] ?? '').toString().compareTo((b['start'] ?? '').toString()));
    return list;
  }

  static DateTime? _parse(String? s) {
    if (s == null || s.isEmpty) return null;
    try {
      return DateTime.parse(s.replaceAll('Z', '+00:00')).toLocal();
    } catch (_) {
      return null;
    }
  }

  static String _ampm(DateTime dt) {
    final am = dt.hour < 12 ? 'AM' : 'PM';
    var h = dt.hour % 12;
    if (h == 0) h = 12;
    return '$h:${dt.minute.toString().padLeft(2, '0')} $am';
  }

  String _fmtDate(DateTime d) =>
      '${_dayAbbr[d.weekday - 1].substring(0, 1)}${_dayAbbr[d.weekday - 1].substring(1).toLowerCase()} , ${_months[d.month - 1]} ${d.day}';

  // ── Build ───────────────────────────────────────────────────────────────

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
                ..._header(),
                ..._grid(),
                _freeCard(),
                _meetingArea(),
                _addButton(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── Header ────────────────────────────────────────────────────────────────
  List<Widget> _header() {
    final isToday = _selected == _today;
    final heading = isToday ? 'Today' : _dayFull[_selected.weekday - 1];
    final (busy, free) = _summary();
    return [
      _pos(24.02, 21.19, 76.28, 76.28,
          GestureDetector(
            onTap: () =>
                context.canPop() ? context.pop() : context.go('/home'),
            child: _asset('assets/calendar/figma/btn_back.png'),
          )),
      _txt(118.66, 14.13, 320, 50, heading, 38.52, _cWhite, FontWeight.w600),
      _pos(360, 22, 36.98, 33,
          _asset('assets/brief/figma/icon_calendar.png')),
      _txt(118.66, 64.36, 320, 36, _fmtDate(_selected), 27.52 * 1.2, _cBlueA,
          FontWeight.w600),
      _pos(851.77, 28, 39.38, 40.89,
          _asset('assets/calendar/figma/icon_spark.png')),
      _txt(905.91, 19.78, 340, 36,
          _loading ? 'Loading calendar...' : busy, 24.61 * 1.2, _cMuted,
          FontWeight.w600),
      _txt(905.91, 55.46, 300, 36, _loading ? '' : free, 24.61 * 1.2, _cMuted,
          FontWeight.w600),
    ];
  }

  (String, String) _summary() {
    final abbrs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final busy = <String>[], moderate = <String>[], free = <String>[];
    final cols = _colDates;
    for (var i = 0; i < 7; i++) {
      final n = (_byDate[_iso(cols[i])] ?? []).length;
      if (n >= 3) {
        busy.add(abbrs[i]);
      } else if (n == 2) {
        moderate.add(abbrs[i]);
      } else if (n == 0) {
        free.add(abbrs[i]);
      }
    }
    String busyText;
    if (busy.isNotEmpty) {
      busyText = 'Busy: ${busy.join(', ')}';
    } else if (moderate.isNotEmpty) {
      busyText = 'Moderate: ${moderate.join(', ')}';
    } else {
      busyText = 'Light week ahead';
    }
    final freeText = free.isNotEmpty ? 'Free: ${free.join(', ')}' : '';
    return (busyText, freeText);
  }

  // ── Week grid ───────────────────────────────────────────────────────────────
  List<Widget> _grid() {
    final cols = _colDates;
    const colStart = _gx + 72; // leave room for the left nav arrow
    const colEnd = _gx + 1140; // leave room for the right nav arrow
    const colW = (colEnd - colStart) / 7;
    final widgets = <Widget>[
      // Grid background card
      _card(_gx, _gy, _gw, _gh, 29.66, _cCardTop, _cCardBot, children: const []),
      // Nav arrows
      _pos(_gx + 4, _gy, 60, _gh,
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => _navWeek(-1),
          )),
      _pos(_gx + 16, _gy + 51, 42, 50,
          _asset('assets/calendar/figma/icon_nav_left.png')),
      _pos(_gx + 1146, _gy, 65, _gh,
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => _navWeek(1),
          )),
      _pos(_gx + 1152, _gy + 51, 42, 50,
          _asset('assets/calendar/figma/icon_nav_right.png')),
    ];

    for (var i = 0; i < 7; i++) {
      final d = cols[i];
      final cx = colStart + colW * i;
      final isToday = d == _today;
      final isSel = d == _selected;
      // Highlight box (square, centred on column)
      const hlSize = 139.84;
      final hlX = cx + (colW - hlSize) / 2;
      if (isToday || isSel) {
        widgets.add(_pos(hlX, _gy + 5, hlSize, hlSize,
            DecoratedBox(
              decoration: BoxDecoration(
                color: isToday ? _cTodayFill : _cToday.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(14.13),
                border: Border.all(
                    color: isToday ? _cToday : _cToday.withValues(alpha: 0.55),
                    width: 1.41),
              ),
            )));
      }
      // Tap zone
      widgets.add(_pos(cx, _gy, colW, _gh,
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => _selectDay(d),
          )));
      // Day abbreviation
      widgets.add(_txt(cx, _gy + 24, colW, 34, _dayAbbr[i], 28.25, _cMuted,
          FontWeight.w600, align: TextAlign.center));
      // Date number
      widgets.add(_txt(cx, _gy + 48, colW, 51, '${d.day}', 42.38, _cWhite,
          FontWeight.w700, align: TextAlign.center));
      // Dots
      widgets.add(_pos(cx, _gy + 118, colW, 20,
          _dots((_byDate[_iso(d)] ?? []).length)));
    }
    return widgets;
  }

  Widget _dots(int n) {
    final count = n == 0 ? 1 : (n > 3 ? 3 : n);
    final filled = n > 0;
    const size = 14.13, spacing = 22.6;
    return Center(
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(count, (i) {
          return Container(
            width: size,
            height: size,
            margin: EdgeInsets.only(right: i == count - 1 ? 0 : spacing - size),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: filled ? _cBdot : null,
              border: filled
                  ? null
                  : Border.all(color: _cMuted.withValues(alpha: 0.8), width: 1.2),
            ),
          );
        }),
      ),
    );
  }

  // ── Free-time status card ─────────────────────────────────────────────────
  Widget _freeCard() {
    const cx = 25.43, cy = 268.39, cw = 1210.56, ch = 100.29;
    final meetings = _selMeetings;
    final isToday = _selected == _today;
    final now = DateTime.now();
    String freeText;
    String mtgText = '';
    bool showSun = false;
    if (meetings.isEmpty) {
      freeText = 'No meetings scheduled for this day';
    } else {
      final n = meetings.length;
      final noun = '$n meeting${n > 1 ? 's' : ''}';
      if (isToday) {
        final states = meetings.map((m) => _state(m, now)).toList();
        if (states.every((s) => s == 'past')) {
          freeText = 'All meetings for today are done';
          mtgText = '$noun completed';
        } else {
          final active = [
            for (var i = 0; i < meetings.length; i++)
              if (states[i] == 'active') meetings[i]
          ];
          final upcoming = [
            for (var i = 0; i < meetings.length; i++)
              if (states[i] == 'upcoming') meetings[i]
          ];
          if (active.isNotEmpty) {
            final end = _parse(active.first['end']?.toString());
            final endStr = end != null ? '  (till ${_ampm(end)})' : '';
            freeText = 'In meeting: ${active.first['title'] ?? 'meeting'}$endStr';
          } else if (upcoming.isNotEmpty) {
            final nxt = _parse(upcoming.first['start']?.toString());
            freeText = nxt != null ? "You're free till ${_ampm(nxt)}" : '$noun today';
          } else {
            freeText = '$noun today';
          }
          mtgText = '$noun today';
        }
        showSun = true;
      } else {
        freeText = '$noun scheduled';
      }
    }
    return _card(cx, cy, cw, ch, 29.66, _cCardTop, _cCardBot, children: [
      _pos(31.08, 24.02, 53.68, 53.68,
          _asset('assets/calendar/figma/icon_clock.png')),
      _txt(97.47, 31.08, 700, 39, freeText, 32.49, _cWhite, FontWeight.w700),
      if (showSun && mtgText.isNotEmpty) ...[
        _pos(884.26, 28.25, 49.44, 49.44,
            _asset('assets/calendar/figma/icon_sun.png')),
        _txt(943.59, 35.32, 280, 37, mtgText, 31.08, _cWhite, FontWeight.w700),
      ],
    ]);
  }

  String _state(Map<String, dynamic> m, DateTime now) {
    final s = _parse(m['start']?.toString());
    final e = _parse(m['end']?.toString());
    if (s == null || e == null) return 'upcoming';
    if (!now.isBefore(e)) return 'past';
    if (!now.isBefore(s)) return 'active';
    return 'upcoming';
  }

  // ── Meeting timeline (scrollable) ───────────────────────────────────────────
  Widget _meetingArea() {
    const ax = 24.02, ay = 377.15, aw = 1210.56, ah = 339.01;
    final meetings = _selMeetings;
    return Positioned(
      left: ax,
      top: ay,
      width: aw,
      height: ah,
      child: Stack(
        children: [
          // Vertical separator (relative x within area = 203.41 - 24.02)
          const Positioned(
            left: 179.39,
            top: 0,
            width: 2.83,
            height: ah,
            child: ColoredBox(color: _cSep),
          ),
          if (meetings.isEmpty)
            const Center(
              child: Text('No meetings scheduled for this day',
                  style: TextStyle(
                      color: _cMuted,
                      fontSize: 28,
                      fontWeight: FontWeight.w600)),
            )
          else
            ListView.builder(
              padding: const EdgeInsets.only(bottom: 8),
              itemCount: meetings.length,
              itemBuilder: (_, i) => _meetingRow(meetings[i]),
            ),
        ],
      ),
    );
  }

  Widget _meetingRow(Map<String, dynamic> m) {
    const rowH = 104.53;
    final now = DateTime.now();
    final isToday = _selected == _today;
    final state = isToday ? _state(m, now) : 'upcoming';
    final start = _parse(m['start']?.toString());
    final timeStr = start != null ? _ampm(start) : '--:--';
    final past = state == 'past';

    // Duration
    var durMin = (int.tryParse((m['duration'] ?? 0).toString()) ?? 0) ~/ 60;
    if (durMin == 0) {
      final s = _parse(m['start']?.toString());
      final e = _parse(m['end']?.toString());
      if (s != null && e != null) durMin = e.difference(s).inMinutes;
    }
    final durStr = durMin > 0 ? '$durMin min' : '';
    final title = (m['title'] ?? '-').toString();

    return SizedBox(
      height: rowH + 8,
      child: Stack(
        children: [
          // Timeline dot (centred on separator x=179.39, vertically centred)
          Positioned(
            left: 179.39 - 16,
            top: rowH / 2 - 16,
            width: 32,
            height: 32,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _cWhite,
                border: Border.all(
                    color: past
                        ? const Color(0xFF99B3FF).withValues(alpha: 0.5)
                        : const Color(0xFF0090FF),
                    width: 2),
              ),
            ),
          ),
          // Time label
          Positioned(
            left: 0,
            top: rowH / 2 - 20,
            width: 130,
            height: 40,
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(timeStr,
                  style: TextStyle(
                      color: past ? _cMuted : _cWhite,
                      fontSize: 28.25 * 1.2,
                      fontWeight: FontWeight.w700)),
            ),
          ),
          // Meeting card
          Positioned(
            left: 252.84,
            top: 0,
            width: 954.89,
            height: rowH,
            child: _meetingCard(title, durStr, past),
          ),
        ],
      ),
    );
  }

  Widget _meetingCard(String title, String durStr, bool past) {
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [_cMtgTop, _cMtgBot],
        ),
        borderRadius: BorderRadius.circular(25.43),
        border: Border.all(color: _cBdrMtg),
      ),
      child: Stack(
        children: [
          Positioned(
            left: 32.49,
            top: 16.95,
            width: 70.63,
            height: 70.63,
            child: _asset('assets/calendar/figma/icon_meeting.png'),
          ),
          Positioned(
            left: 129.95,
            top: 16.95,
            width: 560,
            height: 34,
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      color: past ? _cMuted : _cWhite,
                      fontSize: 28.25,
                      fontWeight: FontWeight.w700)),
            ),
          ),
          Positioned(
            left: 129.95,
            top: 56.5,
            width: 24,
            height: 24,
            child: _asset('assets/calendar/figma/icon_clock.png'),
          ),
          Positioned(
            left: 160,
            top: 56.5,
            width: 175,
            height: 31,
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(durStr,
                  style: const TextStyle(
                      color: _cMuted,
                      fontSize: 22.6,
                      fontWeight: FontWeight.w600)),
            ),
          ),
          // Details button
          Positioned(
            left: 778.32,
            top: 24.01,
            width: 144.08,
            height: 56.5,
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12.71),
                border: Border.all(color: _cBdrBtn),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('Details',
                      style: TextStyle(
                          color: _cWhite,
                          fontSize: 21.19 * 1.3,
                          fontWeight: FontWeight.w700)),
                  const SizedBox(width: 8),
                  SizedBox(
                    width: 16,
                    height: 26,
                    child: _asset(
                        'assets/calendar/figma/icon_arrow_details.png'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Add event button ───────────────────────────────────────────────────────
  Widget _addButton() {
    const bw = 378.57, bh = 60.74;
    return _card(440.72, 716.16, bw, bh, 16.95, _cMtgTop, _cMtgBot, children: [
      _txt(98.88, 9.89, 42.38, 42.38, '+', 34, _cBlueA, FontWeight.w700,
          align: TextAlign.center),
      _txt(146.91, 14.13, 133, 34, 'Add event', 28.25, _cBlueA,
          FontWeight.w700),
    ]);
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
          border: Border.all(color: _cBdrCard),
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
