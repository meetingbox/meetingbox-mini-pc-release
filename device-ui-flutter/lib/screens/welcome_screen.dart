import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:meetingbox_device_ui/core/theme/app_colors.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  static const _canvas = Size(1260, 800);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.welcomeBg,
      body: Center(
        child: FittedBox(
          fit: BoxFit.contain,
          child: SizedBox.fromSize(
            size: _canvas,
            child: Stack(
              children: [
                const ColoredBox(color: AppColors.welcomeBg),
                _asset(
                  'assets/welcome/Ellipse 1.png',
                  left: -90,
                  top: -80,
                  width: 1440,
                  height: 680,
                  opacity: 0.30,
                  fit: BoxFit.fill,
                ),
                _asset(
                  'assets/welcome/Ellipse 2.png',
                  left: -140,
                  top: 170,
                  width: 760,
                  height: 580,
                  opacity: 0.18,
                  fit: BoxFit.fill,
                ),
                _asset(
                  'assets/welcome/Ellipse 3.png',
                  left: 660,
                  top: 170,
                  width: 760,
                  height: 580,
                  opacity: 0.18,
                  fit: BoxFit.fill,
                ),
                Positioned(
                  left: 20,
                  top: 16,
                  width: 240,
                  height: 52,
                  child: Row(
                    children: [
                      Image.asset(
                        'assets/welcome/LOGO.png',
                        width: 26,
                        height: 26,
                        errorBuilder: (_, __, ___) => const Icon(
                          Icons.mic_rounded,
                          color: AppColors.blue,
                          size: 26,
                        ),
                      ),
                      const SizedBox(width: 9),
                      const Text(
                        'MeetingBox',
                        style: TextStyle(
                          color: AppColors.white,
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                Positioned(
                  left: 0,
                  top: 268,
                  width: _canvas.width,
                  height: 264,
                  child: Column(
                    children: [
                      const SizedBox(
                        height: 78,
                        child: Center(
                          child: Text(
                            'MeetingBox AI',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: AppColors.white,
                              fontSize: 64,
                              fontWeight: FontWeight.w800,
                              height: 1,
                              letterSpacing: -1.5,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      const SizedBox(
                        height: 28,
                        child: Center(
                          child: Text(
                            'Your meeting room that remembers everything.',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Color(0xFFA4A4AC),
                              fontSize: 18,
                              height: 1.2,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 32),
                      GestureDetector(
                        onTap: () => context.push('/room-name'),
                        child: Image.asset(
                          'assets/welcome/Button.png',
                          height: 70,
                          fit: BoxFit.contain,
                          errorBuilder: (_, __, ___) => Container(
                            width: 307,
                            height: 70,
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(35),
                              gradient: const LinearGradient(
                                colors: [AppColors.blueBright, AppColors.blueDeep],
                              ),
                            ),
                            child: const Text(
                              'Continue',
                              style: TextStyle(
                                color: AppColors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Image.asset(
                            'assets/welcome/shield.png',
                            width: 16,
                            height: 16,
                            color: const Color(0xFF8A8A92),
                            errorBuilder: (_, __, ___) => const Icon(
                              Icons.shield_outlined,
                              color: Color(0xFF8A8A92),
                              size: 16,
                            ),
                          ),
                          const SizedBox(width: 6),
                          const Text(
                            'Enterprise-grade security included',
                            style: TextStyle(
                              color: Color(0xFF8A8A92),
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  static Widget _asset(
    String path, {
    required double left,
    required double top,
    required double width,
    required double height,
    double opacity = 1,
    BoxFit fit = BoxFit.contain,
  }) {
    return Positioned(
      left: left,
      top: top,
      width: width,
      height: height,
      child: Opacity(
        opacity: opacity,
        child: Image.asset(
          path,
          fit: fit,
          errorBuilder: (_, __, ___) => const SizedBox.shrink(),
        ),
      ),
    );
  }
}
