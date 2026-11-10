# PaliwoMapa – Home Assistant Custom Component

[![GitHub Release](https://img.shields.io/github/v/release/LukaszP2/ha-paliwomapa?style=flat-square)](https://github.com/LukaszP2/ha-paliwomapa/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)


[![Otwórz repozytorium w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukaszP2&repository=ha-paliwomapa&category=integration)
[![Dodaj integrację do Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=paliwomapa)

*(🇬🇧 English description below)*

---

## 🇵🇱 Opis

Integracja z polskim serwisem PaliwoMapa.pl. Pozwala śledzić aktualne ceny paliw (PB95, PB98, ON, LPG) na ulubionych stacjach w Twojej okolicy.

### Główne funkcje
- Encje sensorów dla każdego typu paliwa (PB95, PB98, ON, ON premium, LPG) na wybranej stacji
- Automatyczne odświeżanie cen co 2 godziny oraz przycisk natychmiastowego odświeżenia na żądanie
- Encje najtańszych paliw w Twojej okolicy z bezpośrednimi linkami nawigacyjnymi
- Historia zmian cen i znacznik czasu ostatniej aktualizacji
- Informacja o marce stacji (Orlen, Shell, BP, Moya, Circle K itp.) i lokalizacji
- Wbudowana karta Lovelace (`custom:paliwomapa-card`) z wyszukiwarką i filtrami
- Pełne wsparcie dla reautoryzacji (zmiana hasła) i rekonfiguracji stacji w UI Home Assistant

### Instalacja przez HACS (Niestandardowe repozytorium)

### 🚀 Szybka instalacja (1 kliknięcie przez My Home Assistant)

[![Otwórz repozytorium w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukaszP2&repository=ha-paliwomapa&category=integration)

Po zainstalowaniu i ponownym uruchomieniu Home Assistant, kliknij poniższy przycisk, aby skonfigurować integrację:

[![Dodaj integrację do Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=paliwomapa)



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

### Karta Lovelace (`custom:paliwomapa-card`)

Karta jest serwowana bezpośrednio pod adresem `/paliwomapa/paliwomapa-card.js`.
Dla dashboardów zarządzanych przez UI (Storage mode) rejestracja zasobu następuje automatycznie.

W przypadku dashboardów w trybie **YAML** (`mode: yaml`), dodaj poniższy wpis do swojej konfiguracji Lovelace:
```yaml
lovelace:
  mode: yaml
  resources:
    - url: /paliwomapa/paliwomapa-card.js
      type: module
```

Przykład użycia karty w widoku dashboardu:
```yaml
type: custom:paliwomapa-card
title: Moje Stacje Paliw
fuel_types:
  - pb95
  - on
```

### Szablony automatyzacji (Blueprints)

Repozytorium zawiera gotowe szablony automatyzacji w katalogu `blueprints/automation/paliwomapa/`:
1. **Powiadomienie o niskiej cenie paliwa** (`fuel_price_drop_alert.yaml`): wysyła powiadomienie push z bezpośrednim przyciskiem nawigacji, gdy cena spadnie poniżej zadanego progu.
2. **Rekomendacja tankowania przy wyjeździe ze strefy** (`fuel_recommendation_on_departure.yaml`): sugeruje zjechanie na stację po opuszczeniu np. strefy pracy w godzinach powrotu, jeśli cena jest atrakcyjna.

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

### Lovelace Card (`custom:paliwomapa-card`)

The custom card is hosted at `/paliwomapa/paliwomapa-card.js`.
For UI-managed (storage mode) dashboards, the resource is registered automatically.

For **YAML-mode** dashboards, add the resource explicitly:
```yaml
lovelace:
  mode: yaml
  resources:
    - url: /paliwomapa/paliwomapa-card.js
      type: module
```

---

## Licencja / License

Projekt objęty licencją [MIT](LICENSE).