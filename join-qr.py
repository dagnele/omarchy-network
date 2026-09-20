#!/usr/bin/env python3
"""Private JSON pipe backend for the Quickshell QR UI. No desktop dialogs."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

class Cancelled(Exception):
    pass

class InvalidWifiQr(ValueError):
    """A decoded QR symbol contains unusable Wi-Fi data."""
    pass

def parse_wifi(payload):
    if not payload.startswith('WIFI:'):
        raise ValueError('This QR code is not a Wi-Fi sharing code.')
    fields, part, escaped = {}, '', False
    for char in payload[5:]:
        if escaped:
            part += char
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == ';':
            if part:
                key, sep, value = part.partition(':')
                if not sep or key in fields:
                    raise ValueError('The Wi-Fi QR code contains invalid or repeated fields.')
                fields[key] = value
            part = ''
        else:
            part += char
    if escaped or part:
        raise ValueError('The Wi-Fi QR code is incomplete.')
    ssid = fields.get('S', '')
    password = fields.get('P', '')
    security = fields.get('T', 'nopass').upper()
    if not ssid or len(ssid.encode('utf-8')) > 32 or '\x00' in ssid:
        raise ValueError('The QR code contains an invalid network name.')
    if security not in ('WPA', 'WEP', 'NOPASS', 'SAE'):
        raise ValueError('This Wi-Fi security type is not supported. Join it manually instead.')
    if security != 'NOPASS' and not password:
        raise ValueError('The QR code does not contain the network password.')
    if '\x00' in password:
        raise ValueError('The QR code contains an invalid password.')
    return {'ssid': ssid, 'password': password, 'security': security,
            'hidden': fields.get('H', '').lower() == 'true'}


def decode_xml(raw):
    try:
        document = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError('No readable QR code was found. Try a larger, sharper image.') from None
    payloads = [element.text or '' for element in document.iter()
                if element.tag.rsplit('}', 1)[-1] == 'data']
    wifi = list(dict.fromkeys(value for value in payloads if value.startswith('WIFI:')))
    if len(wifi) > 1:
        raise ValueError('More than one Wi-Fi code was found. Show one code at a time.')
    if not wifi:
        raise ValueError('QR code detected, but it is not a Wi-Fi code. Open Wi-Fi sharing on your phone.')
    return parse_wifi(wifi[0])


def make_connection(data, NM, GLib):
    connection = NM.SimpleConnection.new()
    settings = NM.SettingConnection.new()
    settings.set_property('id', data['ssid'] + ' (QR)')
    settings.set_property('uuid', str(uuid.uuid4()))
    settings.set_property('type', '802-11-wireless')
    connection.add_setting(settings)
    wireless = NM.SettingWireless.new()
    wireless.set_property('ssid', GLib.Bytes.new(data['ssid'].encode('utf-8')))
    wireless.set_property('mode', 'infrastructure')
    wireless.set_property('hidden', data['hidden'])
    connection.add_setting(wireless)
    if data['security'] != 'NOPASS':
        security = NM.SettingWirelessSecurity.new()
        if data['security'] == 'WEP':
            security.set_property('key-mgmt', 'none')
            security.set_property('wep-key0', data['password'])
            security.set_property('wep-key-type', NM.WepKeyType.KEY)
        else:
            security.set_property('key-mgmt', 'sae' if data['security'] == 'SAE' else 'wpa-psk')
            security.set_property('psk', data['password'])
        connection.add_setting(security)
    for setting in (NM.SettingIP4Config.new(), NM.SettingIP6Config.new()):
        setting.set_property('method', 'auto')
        connection.add_setting(setting)
    connection.verify()
    return connection


def connect(data):
    import gi
    gi.require_version('NM', '1.0')
    from gi.repository import NM, GLib, Gio
    client = NM.Client.new(None)
    devices = [device for device in client.get_devices() if device.get_device_type() == NM.DeviceType.WIFI]
    if not devices:
        raise ValueError('No Wi-Fi adapter is available.')
    if not client.wireless_get_enabled():
        raise ValueError('Turn Wi-Fi on in the network menu, then try again.')
    device = devices[0]
    for candidate in devices:
        if any(ap.get_ssid() and bytes(ap.get_ssid().get_data()) == data['ssid'].encode('utf-8')
               for ap in candidate.get_access_points()):
            device = candidate
            break
    connection = make_connection(data, NM, GLib)
    loop, cancellable = GLib.MainLoop(), Gio.Cancellable()
    state = {'active': None, 'error': None, 'ok': False, 'cancelled': False}

    def finished(source, result, unused):
        try:
            state['active'] = source.add_and_activate_connection_finish(result)
        except GLib.Error:
            state['error'] = 'Could not start the connection. Check the QR code and your network permissions.'
            loop.quit()

    def poll():
        active = state['active']
        if active:
            status = active.get_state()
            if status == NM.ActiveConnectionState.ACTIVATED:
                state['ok'] = True
                loop.quit()
                return False
            if status == NM.ActiveConnectionState.DEACTIVATED:
                state['error'] = 'Could not join the network. Check that it is in range and that the shared password is current.'
                loop.quit()
                return False
        return True

    def timeout():
        state['error'] = 'Connecting timed out. Check that the network is in range and try again.'
        cancellable.cancel()
        if state['active']:
            client.deactivate_connection_async(state['active'], None, None, None)
        loop.quit()
        return False

    client.add_and_activate_connection_async(connection, device, None, cancellable, finished, None)
    poll_id = GLib.timeout_add(200, poll)
    timeout_id = GLib.timeout_add_seconds(50, timeout)
    try:
        loop.run()
    except Cancelled:
        state["cancelled"] = True
        cancellable.cancel()
    finally:
        for timer in (poll_id, timeout_id):
            if GLib.MainContext.default().find_source_by_id(timer):
                GLib.source_remove(timer)
    if not state['ok']:
        # Remove only the new profile created for this failed/cancelled attempt.
        subprocess.run(['nmcli', 'connection', 'delete', 'uuid', connection.get_uuid()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if state['cancelled']:
            raise Cancelled()
        raise ValueError(state['error'] or 'Could not join the network.')


def emit(event, **fields):
    print(json.dumps(dict(type=event, **fields)), flush=True)


def decode_frame(path):
    result = subprocess.run(['zbarimg', '--quiet', '--nodbus', '--xml', '-Sdisable',
                             '-Sqrcode.enable', str(path)], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=15)
    if result.returncode == 4:
        return None
    if result.returncode:
        raise ValueError('Could not read the camera frame. Please try again.')
    try:
        return decode_xml(result.stdout)
    except ValueError as error:
        raise InvalidWifiQr(str(error)) from None


def worker():
    candidate = None
    with tempfile.TemporaryDirectory(prefix='wifi-qr-', dir=os.environ.get('XDG_RUNTIME_DIR')) as directory:
        emit('ready', directory=directory)
        for line in sys.stdin:
            try:
                command = json.loads(line)
                action = command.get('action')
                if action == 'quit':
                    return
                if action == 'reset':
                    candidate = None
                    emit('reset')
                    continue
                if action == 'connect':
                    if candidate is None:
                        raise ValueError('Scan a Wi-Fi QR code first.')
                    connect(candidate)
                    candidate = None
                    emit('connected')
                    continue
                if action != 'decode':
                    raise ValueError('Unknown scanner action.')
                candidate = None
                path = Path(directory) / 'frame.png'
                try:
                    candidate = decode_frame(path)
                except InvalidWifiQr as error:
                    emit('invalid', message=str(error))
                    continue
                finally:
                    path.unlink(missing_ok=True)
                if candidate is None:
                    emit('miss')
                    continue
                # The password stays in this process; it is never sent to QML or logged.
                emit('found', ssid=candidate['ssid'], security=candidate['security'])
            except (Cancelled, KeyboardInterrupt):
                return
            except Exception as error:
                message = str(error) if isinstance(error, ValueError) else 'Could not complete this step. Please try again.'
                emit('error', message=message)


def main():
    def stop(signum, frame):
        raise Cancelled()
    signal.signal(signal.SIGTERM, stop)
    try:
        worker()
    except (Cancelled, KeyboardInterrupt, BrokenPipeError):
        pass

if __name__ == '__main__':
    main()
