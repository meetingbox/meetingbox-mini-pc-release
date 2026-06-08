import 'package:flutter/material.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';
import 'package:meetingbox_device_ui/core/theme/design_tokens.dart';
import 'package:meetingbox_device_ui/widgets/app_buttons.dart';

/// Modal dialog ported from `components/modal_dialog.py`.
///
/// Use [showModalDialog] to present it over a dimmed barrier.
class ModalDialogContent extends StatelessWidget {
  const ModalDialogContent({
    super.key,
    this.title = '',
    this.message = '',
    this.confirmText = 'OK',
    this.cancelText = 'CANCEL',
    this.danger = false,
    this.onConfirm,
    this.onCancel,
    this.borderColor,
  });

  final String title;
  final String message;
  final String confirmText;
  final String cancelText;
  final bool danger;
  final VoidCallback? onConfirm;
  final VoidCallback? onCancel;
  final Color? borderColor;

  @override
  Widget build(BuildContext context) {
    final hasCancel = cancelText.isNotEmpty;
    return Center(
      child: Container(
        width: 360,
        constraints: const BoxConstraints(minHeight: 220),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(Layout.borderRadius),
          border: borderColor != null
              ? Border.all(color: borderColor!, width: 2)
              : null,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                color: danger ? AppColors.red : AppColors.white,
                fontSize: FontSizes.title,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            const Divider(color: AppColors.gray700, height: 1),
            const SizedBox(height: 12),
            Flexible(
              child: Text(
                message,
                style: const TextStyle(
                  color: AppColors.gray500,
                  fontSize: FontSizes.small + 2,
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                if (hasCancel) ...[
                  Expanded(
                    child: AppButton.secondary(
                      label: cancelText,
                      height: 50,
                      onPressed: () {
                        Navigator.of(context).maybePop();
                        onCancel?.call();
                      },
                    ),
                  ),
                  const SizedBox(width: Spacing.buttonSpacing),
                ],
                Expanded(
                  child: AppButton(
                    label: confirmText,
                    variant: danger
                        ? AppButtonVariant.danger
                        : AppButtonVariant.primary,
                    height: 50,
                    onPressed: () {
                      Navigator.of(context).maybePop();
                      onConfirm?.call();
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

Future<void> showModalDialog(
  BuildContext context, {
  String title = '',
  String message = '',
  String confirmText = 'OK',
  String cancelText = 'CANCEL',
  bool danger = false,
  VoidCallback? onConfirm,
  VoidCallback? onCancel,
  Color? borderColor,
}) {
  return showDialog(
    context: context,
    barrierColor: danger ? AppColors.overlayRed : AppColors.overlay,
    builder: (_) => ModalDialogContent(
      title: title,
      message: message,
      confirmText: confirmText,
      cancelText: cancelText,
      danger: danger,
      onConfirm: onConfirm,
      onCancel: onCancel,
      borderColor: borderColor,
    ),
  );
}
