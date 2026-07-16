-- MeetingBox Bluetooth roles for AM-W45 duplex voice.
-- A2DP source sends playback to a headset. HFP/HSP AG lets the appliance act
-- as the phone side and exposes simultaneous mSBC capture + playback.
bluez_monitor.properties = {
  ["bluez5.roles"] = "[ a2dp_source hfp_ag hsp_ag ]",
  ["bluez5.hfphsp-backend"] = "native",
  ["bluez5.enable-msbc"] = true,
  ["bluez5.enable-sbc-xq"] = true,
  ["bluez5.enable-hw-volume"] = true,
  ["bluez5.autoswitch-profile"] = false,
}
