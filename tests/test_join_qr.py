import importlib.util
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('join_qr', Path(__file__).resolve().parents[1] / 'join-qr.py')
qr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qr)

class WifiQrTests(unittest.TestCase):
    def test_escaped_credentials(self):
        parsed = qr.parse_wifi(r'WIFI:T:WPA;S:Home\;Guest\:5G;P:two\\slashes\;\:end;;')
        self.assertEqual(parsed['ssid'], 'Home;Guest:5G')
        self.assertEqual(parsed['password'], 'two\\slashes;:end')

    def test_preserve_spaces(self):
        self.assertEqual(qr.parse_wifi('WIFI:T:WPA;S: My Wifi ;P: password ;;')['password'], ' password ')

    def test_hidden_open_network(self):
        data = qr.parse_wifi('WIFI:T:nopass;S:Hidden;H:true;;')
        self.assertTrue(data['hidden'])
        self.assertEqual(data['security'], 'NOPASS')

    def test_invalid_payloads(self):
        for raw in ['https://example.com', 'WIFI:T:WPA;S:X;;', 'WIFI:T:WPA2-EAP;S:X;P:password;;',
                    'WIFI:S:One;S:Two;;', 'WIFI:S:unfinished', 'WIFI:S:' + 'x' * 33 + ';;']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                qr.parse_wifi(raw)

    def test_multiple_codes_are_rejected(self):
        raw = b'<barcodes><data>WIFI:S:A;;</data><data>WIFI:S:B;;</data></barcodes>'
        with self.assertRaises(ValueError):
            qr.decode_xml(raw)

    def test_real_qr_image_round_trip(self):
        payload = r'WIFI:T:WPA;S:Caf\;e WiFi;P:long\\password\;x;;'
        with tempfile.TemporaryDirectory() as directory:
            image = str(Path(directory) / 'test.png')
            subprocess.run(['qrencode', '-o', image], input=payload.encode(), check=True)
            result = subprocess.run(['zbarimg', '--quiet', '--nodbus', '--xml', '-Sdisable',
                                     '-Sqrcode.enable', image], capture_output=True, check=True)
        self.assertEqual(qr.decode_xml(result.stdout), qr.parse_wifi(payload))

    def test_libnm_profiles_validate(self):
        import gi
        gi.require_version('NM', '1.0')
        from gi.repository import NM, GLib
        for kind, password in [('WPA', 'testpassword'), ('SAE', 'testpassword'), ('WEP', 'abcde'), ('nopass', '')]:
            with self.subTest(kind=kind):
                data = qr.parse_wifi(f'WIFI:T:{kind};S:Test;P:{password};H:true;;')
                connection = qr.make_connection(data, NM, GLib)
                self.assertTrue(connection.verify())
                self.assertEqual(bytes(connection.get_setting_wireless().get_ssid().get_data()), b'Test')
                self.assertTrue(connection.get_setting_wireless().get_hidden())

    def run_frame_worker(self, payload, followups):
        import json
        with tempfile.TemporaryDirectory() as directory:
            worker = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve().parents[1] / 'join-qr.py')],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, env={**os.environ, 'XDG_RUNTIME_DIR': directory})
            try:
                ready = json.loads(worker.stdout.readline())
                frame = Path(ready['directory']) / 'frame.png'
                subprocess.run(['qrencode', '-o', str(frame)], input=payload.encode(), check=True)
                requests = [dict(action='decode'), *followups, dict(action='quit')]
                output, errors = worker.communicate(''.join(json.dumps(c) + '\n' for c in requests), timeout=10)
                self.assertEqual(worker.returncode, 0)
                self.assertNotIn('fictionalpassword', output + errors)
                self.assertFalse(Path(ready['directory']).exists())
                return [json.loads(line) for line in output.splitlines()]
            finally:
                if worker.poll() is None:
                    worker.kill()
                    worker.communicate()

    def test_worker_keeps_password_private_and_reset_clears_candidate(self):
        events = self.run_frame_worker('WIFI:T:WPA;S:Test;P:fictionalpassword;;',
                                       [dict(action='reset'), dict(action='connect')])
        self.assertEqual([e['type'] for e in events], ['found', 'reset', 'error'])
        self.assertEqual(events[0]['ssid'], 'Test')

    def test_camera_nonwifi_frame_does_not_stop_scan(self):
        events = self.run_frame_worker('https://example.com', [])
        self.assertEqual(events[0]['type'], 'invalid')
        self.assertIn('not a Wi-Fi code', events[0]['message'])

if __name__ == '__main__':
    unittest.main()
