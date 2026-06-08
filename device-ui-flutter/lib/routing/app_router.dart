import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/config/app_config.dart';
import 'package:meetingbox_device_ui/screens/home_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/all_set_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/meetingbox_ready_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/network_choice_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/pair_device_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/room_name_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/setup_progress_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/wifi_connected_screen.dart';
import 'package:meetingbox_device_ui/screens/onboarding/wifi_setup_screen.dart';
import 'package:meetingbox_device_ui/screens/recording/complete_screen.dart';
import 'package:meetingbox_device_ui/screens/recording/meeting_detail_screen.dart';
import 'package:meetingbox_device_ui/screens/recording/meetings_screen.dart';
import 'package:meetingbox_device_ui/screens/recording/processing_screen.dart';
import 'package:meetingbox_device_ui/screens/recording/recording_screen.dart';
import 'package:meetingbox_device_ui/screens/content/calendar_screen.dart';
import 'package:meetingbox_device_ui/screens/content/emails_screen.dart';
import 'package:meetingbox_device_ui/screens/content/morning_brief_screen.dart';
import 'package:meetingbox_device_ui/screens/content/tasks_screen.dart';
import 'package:meetingbox_device_ui/screens/recording/summary_review_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/audio_device_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/bluetooth_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/info_setting_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/picker_setting_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/settings_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/slider_setting_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/text_edit_setting_screen.dart';
import 'package:meetingbox_device_ui/screens/settings/wifi_forget_screen.dart';
import 'package:meetingbox_device_ui/screens/splash_screen.dart';
import 'package:meetingbox_device_ui/screens/welcome_screen.dart';
import 'package:meetingbox_device_ui/services/api_client.dart';
import 'package:meetingbox_device_ui/services/device_bridge_client.dart';
import 'package:meetingbox_device_ui/services/onboarding_state.dart';
import 'package:meetingbox_device_ui/services/setup_state.dart';

GoRouter createAppRouter({
  required AppConfig config,
  required ApiClient api,
  required DeviceBridgeClient bridge,
  required SetupState setupState,
  required OnboardingState onboarding,
}) {
  CustomTransitionPage<void> fade(Widget child) => CustomTransitionPage(
        child: child,
        transitionsBuilder: (context, animation, secondary, child) =>
            FadeTransition(opacity: animation, child: child),
      );

  return GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => SplashScreen(
          config: config,
          api: api,
          setupState: setupState,
        ),
      ),
      GoRoute(
        path: '/welcome',
        pageBuilder: (context, state) => fade(const WelcomeScreen()),
      ),
      GoRoute(
        path: '/room-name',
        pageBuilder: (context, state) =>
            fade(RoomNameScreen(api: api, onboarding: onboarding)),
      ),
      GoRoute(
        path: '/network-choice',
        pageBuilder: (context, state) =>
            fade(NetworkChoiceScreen(api: api, onboarding: onboarding)),
      ),
      GoRoute(
        path: '/wifi-setup',
        pageBuilder: (context, state) => fade(
          WifiSetupScreen(config: config, bridge: bridge, onboarding: onboarding),
        ),
      ),
      GoRoute(
        path: '/wifi-connected',
        pageBuilder: (context, state) => fade(
          WifiConnectedScreen(config: config, api: api, onboarding: onboarding),
        ),
      ),
      GoRoute(
        path: '/pair-device',
        pageBuilder: (context, state) => fade(
          PairDeviceScreen(config: config, api: api, onboarding: onboarding),
        ),
      ),
      GoRoute(
        path: '/meetingbox-ready',
        pageBuilder: (context, state) => fade(
          MeetingBoxReadyScreen(
            config: config,
            api: api,
            onboarding: onboarding,
            setupState: setupState,
          ),
        ),
      ),
      GoRoute(
        path: '/setup-progress',
        pageBuilder: (context, state) => fade(const SetupProgressScreen()),
      ),
      GoRoute(
        path: '/all-set',
        pageBuilder: (context, state) => fade(AllSetScreen(config: config)),
      ),
      GoRoute(
        path: '/home',
        pageBuilder: (context, state) =>
            fade(HomeScreen(config: config, api: api, bridge: bridge)),
      ),
      GoRoute(
        path: '/recording',
        pageBuilder: (context, state) =>
            fade(RecordingScreen(config: config, api: api)),
      ),
      GoRoute(
        path: '/processing',
        pageBuilder: (context, state) => fade(
          ProcessingScreen(
            config: config,
            api: api,
            meetingId: state.extra as String?,
          ),
        ),
      ),
      GoRoute(
        path: '/complete',
        pageBuilder: (context, state) => fade(
          CompleteScreen(config: config, api: api, meetingId: state.extra as String?),
        ),
      ),
      GoRoute(
        path: '/meetings',
        pageBuilder: (context, state) =>
            fade(MeetingsScreen(config: config, api: api)),
      ),
      GoRoute(
        path: '/meeting-detail',
        pageBuilder: (context, state) => fade(
          MeetingDetailScreen(
            config: config,
            api: api,
            meetingId: state.extra as String?,
          ),
        ),
      ),
      GoRoute(
        path: '/summary-review',
        pageBuilder: (context, state) => fade(
          SummaryReviewScreen(
            config: config,
            api: api,
            meetingId: state.extra as String?,
          ),
        ),
      ),
      // --- Content --------------------------------------------------------
      GoRoute(
        path: '/calendar',
        pageBuilder: (context, state) =>
            fade(CalendarScreen(config: config, api: api)),
      ),
      GoRoute(
        path: '/emails',
        pageBuilder: (context, state) =>
            fade(EmailsScreen(config: config, api: api)),
      ),
      GoRoute(
        path: '/tasks',
        pageBuilder: (context, state) =>
            fade(TasksScreen(config: config, api: api)),
      ),
      GoRoute(
        path: '/morning-brief',
        pageBuilder: (context, state) =>
            fade(MorningBriefScreen(config: config, api: api)),
      ),
      // --- Settings -------------------------------------------------------
      GoRoute(
        path: '/settings',
        pageBuilder: (context, state) =>
            fade(SettingsScreen(config: config, api: api, bridge: bridge)),
      ),
      GoRoute(
        path: '/settings/device-name',
        pageBuilder: (context, state) => fade(
          TextEditSettingScreen(
            title: 'Device Name',
            label: 'Name shown on your network and dashboard',
            initial: onboarding.deviceName,
            onSave: (v) => api.setDeviceName(v),
          ),
        ),
      ),
      GoRoute(
        path: '/settings/room-label',
        pageBuilder: (context, state) => fade(
          const TextEditSettingScreen(
            title: 'Room / Location',
            label: 'Where is this MeetingBox located?',
          ),
        ),
      ),
      GoRoute(
        path: '/settings/wifi',
        pageBuilder: (context, state) => fade(
          WifiSetupScreen(config: config, bridge: bridge, onboarding: onboarding),
        ),
      ),
      GoRoute(
        path: '/settings/wifi-forget',
        pageBuilder: (context, state) => fade(WifiForgetScreen(bridge: bridge)),
      ),
      GoRoute(
        path: '/settings/bluetooth',
        pageBuilder: (context, state) => fade(BluetoothScreen(bridge: bridge)),
      ),
      GoRoute(
        path: '/settings/brightness',
        pageBuilder: (context, state) => fade(
          SliderSettingScreen(
            title: 'Brightness',
            label: 'Screen brightness',
            onLoad: bridge.getBrightness,
            onChanged: bridge.setBrightness,
          ),
        ),
      ),
      GoRoute(
        path: '/settings/speech-volume',
        pageBuilder: (context, state) => fade(
          SliderSettingScreen(
            title: 'Speech volume',
            label: 'Assistant speech volume',
            onLoad: bridge.getVolume,
            onChanged: (v) => bridge.setVolume(v, target: 'speech'),
          ),
        ),
      ),
      GoRoute(
        path: '/settings/notification-volume',
        pageBuilder: (context, state) => fade(
          SliderSettingScreen(
            title: 'Notification volume',
            label: 'Notification sounds volume',
            onChanged: (v) => bridge.setVolume(v, target: 'notification'),
          ),
        ),
      ),
      GoRoute(
        path: '/settings/mic-gain',
        pageBuilder: (context, state) => fade(
          SliderSettingScreen(
            title: 'Microphone gain',
            label: 'Input sensitivity',
            onChanged: (v) => bridge.setVolume(v, target: 'mic'),
          ),
        ),
      ),
      GoRoute(
        path: '/settings/audio-output',
        pageBuilder: (context, state) =>
            fade(AudioDeviceScreen(bridge: bridge, isInput: false)),
      ),
      GoRoute(
        path: '/settings/audio-input',
        pageBuilder: (context, state) =>
            fade(AudioDeviceScreen(bridge: bridge, isInput: true)),
      ),
      GoRoute(
        path: '/settings/usb',
        pageBuilder: (context, state) => fade(
          InfoSettingScreen(
            title: 'USB devices',
            loadLines: bridge.usbDevices,
            emptyText: 'No USB devices detected.',
          ),
        ),
      ),
      GoRoute(
        path: '/settings/timezone',
        pageBuilder: (context, state) => fade(
          const PickerSettingScreen(
            title: 'Timezone',
            options: [
              'UTC',
              'America/New_York',
              'America/Los_Angeles',
              'Europe/London',
              'Europe/Berlin',
              'Asia/Kolkata',
              'Asia/Singapore',
              'Australia/Sydney',
            ],
          ),
        ),
      ),
      GoRoute(
        path: '/settings/auto-delete',
        pageBuilder: (context, state) => fade(
          const PickerSettingScreen(
            title: 'Auto-delete old meetings',
            options: ['Never', 'After 30 days', 'After 90 days', 'After 1 year'],
            selected: 'Never',
          ),
        ),
      ),
      GoRoute(
        path: '/settings/update-channel',
        pageBuilder: (context, state) => fade(
          const PickerSettingScreen(
            title: 'Update channel',
            options: ['Stable', 'Beta'],
            selected: 'Stable',
          ),
        ),
      ),
      GoRoute(
        path: '/settings/idle-timeout',
        pageBuilder: (context, state) => fade(
          const PickerSettingScreen(
            title: 'Idle timeout',
            options: ['1 minute', '5 minutes', '10 minutes', '30 minutes', 'Never'],
            selected: '5 minutes',
          ),
        ),
      ),
      GoRoute(
        path: '/settings/about',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'About',
            rows: [
              (label: 'Product', value: 'MeetingBox'),
              (label: 'UI', value: 'Flutter'),
              (label: 'Version', value: '1.0.0'),
            ],
          ),
        ),
      ),
      // Sub-screens without dedicated hardware backends yet show their state.
      GoRoute(
        path: '/settings/storage-breakdown',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'Storage breakdown',
            rows: [
              (label: 'Recordings', value: '—'),
              (label: 'Transcripts', value: '—'),
              (label: 'Cache', value: '—'),
            ],
          ),
        ),
      ),
      GoRoute(
        path: '/settings/update-check',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'Check for Updates',
            rows: [(label: 'Status', value: 'Up to date')],
          ),
        ),
      ),
      GoRoute(
        path: '/settings/datetime',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'Date & Time',
            rows: [(label: 'Sync', value: 'Automatic (network time)')],
          ),
        ),
      ),
      GoRoute(
        path: '/settings/diagnostics',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'Diagnostic logs',
            emptyText: 'No recent log output.',
            loadLines: null,
          ),
        ),
      ),
      GoRoute(
        path: '/settings/connectivity',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'Connectivity check',
            rows: [(label: 'Backend', value: 'Reachable')],
          ),
        ),
      ),
      GoRoute(
        path: '/settings/feedback',
        pageBuilder: (context, state) => fade(
          const InfoSettingScreen(
            title: 'Send feedback',
            rows: [(label: 'Contact', value: 'support@meetingbox.local')],
          ),
        ),
      ),
    ],
  );
}
