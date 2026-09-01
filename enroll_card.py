"""Yetkili RFID karti kaydetme araci.

Kullanim:  venv/bin/python enroll_card.py "Kart Sahibi Adi"
Kart okuyucuya kart yaklastirilinca UID veritabanina eklenir.
"""
import sys

import database

if len(sys.argv) < 2:
    print('Kullanim: python enroll_card.py "Kart Sahibi Adi"')
    sys.exit(1)

name = sys.argv[1]
database.init_db()

from mfrc522 import SimpleMFRC522
reader = SimpleMFRC522()

print(f"'{name}' icin kart bekleniyor... (karti okuyucuya yaklastir)")
uid, _ = reader.read()
database.add_card(uid, name)
print(f"Kayit tamam: {name} -> UID {uid}")
print("Kayitli kartlar:")
for c in database.list_cards():
    print(f"  {c['uid']}  {c['name']}  ({c['added_at']})")
