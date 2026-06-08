import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:meetingbox_device_ui/config/app_config.dart';

/// REST client — subset of `device-ui/src/api_client.py` for Phase 0–1.
class ApiClient {
  ApiClient(this.config, {http.Client? client}) : _client = client ?? http.Client();

  final AppConfig config;
  final http.Client _client;

  Map<String, String> get _headers {
    final h = <String, String>{'Content-Type': 'application/json'};
    if (config.deviceAuthToken.isNotEmpty) {
      h['Authorization'] = 'Bearer ${config.deviceAuthToken}';
    }
    return h;
  }

  Uri _uri(String path) => Uri.parse('${config.backendUrl}$path');

  Future<Map<String, dynamic>> getSystemInfo() async {
    try {
      final resp = await _client
          .get(_uri('/api/system/device-info'), headers: _headers)
          .timeout(const Duration(seconds: 12));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}

    try {
      final resp = await _client
          .get(_uri('/api/system/status'), headers: _headers)
          .timeout(const Duration(seconds: 12));
      if (resp.statusCode < 200 || resp.statusCode >= 300) {
        return {};
      }
      final raw = jsonDecode(resp.body) as Map<String, dynamic>;
      final system = raw['system'] as Map<String, dynamic>? ?? {};
      return {
        'device_name': 'MeetingBox',
        'firmware_version': '1.0.0',
        'setup_complete': raw['setup_complete'],
        'disk_used_gb': system['disk_used_gb'],
        'disk_total_gb': system['disk_total_gb'],
      };
    } catch (_) {
      return {};
    }
  }

  /// Persist the device/room name (best-effort; mirrors `set_device_name`).
  Future<bool> setDeviceName(String name) async {
    try {
      final resp = await _client
          .post(
            _uri('/api/system/device-name'),
            headers: _headers,
            body: jsonEncode({'device_name': name}),
          )
          .timeout(const Duration(seconds: 10));
      return resp.statusCode >= 200 && resp.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  /// Claim/pair this device with a dashboard-generated code.
  /// Returns the parsed response; throws [ApiException] on HTTP error.
  Future<Map<String, dynamic>> claimDevice(
    String code, {
    required String deviceName,
  }) async {
    final resp = await _client
        .post(
          _uri('/api/devices/claim'),
          headers: _headers,
          body: jsonEncode({'code': code, 'device_name': deviceName}),
        )
        .timeout(const Duration(seconds: 20));
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      String detail = 'Could not link device.';
      try {
        final body = jsonDecode(resp.body);
        if (body is Map && body['detail'] is String) {
          detail = body['detail'] as String;
        }
      } catch (_) {}
      throw ApiException(detail, resp.statusCode);
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// Notify the backend that on-device setup finished (best-effort).
  Future<bool> postSetupComplete({
    required String wifi,
    String flow = 'wifi_on_device_v1',
  }) async {
    try {
      final resp = await _client
          .post(
            _uri('/api/system/setup-complete'),
            headers: _headers,
            body: jsonEncode({'wifi': wifi, 'flow': flow}),
          )
          .timeout(const Duration(seconds: 12));
      return resp.statusCode >= 200 && resp.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  Future<bool> healthCheck() async {
    try {
      final resp = await _client
          .get(_uri('/api/health'), headers: _headers)
          .timeout(const Duration(seconds: 8));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> getRecordingStatus() async {
    try {
      final resp = await _client
          .get(_uri('/api/meetings/recording-status'), headers: _headers)
          .timeout(const Duration(seconds: 12));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {'recording': false};
  }

  Future<bool> startRecording({String? title}) async {
    try {
      final resp = await _client
          .post(
            _uri('/api/meetings/start-recording'),
            headers: _headers,
            body: jsonEncode({if (title != null) 'title': title}),
          )
          .timeout(const Duration(seconds: 15));
      return resp.statusCode >= 200 && resp.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> stopRecording() async {
    try {
      final resp = await _client
          .post(_uri('/api/meetings/stop-recording'), headers: _headers)
          .timeout(const Duration(seconds: 20));
      if (resp.statusCode >= 200 && resp.statusCode < 300) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {};
  }

  Future<Map<String, dynamic>> getMeetingDetail(String id) async {
    try {
      final resp = await _client
          .get(_uri('/api/meetings/$id'), headers: _headers)
          .timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {};
  }

  Future<List<Map<String, dynamic>>> listMeetings({int limit = 5}) async {
    try {
      final resp = await _client
          .get(
            _uri('/api/meetings/?limit=$limit&offset=0'),
            headers: _headers,
          )
          .timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        final body = jsonDecode(resp.body);
        if (body is List) {
          return body.cast<Map<String, dynamic>>();
        }
        if (body is Map && body['meetings'] is List) {
          return (body['meetings'] as List).cast<Map<String, dynamic>>();
        }
      }
    } catch (_) {}
    return [];
  }

  // ---------------------------------------------------------------------
  // Content screens: calendar / emails / tasks / briefing
  // ---------------------------------------------------------------------

  /// GET /api/calendar/week?start=&end= — meetings grouped by date.
  Future<Map<String, dynamic>> getCalendarWeek(
      String startDate, String endDate) async {
    try {
      final resp = await _client
          .get(_uri('/api/calendar/week?start=$startDate&end=$endDate'),
              headers: _headers)
          .timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {'days': {}};
  }

  /// GET /api/briefing/context?days_ahead= — calendar slice, tasks, gmail.
  Future<Map<String, dynamic>> getBriefingContext({int daysAhead = 1}) async {
    try {
      final resp = await _client
          .get(_uri('/api/briefing/context?days_ahead=$daysAhead'),
              headers: _headers)
          .timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {};
  }

  /// GET /api/commitments?limit=&status= — task commitments.
  Future<List<Map<String, dynamic>>> getCommitments(
      {int limit = 100, String status = ''}) async {
    try {
      final q = status.isEmpty ? '?limit=$limit' : '?limit=$limit&status=$status';
      final resp = await _client
          .get(_uri('/api/commitments$q'), headers: _headers)
          .timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        final body = jsonDecode(resp.body);
        if (body is List) return body.cast<Map<String, dynamic>>();
        if (body is Map && body['commitments'] is List) {
          return (body['commitments'] as List).cast<Map<String, dynamic>>();
        }
        if (body is Map && body['items'] is List) {
          return (body['items'] as List).cast<Map<String, dynamic>>();
        }
      }
    } catch (_) {}
    return [];
  }

  /// PATCH /api/commitments/{id} — change status and/or due date.
  Future<bool> patchCommitment(String id,
      {String? status, String? dueDate}) async {
    try {
      final resp = await _client
          .patch(
            _uri('/api/commitments/$id'),
            headers: _headers,
            body: jsonEncode({
              if (status != null) 'status': status,
              if (dueDate != null) 'due_date': dueDate,
            }),
          )
          .timeout(const Duration(seconds: 12));
      return resp.statusCode >= 200 && resp.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  /// POST /api/commitments — create a manual task.
  Future<bool> createCommitment(
      {required String title, String? dueDate, String? description}) async {
    try {
      final resp = await _client
          .post(
            _uri('/api/commitments'),
            headers: _headers,
            body: jsonEncode({
              'title': title,
              if (dueDate != null) 'due_date': dueDate,
              if (description != null) 'description': description,
            }),
          )
          .timeout(const Duration(seconds: 12));
      return resp.statusCode >= 200 && resp.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  /// GET /api/emails?filter=&limit= — Gmail rows.
  Future<List<Map<String, dynamic>>> getEmails(
      {String filter = 'all', int limit = 50}) async {
    try {
      final resp = await _client
          .get(_uri('/api/emails?filter=$filter&limit=$limit'), headers: _headers)
          .timeout(const Duration(seconds: 20));
      if (resp.statusCode == 200) {
        final body = jsonDecode(resp.body);
        if (body is List) return body.cast<Map<String, dynamic>>();
        if (body is Map && body['messages'] is List) {
          return (body['messages'] as List).cast<Map<String, dynamic>>();
        }
        if (body is Map && body['emails'] is List) {
          return (body['emails'] as List).cast<Map<String, dynamic>>();
        }
      }
    } catch (_) {}
    return [];
  }

  /// GET /api/emails/{id} — full email body.
  Future<Map<String, dynamic>> getEmailDetail(String id) async {
    for (final path in [
      '/api/emails/$id',
      '/api/integrations/gmail/messages/$id',
    ]) {
      try {
        final resp = await _client
            .get(_uri(path), headers: _headers)
            .timeout(const Duration(seconds: 15));
        if (resp.statusCode == 200) {
          return jsonDecode(resp.body) as Map<String, dynamic>;
        }
      } catch (_) {}
    }
    return {};
  }

  Future<bool> markEmailRead(String id, {bool read = true}) async {
    final action = read ? 'mark-read' : 'mark-unread';
    for (final path in [
      '/api/emails/$id/$action',
      '/api/integrations/gmail/messages/$id/$action',
    ]) {
      try {
        final resp = await _client
            .post(_uri(path), headers: _headers)
            .timeout(const Duration(seconds: 10));
        if (resp.statusCode >= 200 && resp.statusCode < 300) return true;
      } catch (_) {}
    }
    return false;
  }

  Future<bool> archiveEmail(String id) async {
    for (final path in [
      '/api/emails/$id/archive',
      '/api/integrations/gmail/messages/$id/archive',
    ]) {
      try {
        final resp = await _client
            .post(_uri(path), headers: _headers)
            .timeout(const Duration(seconds: 10));
        if (resp.statusCode >= 200 && resp.statusCode < 300) return true;
      } catch (_) {}
    }
    return false;
  }

  void dispose() => _client.close();
}

/// Raised when an API call returns a non-2xx response.
class ApiException implements Exception {
  ApiException(this.message, this.statusCode);
  final String message;
  final int statusCode;
  @override
  String toString() => message;
}
