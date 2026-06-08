import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';

/// Single-line text input dialog, ported from `components/text_input_dialog.py`.
/// Resolves to the entered string on Save, or null on cancel/tap-out.
Future<String?> showTextInputDialog(
  BuildContext context, {
  String title = '',
  String message = '',
  String initialValue = '',
  String placeholder = '',
  String confirmText = 'SAVE',
  String cancelText = 'CANCEL',
}) {
  final controller = TextEditingController(text: initialValue);
  return showDialog<String>(
    context: context,
    barrierColor: AppColors.overlay,
    builder: (ctx) => Center(
      child: Container(
        width: 440,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(Layout.borderRadius),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                color: AppColors.white,
                fontSize: FontSizes.large,
                fontWeight: FontWeight.w700,
              ),
            ),
            if (message.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                message,
                style: const TextStyle(
                  color: AppColors.gray400,
                  fontSize: FontSizes.small,
                ),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              style: const TextStyle(color: AppColors.white, fontSize: FontSizes.medium),
              onSubmitted: (v) => Navigator.of(ctx).pop(v),
              decoration: InputDecoration(
                hintText: placeholder,
                hintStyle: const TextStyle(color: AppColors.gray500),
                filled: true,
                fillColor: AppColors.surfaceLight,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: AppButton.secondary(
                    label: cancelText,
                    height: 48,
                    onPressed: () => Navigator.of(ctx).pop(),
                  ),
                ),
                const SizedBox(width: Spacing.buttonSpacing),
                Expanded(
                  child: AppButton.primary(
                    label: confirmText,
                    height: 48,
                    onPressed: () => Navigator.of(ctx).pop(controller.text),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
