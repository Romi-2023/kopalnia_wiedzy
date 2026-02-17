# Plan uatrakcyjnienia Kopalni wiedzy (bez monetyzacji)

Produkt: powtórki + pierwszy kontakt z Data Science dla 9–14 lat, wygląd Minecraft.

---

## 1. Mapa kopalni (widoczny postęp)

**Cel:** Użytkownik widzi „kopalnię” – korytarze/działy odblokowują się po ukończonych misjach; „wykopane skarby” = zdobyte umiejętności.

**Do zrobienia:**
- Nowa strona lub sekcja: **Mapa kopalni** (np. w nawigacji / Skrzynce / osobnym linku).
- Wizualizacja: schemat kopalni (obrazek lub CSS) z „korytarzami” = przedmioty/działy (Matematyka, Polski, Data Science…).
- Stan każdego korytarza: zablokowany / odblokowany (na podstawie ukończonych misji z `data/tasks.json` + ewentualnie quizów).
- „Skarby” w korytarzu: np. ikonki/lista zdobytych umiejętności (odznaki, ukończone lekcje).
- Integracja z istniejącym stanem: `is_task_done`, `mark_task_done`, przedmioty z Misji.

**Kolejność:** Zrobić najpierw prostą wersję (lista przedmiotów + które odblokowane), potem dodać wizual „mapy”.

---

## 2. Wyzwanie dnia + szybki quiz

**Cel:** Krótkie wyzwania „na szybko” – powód do codziennego wejścia.

**Do zrobienia:**
- **Wyzwanie dnia:** 1 zadanie (2–3 min), losowane codziennie (np. z `pick_daily_chunk` / `_day_seed`). Widoczny przycisk/baner na Start lub w Misjach. Nagroda: XP/diament (bez zmiany logiki nagród – tylko użycie istniejącej).
- **Szybki quiz:** 3–5 pytań, jeden przycisk „Szybki quiz” (np. na Start lub Plac zabaw). Prosty licznik czasu (opcjonalnie) – np. „Ukończono w X sekund”.

**Kolejność:** Wyzwanie dnia może korzystać z istniejącej logiki „daily”; szybki quiz to skrót do istniejącego quizu z mniejszą liczbą pytań.

---

## 3. Supermoce Data Science (nazwy umiejętności)

**Cel:** Konkretne nazwy w stylu Minecraft: „Wykrywacz wzorców”, „Filtr prawdy”, „Kalkulator średniej”.

**Do zrobienia:**
- Zdefiniować 5–7 „supermoce” (np. w `data/` jako JSON lub w kodzie): nazwa, krótki opis, które misje/quizy je odblokowują.
- W UI: gdzieś (Słowniczek, Mapa, profil) pokazać listę supermocy – odblokowane vs zablokowane.
- Każda supermoce = powiązanie z istniejącą misją lub minilekcją (np. jeden wpis w słowniczku + jedno zadanie).

**Kolejność:** Po mapie lub równolegle – żeby na mapie można było pokazać „skarb” = supermoce.

---

## 4. Lekka rywalizacja (rankingi, drużyny, serie)

**Cel:** Zaangażowanie bez stresu – rankingi klasowe, odznaki za serie.

**Do zrobienia:**
- **Ranking klasowy:** Jeśli jest pojęcie „klasa” (np. w profilu / zaproszeniach) – suma XP klasy, prosta tabela. Jeśli nie ma klas – opcjonalnie „ranking znajomych” lub na razie pominąć.
- **Odznaki za serie:** np. „7 dni z rzędu” – sprawdzanie `claim_streak_lootbox` / ostatnie logowania; wyświetlenie odznaki w profilu / na mapie.
- **Drużyny:** (później) np. pół klasy vs pół klasy – wymaga modelu „klasa” i ewentualnie zaproszeń.

**Kolejność:** Najpierw odznaki za serie (najmniej zależności), potem ranking jeśli będzie model klasy.

---

## 5. Data storytelling (podsumowanie po misji/quizie)

**Cel:** 1–2 zdania „Z twoich odpowiedzi wyszło, że…” + prosty wykres „twoje wyniki w czasie”.

**Do zrobienia:**
- Po zakończeniu misji/quizu: krótki blok tekstowy (szablon) np. „Ukończyłeś X z Y zadań. Twoja ulubiona kategoria to…” (jeśli mamy dane).
- Opcjonalnie: prosty wykres (Streamlit) – np. „Twoje wyniki w ostatnich 7 dniach” z zapisanego stanu (`st.session_state` lub backend).
- Zbieranie minimalnych danych: np. które pytania rozwiązane, czas – żeby dało się coś wyświetlić.

**Kolejność:** Na końcu – wymaga trochę logiki zbierania historii; można zacząć od prostego tekstu bez wykresu.

---

## Proponowana kolejność wdrożenia

| Krok | Element                    | Zależności                          |
|------|----------------------------|-------------------------------------|
| 1    | Mapa kopalni (prosta)      | Misje, `is_task_done`, przedmioty   |
| 2    | Wyzwanie dnia              | Daily seed, istniejące zadania      |
| 3    | Szybki quiz                | Quiz danych, limit pytań           |
| 4    | Supermoce Data Science     | Lista + powiązanie z misjami       |
| 5    | Mapa – wizual „korytarze”  | Po punkcie 1 i 4                    |
| 6    | Odznaki za serie           | Streak / ostatnie logowania         |
| 7    | Data storytelling (tekst)  | Po misji/quizie                     |
| 8    | Ranking (jeśli będzie klasa) | Model klasy / grupy              |

Monetyzacja (płatne wersje, szkoły, rodzice) – na później, osobny plan.
