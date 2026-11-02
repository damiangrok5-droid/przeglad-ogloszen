# przeglad-ogloszen

Statyczna strona z przeglądem publicznych ogłoszeń (kategorie, podmioty, terminy). Treść i dane są szyfrowane (AES-256-GCM, klucz PBKDF2-SHA256, 600 000 iteracji); jawna jest tylko strona z polem hasła. Strona nie jest indeksowana (`noindex`, `robots.txt: Disallow: /`).

Jawne w repo są tylko narzędzia ogólne; pliki robocze z treścią merytoryczną (reguły oceny, słowniki, eksport, interfejs po odszyfrowaniu, testy danych) są w zaszyfrowanym pakiecie `pakiet/pakiet.enc`.

- `narzedzia/pakiet.py` – `otworz` / `zamknij` / `sprawdz` zaszyfrowany pakiet plików roboczych (rozpakowane pliki są w `.gitignore`)
- `narzedzia/zrodla.py` – klienci źródeł z limitami zapytań i obsługą robots.txt
- `narzedzia/szyfruj.mjs`, `narzedzia/stan.mjs`, `narzedzia/sprawdz_build.mjs` – szyfrowanie i weryfikacja strony oraz stanu (hasło z `SITE_PASSWORD`, min. 12 znaków)
- `testy/testy.py` – bramki przed publikacją (w tym skan neutralności wszystkich jawnych plików i historii)
- `testy/test_przegladarka.py` – test zaszyfrowanego buildu w przeglądarce
- `docs/` – zbudowana, zaszyfrowana strona (źródło Pages z gałęzi `main` do czasu przełączenia na GitHub Actions)
- `.github/workflows/publikacja.yml` – aktualizacja i publikacja (ręcznie oraz w poniedziałki i czwartki); publikacja tylko po przejściu testów

Wymagany sekret: `SITE_PASSWORD`.

Praca lokalna: `python3 narzedzia/pakiet.py otworz`, zmiany w plikach roboczych, `python3 narzedzia/pakiet.py zamknij`, commit `pakiet/pakiet.enc`.

Harmonogram: cron w GitHub Actions działa w UTC. `0 5 * * 1,4` = 06:00 czasu polskiego zimą (UTC+1). Od ostatniej niedzieli marca (UTC+2) zmień na `0 4 * * 1,4`, a od ostatniej niedzieli października z powrotem na `0 5 * * 1,4`.

Po dodaniu workflow przełącz źródło Pages z gałęzi (`docs/`) na „GitHub Actions”.
