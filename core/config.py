# core/config.py
from __future__ import annotations
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

XP_SCHOOL_TASK = 2
XP_MISSION_TASK = 2
XP_SECTION_BONUS = 12
GEMS_SECTION_BONUS = 1

TERMS_VERSION = "2025-12-15"

# Dedykowany adres kontaktowy dla Kopalnia Wiedzy
CONTACT_EMAIL = "kopalnia.wiedzy@proton.me"

# Presety zestawów danych dla quizów (z app.py)
DATASETS_PRESETS = {'7-9': {'Łatwy (mały)': ['wiek', 'ulubiony_owoc', 'miasto'], 'Łatwy+ (z kolorem)': ['wiek', 'ulubiony_owoc', 'ulubiony_kolor', 'miasto']}, '10-12': {'Średni': ['wiek', 'wzrost_cm', 'ulubiony_owoc', 'miasto'], 'Średni+': ['wiek', 'wzrost_cm', 'ulubiony_owoc', 'ulubione_zwierze', 'miasto']}, '13-14': {'Zaawansowany': ['wiek', 'wzrost_cm', 'wynik_matematyka', 'wynik_plastyka', 'miasto', 'ulubiony_owoc'], 'Zaawansowany+': ['wiek', 'wzrost_cm', 'wynik_matematyka', 'wynik_plastyka', 'miasto', 'ulubiony_owoc', 'ulubione_zwierze']}}
