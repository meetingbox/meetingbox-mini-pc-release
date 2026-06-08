import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';

// ── Colours — ported 1:1 from screens/tasks.py ──────────────────────────────
const _cBg = Color(0xFF01081A);
const _cWhite = Color(0xFFFFFFFF);
const _cMuted = Color(0xFFB6BAF2);
const _cDim = Color(0xFF9BA2B2);
const _cBlue = Color(0xFF006BF9);
const _cPurple = Color(0xFFA971D4);
const _cOrange = Color(0xFFF18903);
const _cYellow = Color(0xFFFFC800);
const _cRed = Color(0xFFFF4D4D);
const _cGreen = Color(0xFF19D385);
const _cCardTop = Color(0xFF011137);
const _cCardBot = Color(0xFF000A26);
const _cRowTop = Color(0xFF02123C);
const _cBdr = Color(0xFF3F4253);
const _cDiv = Color(0xB302174D); // #02174D @ 0.7
const _cSecBg = Color(0xE6040F2C); // #040F2C @ 0.9
const _cGreenTop = Color(0xFF0EAA69);
const _cGreenBot = Color(0xFF19D385);
const _cRedTop = Color(0xFFD22D2D);
const _cRedBot = Color(0xFFFF4D4D);

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const _weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
  'Saturday', 'Sunday'];

const _bucketColor = {
  'overdue': _cRed,
  'due_today': _cBlue,
  'upcoming': _cPurple,
  'unplanned': _cOrange,
};
const _bucketLabel = {
  'overdue': 'UNFINISHED',
  'due_today': 'TODAY',
  'upcoming': 'UPCOMING',
  'unplanned': 'UNPLANNED',
};
const _bucketIcon = {
  'overdue': 'assets/brief/figma/icon_task_1.png',
  'due_today': 'assets/brief/figma/icon_task_1.png',
  'upcoming': 'assets/brief/figma/icon_task_2.png',
  'unplanned': 'assets/brief/figma/icon_task_3.png',
};

/// Tasks — rebuilt to match `screens/tasks.py` (Figma 569:193, 1260×800).
/// Header with live count + Add, a 4-tab filter bar (Today / Upcoming /
/// Unfinished / Unplanned) with active underline, and a scrollable list of
/// task rows with complete / cancel / assign-date actions. Data: GET
/// /api/commitments.
class TasksScreen extends StatefulWidget {
  const TasksScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends State<TasksScreen> {
  static const _canvas = Size(1260, 800);
  static const _tabs = [
    ('due_today', 'Today'),
    ('upcoming', 'Upcoming'),
    ('overdue', 'Unfinished'),
    ('unplanned', 'Unplanned'),
  ];

  String _activeTab = 'due_today';
  final Map<String, List<Map<String, dynamic>>> _rows = {
    'overdue': [], 'due_today': [], 'upcoming': [], 'unplanned': [],
  };
  bool _loading = true;
  DateTime? _lastFetch;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final items = widget.config.mockBackend
        ? _mock()
        : await widget.api.getCommitments(limit: 100, status: '');
    final bucketed = <String, List<Map<String, dynamic>>>{
      'overdue': [], 'due_today': [], 'upcoming': [], 'unplanned': [],
    };
    for (final r in items) {
      final b = _categorize(r);
      if (b != null) bucketed[b]!.add(r);
    }
    if (!mounted) return;
    setState(() {
      _rows
        ..['overdue'] = bucketed['overdue']!
        ..['due_today'] = bucketed['due_today']!
        ..['upcoming'] = bucketed['upcoming']!
        ..['unplanned'] = bucketed['unplanned']!;
      _loading = false;
      _lastFetch = DateTime.now();
    });
  }

  List<Map<String, dynamic>> _mock() {
    final t = DateTime.now();
    String iso(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    return [
      {'id': '1', 'title': 'Send Q3 roadmap to leadership', 'due_at': '${iso(t)}T17:00:00', 'status': 'active'},
      {'id': '2', 'title': 'Review onboarding spec', 'detail': 'Focus on the WiFi flow', 'due_at': '${iso(t.add(const Duration(days: 2)))}T09:00:00', 'status': 'active'},
      {'id': '3', 'title': 'Book design review room', 'status': 'active'},
      {'id': '4', 'title': 'Reply to overdue vendor email', 'due_at': '${iso(t.subtract(const Duration(days: 1)))}T10:00:00', 'status': 'active'},
    ];
  }

  static DateTime? _parse(String? s) {
    if (s == null || s.isEmpty) return null;
    try {
      final d = DateTime.parse(s.replaceAll('Z', '+00:00'));
      return d.isUtc ? d.toLocal() : d;
    } catch (_) {
      return null;
    }
  }

  String? _categorize(Map<String, dynamic> row) {
    final status = (row['status'] ?? '').toString().toLowerCase();
    if (status == 'completed' || status == 'cancelled' || status == 'canceled') {
      return null;
    }
    final raw = (row['due_at'] ?? row['remind_at'] ?? '').toString().trim();
    if (raw.isEmpty) return 'unplanned';
    final d = _parse(raw);
    if (d == null) return 'unplanned';
    final now = DateTime.now();
    final todayStart = DateTime(now.year, now.month, now.day);
    final todayEnd = DateTime(now.year, now.month, now.day, 23, 59, 59);
    if (d.isBefore(todayStart)) return 'overdue';
    if (!d.isAfter(todayEnd)) return 'due_today';
    return 'upcoming';
  }

  String _fmtDue(Map<String, dynamic> row, String bucket) {
    if (bucket == 'unplanned') return 'No date';
    final raw = (row['due_at'] ?? row['remind_at'] ?? '').toString().trim();
    final d = _parse(raw);
    if (d == null) return '—';
    final now = DateTime.now();
    String time12(DateTime x) {
      final h = x.hour % 12 == 0 ? 12 : x.hour % 12;
      return '$h:${x.minute.toString().padLeft(2, '0')} ${x.hour < 12 ? 'AM' : 'PM'}';
    }

    if (bucket == 'due_today' || bucket == 'overdue') {
      final deltaMin = d.difference(now).inMinutes;
      if (deltaMin >= -2 && deltaMin <= 2) return 'Now';
      if (deltaMin > 0 && deltaMin < 60) return 'in ${deltaMin}m';
      if (deltaMin < 0) {
        final ago = -deltaMin;
        return ago < 60 ? '${ago}m ago' : '${ago ~/ 60}h ago';
      }
      return time12(d);
    }
    final days = DateTime(d.year, d.month, d.day)
        .difference(DateTime(now.year, now.month, now.day))
        .inDays;
    if (days == 0) return time12(d);
    if (days == 1) return 'Tomorrow';
    if (days < 7) return _weekdays[d.weekday - 1];
    return '${_months[d.month - 1]} ${d.day}';
  }

  int _count(String bucket) => _rows[bucket]?.length ?? 0;
  int get _total =>
      _count('overdue') + _count('due_today') + _count('upcoming') +
          _count('unplanned');

  String get _updatedText {
    if (_lastFetch == null) return '';
    final delta = DateTime.now().difference(_lastFetch!).inSeconds;
    if (delta < 15) return 'Updated just now';
    if (delta < 60) return 'Updated ${delta}s ago';
    if (delta < 3600) return 'Updated ${delta ~/ 60} min ago';
    return 'Updated ${delta ~/ 3600}h ago';
  }

  // ── Actions ─────────────────────────────────────────────────────────────

  Future<void> _patch(String id, {String? status, String? dueDate}) async {
    if (id.isEmpty) return;
    if (status == 'completed' || status == 'cancelled') {
      setState(() {
        for (final b in _rows.keys) {
          _rows[b] = _rows[b]!.where((r) => (r['id'] ?? '').toString() != id)
              .toList();
        }
      });
    }
    if (!widget.config.mockBackend) {
      await widget.api.patchCommitment(id, status: status, dueDate: dueDate);
      if (dueDate != null) await _load();
    }
  }

  Future<void> _assignDate(String id) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked == null) return;
    final iso =
        '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    await _patch(id, dueDate: iso);
  }

  Future<void> _openAddTask() async {
    final controller = TextEditingController();
    final title = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF02123C),
        title: const Text('New task', style: TextStyle(color: _cWhite)),
        content: TextField(
          controller: controller,
          autofocus: true,
          style: const TextStyle(color: _cWhite),
          decoration: const InputDecoration(
            hintText: 'e.g. Call John about the proposal',
            hintStyle: TextStyle(color: _cDim),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: _cMuted))),
          TextButton(
              onPressed: () => Navigator.pop(ctx, controller.text.trim()),
              child: const Text('Save', style: TextStyle(color: _cGreen))),
        ],
      ),
    );
    if (title == null || title.isEmpty) return;
    if (!widget.config.mockBackend) {
      await widget.api.createCommitment(title: title);
      await _load();
    }
  }

  // ── Build ───────────────────────────────────────────────────────────────

  double ffb(double x) => x * 1.25;

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
                _filterBar(),
                _listArea(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _header() {
    return [
      _pos(24.02, 21.19, 76.28, 76.28,
          GestureDetector(
            onTap: () =>
                context.canPop() ? context.pop() : context.go('/home'),
            child: _asset('assets/calendar/figma/btn_back.png'),
          )),
      _pos(118, 27, 42.38, 42.38, _asset('assets/brief/figma/icon_tick.png')),
      _txt(170, 14, 300, 56, 'Tasks', 38.52, _cWhite, FontWeight.w600,
          valign: true),
      _txt(620, 10, 440, 40,
          _total > 0 ? '$_total task${_total == 1 ? '' : 's'}'
              : (_loading ? '' : 'No tasks'),
          21.19, _cMuted, FontWeight.w500, align: TextAlign.right),
      _txt(620, 52, 440, 28, _updatedText, 14.13, _cDim, FontWeight.w500,
          align: TextAlign.right),
      // + Add task button
      _pos(1095.98, 28, 140, 48,
          GestureDetector(
            onTap: _openAddTask,
            child: Container(
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [_cGreenTop, _cGreenBot],
                ),
                borderRadius: BorderRadius.circular(14),
              ),
              alignment: Alignment.center,
              child: const Text('+  Add task',
                  style: TextStyle(
                      color: _cWhite, fontSize: 18, fontWeight: FontWeight.w600)),
            ),
          )),
      _pos(22.6, 100, 1214.8, 1.89, const ColoredBox(color: _cDiv)),
    ];
  }

  // ── Filter bar ──────────────────────────────────────────────────────────
  Widget _filterBar() {
    const bx = 22.6, by = 109.0, bw = 1214.8, bh = 62.0;
    const cellW = bw / 4;
    return _card(bx, by, bw, bh, 16.95, children: [
      for (var i = 0; i < _tabs.length; i++)
        _tabCell(i, cellW),
    ]);
  }

  Widget _tabCell(int i, double cellW) {
    final (id, label) = _tabs[i];
    final active = id == _activeTab;
    final n = _count(id);
    return Positioned(
      left: cellW * i,
      top: 0,
      width: cellW,
      height: 62,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() => _activeTab = id),
        child: Stack(
          children: [
            Center(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(label,
                      style: TextStyle(
                          color: active ? _cBlue : _cMuted,
                          fontSize: ffb(21.19),
                          fontWeight: FontWeight.w600)),
                  if (n > 0) ...[
                    const SizedBox(width: 8),
                    Text('$n',
                        style: TextStyle(
                            color: active ? _cBlue : _cWhite,
                            fontSize: ffb(16.95),
                            fontWeight: FontWeight.w500)),
                  ],
                ],
              ),
            ),
            if (active)
              Positioned(
                left: cellW * 0.14,
                bottom: 0,
                width: cellW * 0.72,
                height: 3,
                child: const ColoredBox(color: _cBlue),
              ),
          ],
        ),
      ),
    );
  }

  // ── List area ─────────────────────────────────────────────────────────────
  Widget _listArea() {
    const lx = 22.6, ly = 179.0, lw = 1214.8, lh = 600.0;
    final rows = _rows[_activeTab] ?? [];
    Widget body;
    if (_loading) {
      body = const Center(
          child: Text('Loading tasks…',
              style: TextStyle(color: _cMuted, fontSize: 26)));
    } else if (rows.isEmpty) {
      body = const Center(
          child: Text('No tasks to show',
              style: TextStyle(color: _cMuted, fontSize: 26)));
    } else {
      body = ListView(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
        children: [
          _sectionHeader(_activeTab, rows.length),
          const SizedBox(height: 5),
          for (final r in rows) ...[
            _taskRow(r, _activeTab),
            const SizedBox(height: 7),
          ],
        ],
      );
    }
    return _card(lx, ly, lw, lh, 22.6, children: [Positioned.fill(child: body)]);
  }

  Widget _sectionHeader(String bucket, int count) {
    final col = _bucketColor[bucket]!;
    return Container(
      height: 50,
      decoration: BoxDecoration(
        color: _cSecBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Container(width: 4, height: 50, color: col),
          const SizedBox(width: 8),
          SizedBox(
              width: 31.08,
              child: _asset(_bucketIcon[bucket]!)),
          const SizedBox(width: 12),
          Text(_bucketLabel[bucket]!,
              style: TextStyle(
                  color: col,
                  fontSize: ffb(16.95),
                  fontWeight: FontWeight.w600)),
          const SizedBox(width: 16),
          Text('$count',
              style: TextStyle(
                  color: col,
                  fontSize: ffb(16.95),
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _taskRow(Map<String, dynamic> row, String bucket) {
    final id = (row['id'] ?? '').toString();
    final col = _bucketColor[bucket]!;
    final title = (row['title'] ?? 'Untitled task').toString().trim();
    final detail = (row['detail'] ?? '').toString().trim();
    final dueText = _fmtDue(row, bucket);
    final snoozed = (row['status'] ?? '').toString().toLowerCase() == 'snoozed';
    final isUnplan = bucket == 'unplanned';
    final hasExtra = detail.isNotEmpty;
    final rowH = hasExtra ? 88.0 : 72.0;

    return Container(
      height: rowH,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [_cRowTop, _cCardBot],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _cBdr),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          Container(
            width: 11,
            height: 11,
            decoration: BoxDecoration(
                color: snoozed ? _cYellow : col, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        color: _cWhite,
                        fontSize: ffb(21.19),
                        fontWeight: FontWeight.w600)),
                if (hasExtra) ...[
                  const SizedBox(height: 3),
                  Text(
                      detail.length > 70
                          ? '${detail.substring(0, 70)}…'
                          : detail,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          color: _cDim, fontSize: ffb(14.13))),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          if (snoozed)
            _snoozedRight(dueText, col)
          else
            _actionButtons(id, isUnplan),
        ],
      ),
    );
  }

  Widget _snoozedRight(String dueText, Color col) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text('SNOOZED',
            style: TextStyle(
                color: _cYellow, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(width: 10),
        Text(dueText,
            style: TextStyle(
                color: col, fontSize: 21, fontWeight: FontWeight.w500)),
      ],
    );
  }

  Widget _actionButtons(String id, bool isUnplan) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (isUnplan) ...[
          _actionBtn(
            color: null,
            border: _cBdr,
            child: SizedBox(
                width: 26,
                height: 26,
                child: _asset('assets/brief/figma/icon_calendar.png')),
            onTap: () => _assignDate(id),
          ),
          const SizedBox(width: 10),
        ],
        _actionBtn(
          gradient: const [_cGreenTop, _cGreenBot],
          child: SizedBox(
              width: 26,
              height: 26,
              child: _asset('assets/brief/figma/icon_tick.png')),
          onTap: () => _patch(id, status: 'completed'),
        ),
        const SizedBox(width: 10),
        _actionBtn(
          gradient: const [_cRedTop, _cRedBot],
          child: const Text('×',
              style: TextStyle(
                  color: _cWhite, fontSize: 26, fontWeight: FontWeight.w500)),
          onTap: () => _patch(id, status: 'cancelled'),
        ),
      ],
    );
  }

  Widget _actionBtn({
    required Widget child,
    required VoidCallback onTap,
    List<Color>? gradient,
    Color? color,
    Color? border,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: gradient == null ? (color ?? _cCardTop) : null,
          gradient: gradient == null
              ? null
              : LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: gradient,
                ),
          borderRadius: BorderRadius.circular(10),
          border: border != null ? Border.all(color: border) : null,
        ),
        child: child,
      ),
    );
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  Widget _card(double x, double y, double w, double h, double radius,
      {required List<Widget> children}) {
    return Positioned(
      left: x,
      top: y,
      width: w,
      height: h,
      child: Container(
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [_cCardTop, _cCardBot],
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
      {TextAlign align = TextAlign.left, bool valign = false}) {
    return Positioned(
      left: x,
      top: y,
      width: w,
      height: h,
      child: Align(
        alignment: align == TextAlign.right
            ? (valign ? Alignment.centerRight : Alignment.topRight)
            : (valign ? Alignment.centerLeft : Alignment.topLeft),
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
