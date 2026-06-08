import 'dart:io';

Future<String> readTokenFile(String path) async {
  try {
    final file = File(path);
    if (!await file.exists()) return '';
    return (await file.readAsString()).replaceAll('\r', '').trim();
  } catch (_) {
    return '';
  }
}

Future<bool> writeTokenFile(String path, String token) async {
  try {
    final file = File(path);
    await file.parent.create(recursive: true);
    await file.writeAsString('$token\n');
    return true;
  } catch (_) {
    return false;
  }
}
