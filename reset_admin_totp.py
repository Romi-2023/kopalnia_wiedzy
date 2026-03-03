#!/usr/bin/env python3
"""
Generuje nowy sekret TOTP do panelu administratora.
Użycie: uruchom lokalnie, skopiuj sekret, ustaw go jako zmienną ADMIN_TOTP_SECRET
na serwerze (DigitalOcean → Environment variables) i dodaj wpis w Authenticatorze
(ręcznie: wpisz sekret lub zeskanuj wyświetlony QR).
Dostęp do panelu ma tylko osoba znająca ten sekret (Ty).
"""
from __future__ import annotations

import sys

try:
    import pyotp
    import qrcode
except ImportError as e:
    print("Zainstaluj: pip install pyotp qrcode[pil]")
    sys.exit(1)

secret = pyotp.random_base32()
totp = pyotp.TOTP(secret)
uri = totp.provisioning_uri(name="KopalniaWiedzy-Nadzor", issuer_name="Kopalnia Wiedzy")

print("=" * 60)
print("NOWY SEKRET TOTP – zachowaj go tylko dla siebie")
print("=" * 60)
print()
print("Sekret (ustaw jako ADMIN_TOTP_SECRET na serwerze):")
print(secret)
print()
print("1. W DigitalOcean → Twoja aplikacja → Settings → App-level environment variables")
print("   Dodaj: ADMIN_TOTP_SECRET =", secret)
print()
print("2. W aplikacji Authenticator (Google / Microsoft itp.):")
print("   Dodaj wpis ręcznie, wpisz powyższy sekret (lub zeskanuj QR z pliku).")
print()
print("3. Po zapisaniu zmiennej zrób Redeploy aplikacji.")
print("=" * 60)

# Zapis QR do pliku (opcjonalnie – do zeskanowania w Authenticatorze)
try:
    img = qrcode.make(uri)
    qr_path = "admin_totp_qr.png"
    img.save(qr_path)
    print(f"\nQR do skanowania zapisany w: {qr_path}")
    print("(możesz usunąć plik po dodaniu wpisu w Authenticatorze)")
except Exception as e:
    print("\n(QR nie zapisany:", e, ")")
