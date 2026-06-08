import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/layout/figma_canvas.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';

// ── Colours — ported 1:1 from screens/emails.py ──────────────────────────────
const _cBg = Color(0xFF01081A);
const _cWhite = Color(0xFFFFFFFF);
const _cMuted = Color(0xFFB6BAF2);
const _cBlue = Color(0xFF006BF9);
const _cPnlTop = Color(0xFF000F33);
const _cPnlBot = Color(0xFF000A26);
const _cHdrTop = Color(0xFF02123C);
const _cBdr = Color(0xFF3F4253);
const _cSbr = Color(0xFF21284B);
const _cSel = Color(0xFF3F8CFF);
const _cDotTop = Color(0xFF467DFE);
const _cDotBot = Color(0xFF0058F4);
const _cMoreTop = Color(0xFF011137);
const _cSbTrack = Color(0xFF010B26);
const _cSelFill = Color(0x59000E2E); // (0,0.055,0.18,0.35)
const _cUnreadBdr = Color(0x593F4253); // #3F4253 @ 0.35

/// Emails screen, rebuilt to match `screens/emails.py` — a 1260×800 Figma
/// split-pane: circular back button, header bar with 5 tabs + search, a left
/// list panel (NEW / EARLIER sections, selected/unread/read row styles) and a
/// right reading pane (avatar, sender, To:, subject, scrollable body).
class EmailsScreen extends StatefulWidget {
  const EmailsScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<EmailsScreen> createState() => _EmailsScreenState();
}

class _EmailsScreenState extends State<EmailsScreen> {
  static const _tabDefs = [
    ('today', 'Today', 37.0, 105.0),
    ('all', 'All', 175.0, 220.0),
    ('unread', 'Unread', 295.0, 378.0),
    ('sent', 'Sent', 460.0, 510.0),
    ('drafts', 'Drafts', 600.0, 668.0),
  ];

  List<Map<String, dynamic>> _inbox = [];
  List<Map<String, dynamic>> _sent = [];
  List<Map<String, dynamic>> _drafts = [];
  bool _sentLoaded = false;
  bool _draftsLoaded = false;

  String _activeTab = 'all';
  Map<String, dynamic>? _selected;
  Map<String, dynamic> _detail = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadInbox();
  }

  // ── Data ──────────────────────────────────────────────────────────────────

  Future<void> _loadInbox() async {
    final emails = widget.config.mockBackend
        ? _mock()
        : await widget.api.getEmails(filter: 'all', limit: 50);
    if (!mounted) return;
    setState(() {
      _inbox = emails;
      _loading = false;
      if (_selected == null && _filtered.isNotEmpty) {
        _selected = _filtered.first;
        _detail = _filtered.first;
      }
    });
    _fetchBody(_selected);
  }

  Future<void> _loadFolder(String folder) async {
    if (widget.config.mockBackend) return;
    final emails = await widget.api.getEmails(filter: folder, limit: 50);
    if (!mounted) return;
    setState(() {
      if (folder == 'sent') {
        _sent = emails;
        _sentLoaded = true;
      } else {
        _drafts = emails;
        _draftsLoaded = true;
      }
    });
  }

  List<Map<String, dynamic>> _mock() => [
        {'id': '1', 'sender': 'Alex Rivera', 'subject': 'Q3 roadmap review', 'preview': 'Here is the draft for tomorrow, let me know your thoughts before the sync.', 'time': '9:24 AM', 'is_read': false, 'is_today': true, 'to': 'me', 'body': 'Here is the draft for tomorrow, let me know your thoughts before the sync.'},
        {'id': '2', 'sender': 'GitHub', 'subject': 'PR #482 merged', 'preview': 'Your pull request was merged into main.', 'time': '8:01 AM', 'is_read': false, 'is_today': true, 'to': 'me', 'body': 'Your pull request was merged into main.'},
        {'id': '3', 'sender': 'Sam Park', 'subject': 'Design review notes', 'preview': 'Thanks everyone for the feedback on the new layout.', 'time': 'Yesterday', 'is_read': true, 'is_today': false, 'to': 'me', 'body': 'Thanks everyone for the feedback on the new layout.'},
        {'id': '4', 'sender': 'Notion', 'subject': 'Weekly digest', 'preview': '3 pages were updated in your workspace.', 'time': 'Mon', 'is_read': true, 'is_today': false, 'to': 'me', 'body': '3 pages were updated in your workspace.'},
      ];

  List<Map<String, dynamic>> get _filtered {
    switch (_activeTab) {
      case 'sent':
        return _sent;
      case 'drafts':
        return _drafts;
      case 'today':
        return _inbox.where((e) => e['is_today'] == true).toList();
      case 'unread':
        return _inbox.where((e) => e['is_read'] != true).toList();
      default:
        return _inbox;
    }
  }

  int _count(String tab) {
    switch (tab) {
      case 'today':
        return _inbox.where((e) => e['is_today'] == true).length;
      case 'all':
        return _inbox.length;
      case 'unread':
        return _inbox.where((e) => e['is_read'] != true).length;
      case 'sent':
        return _sent.length;
      case 'drafts':
        return _drafts.length;
    }
    return 0;
  }

  void _onTab(String tab) {
    if (tab == _activeTab) return;
    setState(() => _activeTab = tab);
    if (tab == 'sent' && !_sentLoaded) _loadFolder('sent');
    if (tab == 'drafts' && !_draftsLoaded) _loadFolder('drafts');
  }

  void _select(Map<String, dynamic> e) {
    setState(() {
      if (e['is_read'] != true) e['is_read'] = true;
      _selected = e;
      _detail = e;
    });
    if (!widget.config.mockBackend) {
      widget.api.markEmailRead((e['id'] ?? '').toString());
    }
    _fetchBody(e);
  }

  Future<void> _fetchBody(Map<String, dynamic>? e) async {
    if (e == null || widget.config.mockBackend) return;
    final id = (e['id'] ?? '').toString();
    if (id.isEmpty) return;
    final d = await widget.api.getEmailDetail(id);
    if (!mounted || _selected == null || _selected!['id'] != e['id']) return;
    if (d.isNotEmpty) setState(() => _detail = {...e, ...d});
  }

  void _markUnread() {
    final e = _selected;
    if (e == null) return;
    setState(() => e['is_read'] = false);
    if (!widget.config.mockBackend) {
      widget.api.markEmailRead((e['id'] ?? '').toString(), read: false);
    }
  }

  void _archive() {
    final e = _selected;
    if (e == null) return;
    setState(() {
      _inbox = _inbox.where((m) => m['id'] != e['id']).toList();
      _selected = null;
      _detail = {};
    });
    if (!widget.config.mockBackend) {
      widget.api.archiveEmail((e['id'] ?? '').toString());
    }
  }

  void _detailBack() => setState(() {
        _selected = null;
        _detail = {};
      });

  // ── Build ───────────────────────────────────────────────────────────────

  double _fz(FigmaScale s, double px) => s.font(px / kCanvasH);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _cBg,
      body: FigmaCanvas(
        background: _cBg,
        children: [
          // Back button — x=24.02 y=21 w/h=76.28 circular
          FigmaChild(
            const FigmaBox(24.02, 21, 76.28, 76.28),
            (_, s) => GestureDetector(
              onTap: () =>
                  context.canPop() ? context.pop() : context.go('/home'),
              child: Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [_cPnlTop, _cBg],
                  ),
                  border: Border.all(color: _cBdr, width: s.px(1)),
                ),
                alignment: Alignment.center,
                child: Text('←',
                    style: TextStyle(
                        color: _cWhite,
                        fontSize: _fz(s, 22),
                        fontWeight: FontWeight.w600)),
              ),
            ),
          ),

          // Header bar — x=23 y=104 w=1214 h=101 r=22.6
          FigmaChild(
            const FigmaBox(23, 104, 1214, 101),
            (_, s) => _panel(s, 22.60,
                top: _cHdrTop, bot: _cPnlBot),
          ),
          // Header title
          FigmaChild(
            const FigmaBox(60, 125, 120, 36),
            (_, s) => _text('Emails', _fz(s, 30), _cWhite, weight: FontWeight.w700),
          ),
          // Tabs (label + count) + tap regions
          for (final t in _tabDefs) ...[
            FigmaChild(
              FigmaBox(23 + t.$3, 166, 90, 29),
              (_, s) => _text(t.$2, _fz(s, 22),
                  t.$1 == _activeTab ? _cBlue : _cMuted,
                  weight: FontWeight.w600),
            ),
            FigmaChild(
              FigmaBox(23 + t.$4, 166, 40, 29),
              (_, s) => _text('${_count(t.$1)}', _fz(s, 22),
                  t.$1 == _activeTab ? _cBlue : _cWhite,
                  weight: FontWeight.w600),
            ),
            FigmaChild(
              FigmaBox(23 + t.$3 - 4, 161, 130, 45),
              (_, __) => GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => _onTab(t.$1),
              ),
            ),
          ],
          // Search bar — x=948 y=120 w=249 h=45 r=16
          FigmaChild(
            const FigmaBox(948, 120, 249, 45),
            (_, s) => Container(
              decoration: BoxDecoration(
                color: const Color(0xFF010717),
                borderRadius: BorderRadius.circular(s.px(16)),
                border: Border.all(color: _cSbr, width: s.px(1)),
              ),
              padding: EdgeInsets.symmetric(horizontal: s.px(12)),
              child: Row(
                children: [
                  Text('⌕',
                      style: TextStyle(
                          color: _cMuted.withValues(alpha: 0.7),
                          fontSize: _fz(s, 18))),
                  SizedBox(width: s.px(8)),
                  Text('Search emails',
                      style: TextStyle(
                          color: _cMuted.withValues(alpha: 0.65),
                          fontSize: _fz(s, 17))),
                ],
              ),
            ),
          ),

          // Left list panel — x=23 y=212 w=535 h=567 r=29.66
          FigmaChild(
            const FigmaBox(23, 212, 535, 567),
            (_, s) => _panel(s, 29.66),
          ),
          FigmaChild(
            const FigmaBox(23, 212, 535, 567),
            (_, s) => _listContent(s),
          ),
          // Left scrollbar track — abs x=542 y=261 w=9 h=456
          FigmaChild(
            const FigmaBox(542, 261, 9, 456),
            (_, s) => _scrollTrack(s),
          ),

          // Right detail panel — x=570 y=212 w=667 h=567 r=29.66
          FigmaChild(
            const FigmaBox(570, 212, 667, 567),
            (_, s) => _panel(s, 29.66),
          ),
          FigmaChild(
            const FigmaBox(570, 212, 667, 567),
            (_, s) => _detailContent(s),
          ),
          // Right scrollbar track — abs x=1220 y=243 w=9 h=510
          FigmaChild(
            const FigmaBox(1220, 243, 9, 510),
            (_, s) => _scrollTrack(s),
          ),
        ],
      ),
    );
  }

  // ── Reusable bits ─────────────────────────────────────────────────────────

  Widget _panel(FigmaScale s, double radius,
          {Color top = _cPnlTop, Color bot = _cPnlBot}) =>
      Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [top, bot],
          ),
          borderRadius: BorderRadius.circular(s.px(radius)),
          border: Border.all(color: _cBdr, width: s.px(1)),
        ),
      );

  Widget _scrollTrack(FigmaScale s) => DecoratedBox(
        decoration: BoxDecoration(
          color: _cSbTrack,
          borderRadius: BorderRadius.circular(s.px(6)),
        ),
        child: Align(
          alignment: Alignment.topCenter,
          child: FractionallySizedBox(
            heightFactor: 0.16,
            child: Container(
              decoration: BoxDecoration(
                color: _cBlue,
                borderRadius: BorderRadius.circular(s.px(6)),
              ),
            ),
          ),
        ),
      );

  Widget _text(String t, double fs, Color c,
          {FontWeight weight = FontWeight.w500,
          TextAlign align = TextAlign.left,
          int? maxLines}) =>
      Align(
        alignment: align == TextAlign.right
            ? Alignment.centerRight
            : Alignment.centerLeft,
        child: Text(
          t,
          textAlign: align,
          maxLines: maxLines,
          overflow: maxLines != null ? TextOverflow.ellipsis : TextOverflow.clip,
          style: TextStyle(color: c, fontSize: fs, fontWeight: weight),
        ),
      );

  // ── List content (sections + rows) ─────────────────────────────────────────

  Widget _listContent(FigmaScale s) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    final emails = _filtered;
    if (emails.isEmpty) {
      return Center(
        child: Text('No emails',
            style: TextStyle(color: _cMuted, fontSize: _fz(s, 18))),
      );
    }
    final today = emails.where((e) => e['is_today'] == true).toList();
    final earlier = emails.where((e) => e['is_today'] != true).toList();

    final children = <Widget>[];
    if (today.isNotEmpty) {
      children.add(_sectionLabel('NEW', s));
      children.addAll(today.map((e) => _row(e, s)));
    }
    if (today.isNotEmpty && earlier.isNotEmpty) {
      children.add(_listDivider(s));
    }
    if (earlier.isNotEmpty) {
      children.add(_sectionLabel('EARLIER', s));
      children.addAll(earlier.map((e) => _row(e, s)));
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(s.px(29.66)),
      child: ListView(
        padding: EdgeInsets.only(top: s.px(11), bottom: s.px(24)),
        children: children,
      ),
    );
  }

  Widget _sectionLabel(String t, FigmaScale s) => Padding(
        padding: EdgeInsets.only(left: s.px(28), bottom: s.px(6)),
        child: Text(t,
            style: TextStyle(
                color: _cBlue,
                fontSize: _fz(s, 20),
                fontWeight: FontWeight.w700)),
      );

  Widget _listDivider(FigmaScale s) => Padding(
        padding: EdgeInsets.only(left: s.px(29), top: s.px(8), bottom: s.px(8)),
        child: Container(
          width: s.px(478),
          height: s.px(3),
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [Color(0x0002154D), Color(0xFF0F296C), Color(0x0002154D)],
            ),
          ),
        ),
      );

  Widget _row(Map<String, dynamic> e, FigmaScale s) {
    final unread = e['is_read'] != true;
    final selected = _selected != null && _selected!['id'] == e['id'];
    final sender = (e['sender'] ?? '').toString();
    final time = (e['time'] ?? '').toString();
    final subject = (e['subject'] ?? '(no subject)').toString();
    final preview = (e['preview'] ?? '').toString();

    if (selected || unread) {
      // Selected/unread row — w=480 h=122.61, x inset 28
      return Padding(
        padding: EdgeInsets.only(left: s.px(28), bottom: s.px(10)),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () => _select(e),
          child: SizedBox(
            width: s.px(480),
            height: s.px(122.61),
            child: Stack(
              children: [
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: selected ? _cSelFill : null,
                      gradient: selected
                          ? null
                          : const LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [_cPnlTop, _cPnlBot],
                            ),
                      borderRadius: BorderRadius.circular(s.px(11)),
                      border: Border.all(
                        color: selected ? _cSel : _cUnreadBdr,
                        width: selected ? s.px(1.6) : s.px(0.8),
                      ),
                    ),
                  ),
                ),
                _dot(s, 11.3, 19, 10.43, true),
                if (selected)
                  Positioned(
                    left: s.px(373.41),
                    top: s.px(7.14),
                    width: s.px(53.17),
                    height: s.px(106.34),
                    child: Center(
                      child: Text('›',
                          style: TextStyle(
                              color: _cBlue.withValues(alpha: 0.7),
                              fontSize: _fz(s, 34))),
                    ),
                  ),
                _pos(s, 33.05, 8.57, 240, 31,
                    _text(sender, _fz(s, 26), _cWhite, weight: FontWeight.w600, maxLines: 1)),
                _pos(s, 364.34, 12.18, 92, 25,
                    _text(time, _fz(s, 21), _cBlue, align: TextAlign.right, maxLines: 1)),
                _pos(s, 33.05, 47.70, 340, 27,
                    _text(subject, _fz(s, 23), _cWhite, weight: FontWeight.w600, maxLines: 1)),
                _pos(s, 33.05, 82.48, 340, 24,
                    _text(preview, _fz(s, 20), _cMuted, maxLines: 1)),
              ],
            ),
          ),
        ),
      );
    }

    // Read row — w=440 h=90, x inset 42, transparent bg
    return Padding(
      padding: EdgeInsets.only(left: s.px(42), bottom: s.px(10)),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => _select(e),
        child: SizedBox(
          width: s.px(440),
          height: s.px(90),
          child: Stack(
            children: [
              _dot(s, 0, 10.33, 10.33, false),
              _pos(s, 21.52, 0, 220, 31,
                  _text(sender, _fz(s, 26), _cWhite, maxLines: 1)),
              Positioned(
                right: 0,
                top: s.px(3.58),
                width: s.px(81),
                height: s.px(25),
                child: _text(time, _fz(s, 21), _cBlue, align: TextAlign.right, maxLines: 1),
              ),
              _pos(s, 21.52, 38.73, 310, 27,
                  _text(subject, _fz(s, 22), _cWhite, maxLines: 1)),
              _pos(s, 21.52, 65.73, 340, 24,
                  _text(preview, _fz(s, 20), _cMuted, maxLines: 1)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _pos(FigmaScale s, double x, double y, double w, double h, Widget child) =>
      Positioned(
        left: s.px(x),
        top: s.px(y),
        width: s.px(w),
        height: s.px(h),
        child: child,
      );

  Widget _dot(FigmaScale s, double x, double y, double d, bool unread) => Positioned(
        left: s.px(x),
        top: s.px(y),
        width: s.px(d),
        height: s.px(d),
        child: unread
            ? const DecoratedBox(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [_cDotTop, _cDotBot],
                  ),
                ),
              )
            : DecoratedBox(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                      color: _cMuted.withValues(alpha: 0.5), width: s.px(0.9)),
                ),
              ),
      );

  // ── Detail content ──────────────────────────────────────────────────────

  Widget _detailContent(FigmaScale s) {
    if (_selected == null) {
      return Center(
        child: Text('Select an email to read',
            style: TextStyle(
                color: _cMuted.withValues(alpha: 0.55), fontSize: _fz(s, 20))),
      );
    }
    final d = _detail;
    final sender = (d['sender'] ?? '').toString();
    final to = (d['to'] ?? '').toString().split('<').first.trim();
    final subject = (d['subject'] ?? '(no subject)').toString();
    final body = (d['body'] ?? d['preview'] ?? '').toString();
    final initials = sender
            .split(' ')
            .where((w) => w.isNotEmpty)
            .map((w) => w[0])
            .take(2)
            .join()
            .toUpperCase()
            .trim();

    return Stack(
      children: [
        // Action bar
        _pos(s, 39, 17, 72, 24, _actionBtn(s, '← Back', _detailBack)),
        _pos(s, 133, 17, 134, 24, _actionBtn(s, '✉ Mark unread', _markUnread)),
        _pos(s, 298, 17, 92, 24, _actionBtn(s, '⬚ Archive', _archive)),
        // More button — x=528 y=8 w=101 h=42 r=11
        Positioned(
          left: s.px(528),
          top: s.px(8),
          width: s.px(101),
          height: s.px(42),
          child: Container(
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [_cMoreTop, _cPnlBot],
              ),
              borderRadius: BorderRadius.circular(s.px(11)),
              border: Border.all(color: _cSbr, width: s.px(1)),
            ),
            alignment: Alignment.center,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('···',
                    style: TextStyle(color: _cBlue, fontSize: _fz(s, 20))),
                SizedBox(width: s.px(6)),
                Text('More',
                    style: TextStyle(color: _cBlue, fontSize: _fz(s, 18))),
              ],
            ),
          ),
        ),
        // Divider — x=28 y=57 w=611 h=3
        Positioned(
          left: s.px(28),
          top: s.px(57),
          width: s.px(611),
          height: s.px(3),
          child: const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [Color(0x0002154D), Color(0xFF0F296C), Color(0x0002154D)],
              ),
            ),
          ),
        ),
        // Avatar — x=50 y=79 w/h=48
        Positioned(
          left: s.px(50),
          top: s.px(79),
          width: s.px(48),
          height: s.px(48),
          child: Container(
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [_cDotTop, _cDotBot],
              ),
            ),
            alignment: Alignment.center,
            child: Text(initials.isEmpty ? '?' : initials,
                style: TextStyle(
                    color: _cWhite,
                    fontSize: _fz(s, 16),
                    fontWeight: FontWeight.w600)),
          ),
        ),
        _dot(s, 28, 99, 12, true),
        _pos(s, 107, 74, 220, 27,
            _text(sender, _fz(s, 23), _cWhite, weight: FontWeight.w600, maxLines: 1)),
        _pos(s, 107, 108, 28, 24, _text('To:', _fz(s, 20), _cMuted)),
        _pos(s, 144, 108, 220, 24,
            _text(to.isEmpty ? 'me' : to, _fz(s, 20), _cBlue, maxLines: 1)),
        _pos(s, 32, 146, 580, 30,
            _text(subject, _fz(s, 25), _cWhite, weight: FontWeight.w600, maxLines: 1)),
        // Body scroll — x=32 y=189 w=580 h=358
        Positioned(
          left: s.px(32),
          top: s.px(189),
          width: s.px(580),
          height: s.px(358),
          child: SingleChildScrollView(
            child: Text(
              body,
              style: TextStyle(
                  color: _cWhite, fontSize: _fz(s, 18), height: 1.45),
            ),
          ),
        ),
      ],
    );
  }

  Widget _actionBtn(FigmaScale s, String label, VoidCallback onTap) =>
      GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Align(
          alignment: Alignment.centerLeft,
          child: Text(label,
              style: TextStyle(color: _cWhite, fontSize: _fz(s, 18))),
        ),
      );
}
