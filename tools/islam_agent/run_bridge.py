#!/usr/bin/env python3
"""Create a private-LAN TLS certificate and start the ISLAM phone bridge."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
from pathlib import Path

from bridge_server import BridgeApplication, create_server
from work_schedule import ScheduledWorker


ROOT = Path(__file__).resolve().parents[2]
TLS_DIR = Path.home() / ".islam-free-agent" / "bridge-tls"


def discover_lan_ipv4() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        address = sock.getsockname()[0]
    finally:
        sock.close()
    parsed = ipaddress.ip_address(address)
    if parsed.version != 4 or not parsed.is_private or parsed.is_loopback:
        raise RuntimeError("تعذر اكتشاف عنوان IPv4 خاص بالشبكة المحلية")
    return address


def ensure_certificate(host: str, directory: Path = TLS_DIR) -> tuple[Path, Path]:
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("OpenSSL غير مثبت. ثبّت OpenSSL ثم أعد التشغيل.")
    directory.mkdir(parents=True, exist_ok=True)
    cert = directory / "server.crt"
    key = directory / "server.key"
    if cert.exists() and key.exists():
        valid_ip = subprocess.run(
            [openssl, "x509", "-in", str(cert), "-checkip", host, "-noout"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0
        valid_time = subprocess.run(
            [openssl, "x509", "-in", str(cert), "-checkend", "86400", "-noout"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0
        if valid_ip and valid_time:
            return cert, key
    subprocess.run([
        openssl, "req", "-x509", "-newkey", "rsa:3072", "-sha256",
        "-days", "30", "-nodes", "-keyout", str(key), "-out", str(cert),
        "-subj", "/CN=ISLAM-FREE-AGENT",
        "-addext", f"subjectAltName=IP:{host}",
        "-addext", "keyUsage=digitalSignature,keyEncipherment",
        "-addext", "extendedKeyUsage=serverAuth",
    ], check=True, stdout=subprocess.DEVNULL)
    try:
        key.chmod(0o600)
    except OSError:
        pass
    return cert, key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="private LAN IPv4; auto-detected if omitted")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", required=True, help="exact model name from ollama list")
    parser.add_argument("--interval-seconds", type=int, default=300, help="proposal scan interval inside work hours")
    parser.add_argument("--work-start", default="20:00", help="daily start time in Algeria (supports overnight windows)")
    parser.add_argument("--work-end", default="06:00", help="daily end time in Algeria (supports overnight windows)")
    parser.add_argument("--schedule-check-seconds", type=int, default=30)
    parser.add_argument("--no-continuous", action="store_true", help="disable scheduled automatic scanning")
    args = parser.parse_args()
    schedule = None
    try:
        host = args.host or discover_lan_ipv4()
        cert, key = ensure_certificate(host)
        pair_code = f"{secrets.randbelow(1_000_000):06d}"
        app = BridgeApplication(pair_code, args.model)
        app.work_window = {
            "start": args.work_start,
            "end": args.work_end,
            "timezone": "Africa/Algiers",
        }
        server = create_server(host, args.port, app, cert, key)
        if not args.no_continuous:
            schedule = ScheduledWorker(
                app.start_continuous_worker, app.stop_continuous_worker,
                interval_seconds=args.interval_seconds,
                start=args.work_start, end=args.work_end,
                check_seconds=args.schedule_check_seconds,
            )
            schedule.tick()
            schedule.start_schedule()
        der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))
        fingerprint = hashlib.sha256(der).hexdigest()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"تعذر تشغيل جسر إسلام: {exc}", file=sys.stderr)
        return 2

    print("\n=== جسر ISLAM FREE AGENT الآمن ===", flush=True)
    print(f"العنوان: https://{host}:{server.server_port}", flush=True)
    print(f"بصمة شهادة SHA-256: {fingerprint}", flush=True)
    print(f"رمز الاقتران لمرة واحدة (5 دقائق): {pair_code}", flush=True)
    print(f"النموذج المحلي: {args.model}", flush=True)
    print("يبقى Ollama على 127.0.0.1:11434 ولا تفتح منفذه للإنترنت.", flush=True)
    if not args.no_continuous:
        print(f"العمل التلقائي يومياً {args.work_start}-{args.work_end} بتوقيت الجزائر؛ المحاكاة المختبرية المسموحة تنفذ وتتحقق تلقائياً، أما تعديل الملفات فينتظر موافقتك.", flush=True)
    else:
        print("المتابعة الدورية معطلة؛ يمكن طلب الاقتراح يدوياً من الهاتف.", flush=True)
    print("أوقف الجسر بـ Ctrl+C. إعادة التشغيل تنهي جلسة الهاتف الحالية.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nتم إيقاف جسر إسلام.", flush=True)
    finally:
        if schedule:
            schedule.stop_schedule()
        app.stop_continuous_worker()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
