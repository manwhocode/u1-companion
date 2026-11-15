"""AI session capability issued through authenticated/trusted Moonraker mailbox."""
import hashlib
from pathlib import Path
import secrets
import socket
import time
from urllib.parse import urlsplit
from u1_ai.storage import ROOT, atomic


def local_hosts():
    result = {'localhost', '127.0.0.1', '::1', socket.gethostname(), socket.gethostname() + '.local'}
    import fcntl
    import struct
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for _, name in socket.if_nameindex():
            try:
                raw = fcntl.ioctl(sock.fileno(), 0x8915, struct.pack('256s', name.encode()[:15]))
                result.add(socket.inet_ntoa(raw[20:24]))
            except OSError:
                pass
    return result


def issue(payload, root=ROOT, hosts=None, clock=time.time):
    origin = payload.get('origin')
    if not isinstance(origin, str) or len(origin) > 260:
        raise ValueError('Неизвестный адрес интерфейса.')
    parsed = urlsplit(origin)
    if (parsed.scheme not in ('http', 'https') or parsed.hostname not in (local_hosts() if hosts is None else hosts)
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or parsed.port not in (None, 80, 443)):
        raise ValueError('Для AI откройте основной локальный HTTP/HTTPS-адрес принтера.')
    token = secrets.token_hex(32)
    expiry = clock() + 900
    folder = Path(root) / 'sessions'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    for old in folder.glob('*.json'):
        if old.stat().st_mtime < clock() - 1800:
            old.unlink()
    if len(list(folder.glob('*.json'))) >= 100:
        raise ValueError('Слишком много сессий AI. Повторите позже.')
    atomic(folder / (hashlib.sha256(token.encode()).hexdigest() + '.json'), {'origin': origin, 'expires': expiry})
    return {'session': token, 'expires': expiry}
