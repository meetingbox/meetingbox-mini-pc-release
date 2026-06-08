import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.config,
    required this.api,
    required this.bridge,
  });

  final AppConfig config;
  final ApiClient api;
  final DeviceBridgeClient bridge;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _canvas = Size(1260, 800);

  Timer? _clockTimer;
  DateTime _now = DateTime.now();
  bool _backendOk = false;
  bool _bridgeOk = false;
  bool _recording = false;
  List<Map<String, dynamic>> _meetings = const [];

  @override
  void initState() {
    super.initState();
    _clockTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() => _now = DateTime.now());
    });
    _refresh();
  }

  Future<void> _refresh() async {
    final results = await Future.wait<Object>([
      widget.api.healthCheck(),
      widget.bridge.isHealthy(),
      widget.api.getRecordingStatus(),
      widget.api.listMeetings(limit: 3),
    ]);

    if (!mounted) return;
    final status = results[2] as Map<String, dynamic>;
    setState(() {
      _backendOk = results[0] as bool;
      _bridgeOk = results[1] as bool;
      _recording = status['recording'] == true || status['is_recording'] == true;
      _meetings = results[3] as List<Map<String, dynamic>>;
    });
  }

  @override
  void dispose() {
    _clockTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final greeting = _greeting();
    final hourMinute = DateFormat('h:mm').format(_now);
    final amPm = DateFormat('a').format(_now);
    final dateText = DateFormat('MMM d, yyyy').format(_now);
    final firstMeeting = _meetings.isNotEmpty ? _meetings.first : null;
    final meetingTitle = firstMeeting?['title'] as String? ?? 'Product Sync';
    final meetingTime = _meetingTime(firstMeeting) ?? '11:00 AM';

    return Scaffold(
      backgroundColor: const Color(0xFF01081A),
      body: Center(
        child: FittedBox(
          fit: BoxFit.contain,
          child: SizedBox.fromSize(
            size: _canvas,
            child: Stack(
              children: [
                const ColoredBox(color: Color(0xFF01081A)),
                _header(greeting),
                _heroCard(hourMinute, amPm, dateText, meetingTitle, meetingTime),
                _summaryCard(meetingTitle),
                _briefCard(),
                _scheduleCard(meetingTitle, meetingTime),
                _metricCard(
                  left: 542.42,
                  width: 334.78,
                  icon: 'assets/home/figma/icon_email_circle.png',
                  value: '—',
                  label: 'New emails',
                  route: '/emails',
                ),
                _metricCard(
                  left: 885.67,
                  width: 350.31,
                  icon: 'assets/home/figma/icon_tasks_circle.png',
                  value: '—',
                  label: 'Tasks due',
                  route: '/tasks',
                ),
                _sayBar(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _header(String greeting) {
    return Stack(
      children: [
        _pos(
          left: 24.01,
          top: 33.9,
          width: 700,
          height: 56,
          child: Text(
            greeting,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppColors.white,
              fontSize: 42.38,
              fontWeight: FontWeight.w700,
              height: 1.05,
              letterSpacing: -0.6,
            ),
          ),
        ),
        _pos(
          left: 900,
          top: 7,
          width: 250,
          height: 28,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              _smallStatus(_backendOk ? 'API' : 'API off', _backendOk),
              const SizedBox(width: 8),
              _smallStatus(_bridgeOk ? 'Device' : 'Bridge off', _bridgeOk),
            ],
          ),
        ),
        // Settings — last in stack so status text never covers it.
        _settingsButton(),
      ],
    );
  }

  /// Top-right settings control (Figma 1159.71, 21.19). Uses a tracked PNG
  /// under assets/calendar/figma so release builds always bundle the icon.
  Widget _settingsButton() {
    return _pos(
      left: 1159.71,
      top: 21.19,
      width: 76.28,
      height: 76.28,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: () => _go('/settings'),
          child: DecoratedBox(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFF000F33), Color(0xFF01081A)],
              ),
              border: Border.all(color: AppColors.rowBorder),
            ),
            child: Center(
              child: Image.asset(
                'assets/calendar/figma/icon_settings_badge.png',
                width: 76.28,
                height: 76.28,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const Icon(
                  Icons.settings,
                  color: AppColors.white,
                  size: 34,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _heroCard(
    String hourMinute,
    String amPm,
    String dateText,
    String meetingTitle,
    String meetingTime,
  ) {
    return _figmaCard(
      left: 24.01,
      top: 114.42,
      width: 579.15,
      height: 372.03,
      radius: 19.48,
      solid: AppColors.heroBg,
      child: Stack(
        children: [
          _inside(
            left: -10.39,
            top: -1.3,
            width: 599.92,
            height: 375.28,
            child: _asset('assets/home/figma/hero_bg.png', fit: BoxFit.fill),
          ),
          _inside(
            left: 29.87,
            top: 34.07,
            width: 280,
            height: 82,
            child: RichText(
              text: TextSpan(
                children: [
                  TextSpan(
                    text: hourMinute,
                    style: const TextStyle(
                      color: AppColors.white,
                      fontSize: 64.93,
                      fontWeight: FontWeight.w800,
                      height: 0.95,
                      letterSpacing: -1.6,
                    ),
                  ),
                  TextSpan(
                    text: ' $amPm',
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 22.72,
                      height: 1,
                    ),
                  ),
                ],
              ),
            ),
          ),
          _inside(
            left: 29.87,
            top: 111.33,
            width: 240,
            height: 28,
            child: Text(
              dateText,
              style: const TextStyle(
                color: AppColors.white,
                fontSize: 23.38,
                fontWeight: FontWeight.w600,
                height: 1,
              ),
            ),
          ),
          _inside(
            left: 439.56,
            top: 44.46,
            width: 58.7,
            height: 58.7,
            child: _asset('assets/home/figma/icon_sun_brief.png'),
          ),
          const _HomeText(
            left: 492.8,
            top: 51.6,
            width: 100,
            height: 27,
            text: '--°C',
            fontSize: 22.72,
            weight: FontWeight.w800,
          ),
          const _HomeText(
            left: 492.8,
            top: 82.76,
            width: 100,
            height: 23,
            text: '--',
            fontSize: 19.48,
            color: AppColors.muted,
            weight: FontWeight.w500,
          ),
          _recordingButton(),
          const _HomeText(
            left: 29.87,
            top: 216.2,
            width: 110,
            height: 24,
            text: 'Next up',
            fontSize: 18.18,
            color: Color(0xFF3481F1),
            weight: FontWeight.w700,
          ),
          _inside(
            left: 29.87,
            top: 255.16,
            width: 31.18,
            height: 30.82,
            child: _asset('assets/home/figma/icon_calendar_row.png'),
          ),
          _HomeText(
            left: 64.28,
            top: 256.45,
            width: 160,
            height: 22,
            text: meetingTime,
            fontSize: 18.18,
            color: const Color(0xFF3481F1),
            weight: FontWeight.w700,
          ),
          _HomeText(
            left: 29.87,
            top: 289.57,
            width: 240,
            height: 26,
            text: 'Now: $meetingTitle',
            fontSize: 20.13,
            weight: FontWeight.w800,
          ),
          const _HomeText(
            left: 29.87,
            top: 322.68,
            width: 120,
            height: 22,
            text: '+2 more',
            fontSize: 18.18,
            color: Color(0xFF3481F1),
            weight: FontWeight.w800,
          ),
        ],
      ),
    );
  }

  Widget _recordingButton() {
    return _inside(
      left: 277.24,
      top: 235.68,
      width: 268.39,
      height: 108.26,
      child: GestureDetector(
        onTap: () => _go('/recording'),
        child: Stack(
        children: [
          _asset('assets/home/figma/recording_btn_bg.png', fit: BoxFit.fill),
          _inside(
            left: 17.5,
            top: 20.74,
            width: 65.48,
            height: 65.48,
            child: _asset('assets/home/figma/mic_orb_mini.png'),
          ),
          _HomeText(
            left: 106.96,
            top: 31.76,
            width: 150,
            height: 26,
            text: _recording ? 'Recording' : 'Start Recording',
            fontSize: 19.45,
            weight: FontWeight.w800,
          ),
          const _HomeText(
            left: 95.94,
            top: 60.94,
            width: 170,
            height: 19,
            text: 'Tap or say "start recording"',
            fontSize: 15.56,
            weight: FontWeight.w600,
          ),
        ],
        ),
      ),
    );
  }

  Widget _summaryCard(String meetingTitle) {
    return _figmaCard(
      left: 611.64,
      top: 114.42,
      width: 307.94,
      height: 371.5,
      radius: 16.95,
      onTap: () => _go('/meetings'),
      child: Stack(
        children: [
          _inside(
            left: 21.19,
            top: 50.85,
            width: 39.55,
            height: 39.55,
            child: _asset('assets/home/figma/icon_file.png'),
          ),
          const _HomeText(
            left: 62.15,
            top: 57.91,
            width: 230,
            height: 30,
            text: 'Last Meeting Summary',
            fontSize: 25.43,
            color: Color(0xFFA4A4AC),
            weight: FontWeight.w700,
          ),
          _HomeText(
            left: 28.25,
            top: 104.53,
            width: 250,
            height: 48,
            text: meetingTitle,
            fontSize: 38.98,
            weight: FontWeight.w700,
          ),
          const _HomeText(
            left: 28.25,
            top: 153.97,
            width: 260,
            height: 30,
            text: 'Today, 10:00 AM',
            fontSize: 25.43,
            color: AppColors.muted,
            weight: FontWeight.w600,
          ),
          const _HomeText(
            left: 28.25,
            top: 238.72,
            width: 180,
            height: 30,
            text: 'Open summary',
            fontSize: 25.43,
            color: AppColors.blue,
            weight: FontWeight.w700,
          ),
          _inside(
            left: 203.25,
            top: 234.72,
            width: 12,
            height: 22,
            child: _asset('assets/home/figma/icon_arrow.png'),
          ),
          _inside(
            left: 28.25,
            top: 274.04,
            width: 46.19,
            height: 46.04,
            child: ClipOval(child: _asset('assets/home/figma/avatar_1.png')),
          ),
          _inside(
            left: 85.26,
            top: 274.99,
            width: 46.19,
            height: 46.04,
            child: ClipOval(child: _asset('assets/home/figma/avatar_2.png')),
          ),
          _inside(
            left: 142.27,
            top: 274.04,
            width: 45.61,
            height: 45.61,
            child: Container(
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: const Color(0xFF010A1B),
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.rowBorder),
              ),
              child: const Text(
                '+2',
                style: TextStyle(
                  color: AppColors.white,
                  fontSize: 21.17,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _briefCard() {
    return _figmaCard(
      left: 928.05,
      top: 114.42,
      width: 307.94,
      height: 371.5,
      radius: 16.95,
      onTap: () => _go('/morning-brief'),
      child: Stack(
        children: [
          _inside(
            left: 29.66,
            top: 14.13,
            width: 28.25,
            height: 28.25,
            child: _asset('assets/home/figma/icon_sun_brief.png'),
          ),
          const _HomeText(
            left: 72.04,
            top: 14.13,
            width: 200,
            height: 35,
            text: 'Morning Brief',
            fontSize: 28.81,
            color: Color(0xFFA4A4AC),
            weight: FontWeight.w700,
          ),
          _briefRow(
            top: 57.91,
            icon: 'assets/home/figma/icon_calendar_row.png',
            title: 'Briefing ready',
            sub: 'Ask Tony for a briefing',
          ),
          _briefRow(
            top: 137.02,
            icon: 'assets/home/figma/icon_weather.png',
            title: 'Weather: --°C',
            sub: '--',
          ),
          _briefRow(
            top: 216.12,
            height: 125.72,
            icon: 'assets/home/figma/icon_email.png',
            title: 'email:',
            sub: 'Connect Gmail for updates',
          ),
          const _HomeText(
            left: 107,
            top: 344,
            width: 90,
            height: 28,
            text: 'View all',
            fontSize: 18.65,
            color: AppColors.blue,
            weight: FontWeight.w700,
          ),
          _inside(
            left: 193.52,
            top: 344.66,
            width: 11.3,
            height: 22.6,
            child: _asset('assets/home/figma/icon_arrow.png'),
          ),
        ],
      ),
    );
  }

  Widget _briefRow({
    required double top,
    required String icon,
    required String title,
    required String sub,
    double height = 73.45,
  }) {
    return _inside(
      left: 9.89,
      top: top,
      width: 288.16,
      height: height,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF010B26),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: AppColors.rowBorder),
        ),
        child: Stack(
          children: [
            _inside(left: 16, top: height / 2 - 18, width: 38, height: 38, child: _asset(icon)),
            _HomeText(
              left: 81.37,
              top: height > 80 ? 21.46 : 13.77,
              width: 210,
              height: 30,
              text: title,
              fontSize: 25.43,
              color: title == 'email:' ? AppColors.white : const Color(0xFFA4A4AC),
              weight: FontWeight.w800,
            ),
            _HomeText(
              left: 81.37,
              top: height > 80 ? 49.44 : 41.32,
              width: 210,
              height: 24,
              text: sub,
              fontSize: 20.34,
              color: AppColors.muted,
              weight: FontWeight.w600,
            ),
          ],
        ),
      ),
    );
  }

  Widget _scheduleCard(String title, String time) {
    return _figmaCard(
      left: 24.01,
      top: 507.11,
      width: 509.93,
      height: 144.08,
      radius: 22.6,
      onTap: () => _go('/calendar'),
      child: Stack(
        children: [
          _inside(
            left: 40.96,
            top: 26.84,
            width: 93.23,
            height: 93.23,
            child: _asset('assets/home/figma/icon_schedule_circle.png'),
          ),
          _HomeText(
            left: 156.79,
            top: 16.95,
            width: 230,
            height: 45,
            text: time.replaceAll(' AM', '').replaceAll(' PM', ''),
            fontSize: 38.14,
            weight: FontWeight.w700,
          ),
          _HomeText(
            left: 156.79,
            top: 67.8,
            width: 260,
            height: 32,
            text: 'Now: $title',
            fontSize: 27.12,
            color: AppColors.muted,
            weight: FontWeight.w600,
          ),
          const _HomeText(
            left: 156.79,
            top: 101.7,
            width: 90,
            height: 25,
            text: '+2 more',
            fontSize: 21.19,
            color: AppColors.blue,
            weight: FontWeight.w700,
          ),
          _inside(
            left: 449.19,
            top: 62.15,
            width: 19.78,
            height: 39.55,
            child: _asset('assets/home/figma/icon_arrow.png'),
          ),
        ],
      ),
    );
  }

  Widget _metricCard({
    required double left,
    required double width,
    required String icon,
    required String value,
    required String label,
    String? route,
  }) {
    final iconLeft = width > 340 ? 36.73 : 22.6;
    final textLeft = iconLeft + 115.83;
    return _figmaCard(
      left: left,
      top: 507.11,
      width: width,
      height: 144.08,
      radius: 22.6,
      onTap: route == null ? null : () => _go(route),
      child: Stack(
        children: [
          _inside(left: iconLeft, top: 25.43, width: 93.23, height: 93.23, child: _asset(icon)),
          _HomeText(
            left: textLeft,
            top: 36.73,
            width: 80,
            height: 45,
            text: value,
            fontSize: 38.14,
            weight: FontWeight.w700,
          ),
          _HomeText(
            left: textLeft,
            top: 86.17,
            width: 170,
            height: 36,
            text: label,
            fontSize: 30.52,
            color: AppColors.muted,
            weight: FontWeight.w700,
          ),
          _inside(
            left: width - 42,
            top: 56.5,
            width: 19.78,
            height: 39.55,
            child: _asset('assets/home/figma/icon_arrow.png'),
          ),
        ],
      ),
    );
  }

  Widget _sayBar() {
    return _figmaCard(
      left: 38.14,
      top: 672.38,
      width: 1183.72,
      height: 100.29,
      radius: 29.66,
      child: Stack(
        children: [
          _inside(
            left: 22.6,
            top: 32.49,
            width: 33.67,
            height: 33.66,
            child: _asset('assets/home/figma/icon_sparkle.png'),
          ),
          const _HomeText(
            left: 46.49,
            top: 50.73,
            width: 20,
            height: 27,
            text: '+',
            fontSize: 22.6,
            color: Color(0xFF1B76FA),
            weight: FontWeight.w800,
          ),
          const _HomeText(
            left: 80.51,
            top: 15.54,
            width: 160,
            height: 32,
            text: 'Try saying',
            fontSize: 26.84,
            color: AppColors.blue,
            weight: FontWeight.w700,
          ),
          const _HomeText(
            left: 80.51,
            top: 56.5,
            width: 560,
            height: 33,
            text: '"Schedule a meeting tomorrow at 4 PM"',
            fontSize: 27.12,
            color: AppColors.muted,
            weight: FontWeight.w600,
          ),
          _inside(
            left: 591.86,
            top: 4.24,
            width: 91.82,
            height: 91.82,
            child: _asset('assets/home/figma/icon_voice_orb.png'),
          ),
          _inside(
            left: 1084.84,
            top: 16.95,
            width: 76.28,
            height: 67.8,
            child: _asset('assets/home/figma/icon_keyboard.png'),
          ),
        ],
      ),
    );
  }

  Widget _figmaCard({
    required double left,
    required double top,
    required double width,
    required double height,
    required double radius,
    required Widget child,
    Color? solid,
    VoidCallback? onTap,
  }) {
    final card = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: Container(
        decoration: BoxDecoration(
          color: solid,
          gradient: solid == null
              ? const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [AppColors.cardTop, AppColors.cardBottom],
                )
              : null,
          border: Border.all(color: const Color(0xFF232942)),
          borderRadius: BorderRadius.circular(radius),
        ),
        child: child,
      ),
    );
    return _pos(
      left: left,
      top: top,
      width: width,
      height: height,
      child: onTap == null
          ? card
          : GestureDetector(onTap: onTap, child: card),
    );
  }

  void _go(String route) {
    GoRouter.of(context).push(route);
  }

  Widget _smallStatus(String label, bool enabled) {
    return Text(
      label,
      style: TextStyle(
        color: enabled ? AppColors.blue : const Color(0xFF8A8A92),
        fontSize: 12,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  String _greeting() {
    final h = _now.hour;
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  String? _meetingTime(Map<String, dynamic>? meeting) {
    final raw = meeting?['start_time'] ?? meeting?['started_at'] ?? meeting?['created_at'];
    if (raw is! String || raw.isEmpty) return null;
    try {
      final normalized = raw.endsWith('Z') ? raw.replaceFirst('Z', '+00:00') : raw;
      return DateFormat('h:mm a').format(DateTime.parse(normalized).toLocal());
    } catch (_) {
      return null;
    }
  }

  static Widget _asset(String path, {BoxFit fit = BoxFit.contain}) {
    return Image.asset(
      path,
      fit: fit,
      errorBuilder: (_, __, ___) => const SizedBox.shrink(),
    );
  }

  static Widget _pos({
    required double left,
    required double top,
    required double width,
    required double height,
    required Widget child,
  }) {
    return Positioned(left: left, top: top, width: width, height: height, child: child);
  }

  static Widget _inside({
    required double left,
    required double top,
    required double width,
    required double height,
    required Widget child,
  }) {
    return Positioned(left: left, top: top, width: width, height: height, child: child);
  }
}

class _HomeText extends StatelessWidget {
  const _HomeText({
    required this.left,
    required this.top,
    required this.width,
    required this.height,
    required this.text,
    required this.fontSize,
    this.color = AppColors.white,
    this.weight = FontWeight.w600,
  });

  final double left;
  final double top;
  final double width;
  final double height;
  final String text;
  final double fontSize;
  final Color color;
  final FontWeight weight;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: left,
      top: top,
      width: width,
      height: height,
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: color,
          fontSize: fontSize,
          fontWeight: weight,
          height: 1,
        ),
      ),
    );
  }
}
