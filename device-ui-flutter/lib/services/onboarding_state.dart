import 'package:flutter/foundation.dart';

/// Holds onboarding selections that the Kivy app stored directly on the `App`
/// instance (`device_name`, `connected_wifi_ssid`, `paired_owner_email`,
/// `setup_language`, `setup_network_is_ethernet`).
class OnboardingState extends ChangeNotifier {
  String deviceName = 'MeetingBox';
  String connectedWifiSsid = '';
  String pairedOwnerEmail = '';
  String setupLanguage = 'English (US)';
  bool setupNetworkIsEthernet = false;

  void setDeviceName(String name) {
    deviceName = name;
    notifyListeners();
  }

  void setWifi(String ssid, {bool ethernet = false}) {
    connectedWifiSsid = ssid;
    setupNetworkIsEthernet = ethernet;
    notifyListeners();
  }

  void setPairedOwner(String email) {
    pairedOwnerEmail = email;
    notifyListeners();
  }
}
