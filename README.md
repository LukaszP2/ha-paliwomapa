# PaliwoMapa – Home Assistant Custom Component

[![GitHub Release](https://img.shields.io/github/v/release/LukaszP2/ha-paliwomapa?style=flat-square)](https://github.com/LukaszP2/ha-paliwomapa/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)

*(🇬🇧 English description below)*

---

## 🇵🇱 Opis

Integracja z polskim serwisem PaliwoMapa.pl. Pozwala śledzić aktualne ceny paliw (PB95, PB98, ON, LPG) na ulubionych stacjach w Twojej okolicy.

### Główne funkcje
- Encje sensorów dla każdego typu paliwa na wybranej stacji
- Historia zmian cen i znacznik czasu ostatniej aktualizacji
- Informacja o marce stacji (Orlen, Shell, BP, Moya, Circle K itp.) i lokalizacji
- Gotowe do integracji z dashboardami Lovelace

### Instalacja przez HACS (Niestandardowe repozytorium)

1. Upewnij się, że masz zainstalowany **HACS** w Home Assistant.
2. W HACS przejdź do: **Integracje** -> menu w prawym górnym rogu (trzy kropki) -> **Niestandardowe repozytoria** (*Custom repositories*).
3. W polu **Repozytorium** wklej adres:
   ```text
   https://github.com/LukaszP2/ha-paliwomapa
   ```
4. W polu **Kategoria** wybierz: **Integracja** (*Integration*).
5. Kliknij **Dodaj**, a następnie wyszukaj **PaliwoMapa** i kliknij **Pobierz**.
6. Uruchom ponownie Home Assistant.

### Konfiguracja

1. W Home Assistant przejdź do: **Ustawienia** -> **Urządzenia oraz usługi** -> **Dodaj integrację**.
2. Wyszukaj **PaliwoMapa**.
3. Postępuj zgodnie z instrukcjami na ekranie.

---

## 🇬🇧 Description

Home Assistant integration with PaliwoMapa.pl tracking live fuel prices (PB95, PB98, Diesel, LPG) at local petrol stations in Poland.

### Installation via HACS (Custom Repository)

1. Open **HACS** in Home Assistant.
2. Navigate to **Integrations** -> top right menu (three dots) -> **Custom repositories**.
3. Enter repository URL:
   ```text
   https://github.com/LukaszP2/ha-paliwomapa
   ```
4. Category: **Integration**.
5. Click **Add**, find **PaliwoMapa**, and install.
6. Restart Home Assistant.

---

## Licencja / License

Projekt objęty licencją [MIT](LICENSE).
