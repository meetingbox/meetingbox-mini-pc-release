import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/widgets/device_background.dart';
import 'package:meetingbox_device_ui/widgets/status_bar.dart';

/// Emails screen, ported from `screens/emails.py`. Lists Gmail rows with
/// folder filters; tapping a row opens the body and marks it read.
class EmailsScreen extends StatefulWidget {
  const EmailsScreen({super.key, required this.config, required this.api});

  final AppConfig config;
  final ApiClient api;

  @override
  State<EmailsScreen> createState() => _EmailsScreenState();
}

class _EmailsScreenState extends State<EmailsScreen> {
  static const _filters = ['all', 'unread', 'important'];
  String _filter = 'all';
  List<Map<String, dynamic>> _emails = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final emails = widget.config.mockBackend
        ? _mock()
        : await widget.api.getEmails(filter: _filter, limit: 50);
    if (!mounted) return;
    setState(() {
      _emails = emails;
      _loading = false;
    });
  }

  List<Map<String, dynamic>> _mock() => [
        {'id': '1', 'from': 'Alex Rivera', 'subject': 'Q3 roadmap review', 'snippet': 'Here is the draft for tomorrow…', 'unread': true},
        {'id': '2', 'from': 'GitHub', 'subject': 'PR #482 merged', 'snippet': 'Your pull request was merged.', 'unread': false},
        {'id': '3', 'from': 'Sam Park', 'subject': 'Design review notes', 'snippet': 'Thanks everyone for the feedback.', 'unread': true},
      ];

  List<Map<String, dynamic>> get _filtered {
    if (_filter == 'unread') {
      return _emails.where((e) => e['unread'] == true).toList();
    }
    if (_filter == 'important') {
      return _emails.where((e) => e['important'] == true).toList();
    }
    return _emails;
  }

  Future<void> _open(Map<String, dynamic> e) async {
    setState(() => e['unread'] = false);
    if (!widget.config.mockBackend) {
      await widget.api.markEmailRead((e['id'] ?? '').toString());
    }
    if (!mounted) return;
    await showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      isScrollControlled: true,
      builder: (_) => _EmailDetailSheet(
        config: widget.config,
        api: widget.api,
        email: e,
      ),
    );
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
                deviceName: 'Emails',
                backButton: true,
                showSettings: false,
                onBack: () =>
                    context.canPop() ? context.pop() : context.go('/home'),
              ),
              _filterBar(),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : _filtered.isEmpty
                        ? const Center(
                            child: Text('No emails',
                                style: TextStyle(
                                    color: AppColors.gray400, fontSize: 18)))
                        : ListView.separated(
                            padding:
                                const EdgeInsets.all(Spacing.screenPadding),
                            itemCount: _filtered.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 8),
                            itemBuilder: (_, i) => _row(_filtered[i]),
                          ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _filterBar() => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            for (final f in _filters)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: GestureDetector(
                  onTap: () {
                    setState(() => _filter = f);
                    if (!widget.config.mockBackend) _load();
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: _filter == f
                          ? AppColors.primaryStart
                          : const Color(0xDB1F2A3B),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      f[0].toUpperCase() + f.substring(1),
                      style: TextStyle(
                        color: _filter == f ? Colors.white : AppColors.gray300,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      );

  Widget _row(Map<String, dynamic> e) {
    final unread = e['unread'] == true;
    return GestureDetector(
      onTap: () => _open(e),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xDB1F2A3B),
          borderRadius: BorderRadius.circular(Layout.borderRadius),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 8,
              height: 8,
              margin: const EdgeInsets.only(top: 6, right: 10),
              decoration: BoxDecoration(
                color: unread ? AppColors.primaryStart : Colors.transparent,
                shape: BoxShape.circle,
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (e['from'] ?? e['sender'] ?? '').toString(),
                    style: TextStyle(
                      color: AppColors.white,
                      fontSize: 15,
                      fontWeight: unread ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    (e['subject'] ?? '(no subject)').toString(),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: AppColors.gray300, fontSize: 14),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    (e['snippet'] ?? e['preview'] ?? '').toString(),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: AppColors.gray500, fontSize: 13),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmailDetailSheet extends StatefulWidget {
  const _EmailDetailSheet({
    required this.config,
    required this.api,
    required this.email,
  });

  final AppConfig config;
  final ApiClient api;
  final Map<String, dynamic> email;

  @override
  State<_EmailDetailSheet> createState() => _EmailDetailSheetState();
}

class _EmailDetailSheetState extends State<_EmailDetailSheet> {
  Map<String, dynamic> _detail = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final d = widget.config.mockBackend
        ? {...widget.email, 'body': widget.email['snippet']}
        : await widget.api.getEmailDetail((widget.email['id'] ?? '').toString());
    if (!mounted) return;
    setState(() {
      _detail = d.isEmpty ? widget.email : d;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.92,
      builder: (_, controller) => Padding(
        padding: const EdgeInsets.all(20),
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                controller: controller,
                children: [
                  Text(
                    (_detail['subject'] ?? '(no subject)').toString(),
                    style: const TextStyle(
                      color: AppColors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'From: ${(_detail['from'] ?? _detail['sender'] ?? '').toString()}',
                    style: const TextStyle(color: AppColors.gray400, fontSize: 14),
                  ),
                  const Divider(color: AppColors.gray800, height: 28),
                  Text(
                    (_detail['body'] ?? _detail['snippet'] ?? '').toString(),
                    style: const TextStyle(color: AppColors.gray300, fontSize: 15),
                  ),
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      TextButton.icon(
                        onPressed: () async {
                          if (!widget.config.mockBackend) {
                            await widget.api.archiveEmail(
                                (widget.email['id'] ?? '').toString());
                          }
                          if (context.mounted) Navigator.pop(context);
                        },
                        icon: const Icon(Icons.archive_outlined),
                        label: const Text('Archive'),
                      ),
                      TextButton.icon(
                        onPressed: () async {
                          if (!widget.config.mockBackend) {
                            await widget.api.markEmailRead(
                                (widget.email['id'] ?? '').toString(),
                                read: false);
                          }
                          if (context.mounted) Navigator.pop(context);
                        },
                        icon: const Icon(Icons.mark_email_unread_outlined),
                        label: const Text('Mark unread'),
                      ),
                    ],
                  ),
                ],
              ),
      ),
    );
  }
}
