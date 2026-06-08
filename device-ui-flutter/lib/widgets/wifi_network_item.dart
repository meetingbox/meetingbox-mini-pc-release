import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';

/// WiFi network row, ported from `components/wifi_network_item.py`.
class WiFiNetworkItem extends StatefulWidget {
  const WiFiNetworkItem({
    super.key,
    required this.ssid,
    this.signalStrength = 0,
    this.connected = false,
    this.onPressed,
  });

  final String ssid;
  final int signalStrength;
  final bool connected;
  final VoidCallback? onPressed;

  @override
  State<WiFiNetworkItem> createState() => _WiFiNetworkItemState();
}

class _WiFiNetworkItemState extends State<WiFiNetworkItem> {
  bool _pressed = false;

  Color get _sigColor {
    if (widget.connected) return AppColors.green;
    if (widget.signalStrength >= 25) return AppColors.yellow;
    return AppColors.gray500;
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.onPressed,
      child: Container(
        height: 48,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: _pressed && !widget.connected
              ? AppColors.surfaceLight
              : AppColors.surface,
          borderRadius: BorderRadius.circular(Layout.borderRadius),
        ),
        child: Row(
          children: [
            Expanded(
              flex: 65,
              child: Text(
                widget.ssid,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: AppColors.white,
                  fontSize: FontSizes.medium,
                  fontWeight:
                      widget.connected ? FontWeight.w700 : FontWeight.w400,
                ),
              ),
            ),
            Expanded(
              flex: 22,
              child: Text(
                '${widget.signalStrength}%',
                textAlign: TextAlign.right,
                style: TextStyle(color: _sigColor, fontSize: FontSizes.small),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
