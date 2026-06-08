import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/screens/recording/summary_review_screen.dart';

/// Ported from `screens/meeting_detail.py`. Reuses the summary review view —
/// both present a stored meeting's summary, tabs, and transcript.
class MeetingDetailScreen extends StatelessWidget {
  const MeetingDetailScreen({
    super.key,
    required this.config,
    required this.api,
    this.meetingId,
  });

  final AppConfig config;
  final ApiClient api;
  final String? meetingId;

  @override
  Widget build(BuildContext context) {
    return SummaryReviewScreen(
      config: config,
      api: api,
      meetingId: meetingId,
    );
  }
}
