# Schemat bazy danych dla faktur prądu

## Analiza i propozycja struktury

### Uwagi ogólne

1. **Okres (rok)**: Wszystkie tabele powinny mieć pole `rok` (INTEGER) zamiast tylko `data`, aby ułatwić grupowanie i filtrowanie po latach.
2. **Normalizacja**: Niektóre dane są powtarzalne - warto je wydzielić do osobnych tabel (np. typy opłat dystrybucyjnych).
3. **Klucze obce**: Wszystkie tabele szczegółowe powinny mieć FK do głównej tabeli faktur.
4. **Taryfy**: Schemat obsługuje zarówno taryfę **dwutaryfową** (dzienna/nocna) jak i **całodobową** (jednotaryfową). Pole `typ_taryfy` w głównej tabeli faktur określa typ taryfy.

---

## 1. Tabela: `electricity_invoices` (Dane ogólne faktury)

**Opis**: Główne informacje o fakturze - jedna faktura = jeden rekord.

### Pola:

| Nazwa pola | Typ | Nullable | Opis | PK/FK |
|------------|-----|----------|------|-------|
| `id` | INTEGER | NO | Klucz główny | **PK** |
| `rok` | INTEGER | NO | Rok rozliczeniowy (np. 2021) | |
| `numer_faktury` | VARCHAR(100) | NO | Numer faktury (np. "P/23666363/0001/21") | UNIQUE |
| `data_wystawienia` | DATE | NO | Data wystawienia faktury (data sprzedaży) | |
| `data_poczatku_okresu` | DATE | NO | Data początku okresu rozliczeniowego | |
| `data_konca_okresu` | DATE | NO | Data końca okresu rozliczeniowego | |
| `naleznosc_za_okres` | DECIMAL(10,2) | NO | Należność za okres | |
| `wartosc_prognozy` | DECIMAL(10,2) | NO | Wartość prognozy | |
| `faktury_korygujace` | DECIMAL(10,2) | NO | Faktury korygujące | |
| `odsetki` | DECIMAL(10,2) | NO | Odsetki | |
| `wynik_rozliczenia` | DECIMAL(10,2) | NO | Wynik rozliczenia | |
| `kwota_nadplacona` | DECIMAL(10,2) | NO | Kwota nadpłacona | |
| `saldo_z_rozliczenia` | DECIMAL(10,2) | NO | Saldo z rozliczenia | |
| `niedoplata_nadplata` | DECIMAL(10,2) | NO | Niedopłata/nadpłata | |
| `energia_do_akcyzy_kwh` | INTEGER | NO | Energia do akcyzy (kWh) | |
| `akcyza` | DECIMAL(10,2) | NO | Akcyza | |
| `do_zaplaty` | DECIMAL(10,2) | NO | Do zapłaty (przewidywana należność) | |
| `zuzycie_kwh` | INTEGER | NO | Zużycie: 7.461 kWh | |
| `ogolem_sprzedaz_energii` | DECIMAL(10,2) | NO | Ogółem sprzedaż energii | |
| `ogolem_usluga_dystrybucji` | DECIMAL(10,2) | NO | Ogółem usługa dystrybucji | |
| `grupa_taryfowa` | VARCHAR(10) | NO | Grupa taryfowa (np. "G12", "G11") | |
| `typ_taryfy` | VARCHAR(20) | NO | Typ taryfy: "DWUTARYFOWA" (dzienna/nocna) lub "CAŁODOBOWA" (jednotaryfowa) | |
| `energia_lacznie_zuzyta_w_roku_kwh` | INTEGER | NO | Energia łącznie zużyta w roku (kWh) | |

### Indeksy:
- `UNIQUE(numer_faktury, rok)` - unikalność faktury w danym roku
- `INDEX(rok)` - dla szybkiego filtrowania po roku

---

## 2. Tabela: `electricity_invoice_blankiety` (Blankiety prognozowe)

**Opis**: Blankiety prognozowe - jedna faktura może mieć wiele blankietów.

### Pola:

| Nazwa pola | Typ | Nullable | Opis | PK/FK |
|------------|-----|----------|------|-------|
| `id` | INTEGER | NO | Klucz główny | **PK** |
| `invoice_id` | INTEGER | NO | ID faktury | **FK → electricity_invoices.id** |
| `rok` | INTEGER | NO | Rok (dla szybkiego filtrowania) | |
| `numer_blankietu` | VARCHAR(100) | NO | Nr blankietu (np. "P/23666363/0001/21/1") | |
| `poczatek_podokresu` | DATE | YES | Data początku podokresu | |
| `koniec_podokresu` | DATE | YES | Data końca podokresu | |
| `ilosc_dzienna_kwh` | INTEGER | YES | Ilość dzienna (kWh) - NULL dla taryfy całodobowej | |
| `ilosc_nocna_kwh` | INTEGER | YES | Ilość nocna (kWh) - NULL dla taryfy całodobowej | |
| `ilosc_calodobowa_kwh` | INTEGER | YES | Ilość całodobowa (kWh) - NULL dla taryfy dwutaryfowej | |
| `kwota_brutto` | DECIMAL(10,2) | NO | Kwota brutto | |
| `akcyza` | DECIMAL(10,2) | NO | Akcyza | |
| `energia_do_akcyzy_kwh` | INTEGER | NO | Energia do akcyzy (kWh) | |
| `nadplata_niedoplata` | DECIMAL(10,2) | NO | Nadpłata/Niedopłata | |
| `odsetki` | DECIMAL(10,2) | NO | Odsetki | |
| `termin_platnosci` | DATE | NO | Termin płatności | |
| `do_zaplaty` | DECIMAL(10,2) | NO | Do zapłaty | |

### Indeksy:
- `INDEX(invoice_id)` - dla szybkiego wyszukiwania blankietów faktury
- `INDEX(rok)` - dla filtrowania po roku

---

## 3. Tabela: `electricity_invoice_odczyty` (Odczyty liczników)

**Opis**: Odczyty liczników z faktury - jeden rekord = jeden typ odczytu.

**Dla taryfy dwutaryfowej**: dzienna pobrana, nocna pobrana, dzienna oddana, nocna oddana (4 rekordy).
**Dla taryfy całodobowej**: pobrana, oddana (2 rekordy, `strefa` = NULL).

### Pola:

| Nazwa pola | Typ | Nullable | Opis | PK/FK |
|------------|-----|----------|------|-------|
| `id` | INTEGER | NO | Klucz główny | **PK** |
| `invoice_id` | INTEGER | NO | ID faktury | **FK → electricity_invoices.id** |
| `rok` | INTEGER | NO | Rok | |
| `typ_energii` | VARCHAR(20) | NO | "POBRANA" lub "ODDANA" | |
| `strefa` | VARCHAR(10) | YES | "DZIENNA", "NOCNA" (dla taryfy dwutaryfowej) lub NULL (dla taryfy całodobowej) | |
| `data_odczytu` | DATE | NO | Data odczytu | |
| `biezacy_odczyt` | INTEGER | NO | Bieżący odczyt | |
| `poprzedni_odczyt` | INTEGER | NO | Poprzedni odczyt | |
| `mnozna` | INTEGER | NO | Mnożna (zwykle 1) | |
| `ilosc_kwh` | INTEGER | NO | Ilość (kWh) | |
| `straty_kwh` | INTEGER | NO | Straty (kWh) | |
| `razem_kwh` | INTEGER | NO | Razem (kWh) | |

### Indeksy:
- `INDEX(invoice_id)` - dla szybkiego wyszukiwania odczytów faktury
- `INDEX(rok)` - dla filtrowania po roku
- `UNIQUE(invoice_id, typ_energii, strefa)` - jeden typ odczytu na fakturę (dla taryfy dwutaryfowej: unikalność po typ_energii+strefa, dla całodobowej: unikalność po typ_energii gdzie strefa IS NULL)

---

## 4. Tabela: `electricity_invoice_sprzedaz_energii` (Sprzedaż energii szczegółowo)

**Opis**: Szczegółowe pozycje sprzedaży energii - jedna faktura może mieć wiele pozycji.

**Dla taryfy dwutaryfowej**: pozycje z `strefa` = "DZIENNA" lub "NOCNA".
**Dla taryfy całodobowej**: pozycje z `strefa` = NULL lub "CAŁODOBOWA".

### Pola:

| Nazwa pola | Typ | Nullable | Opis | PK/FK |
|------------|-----|----------|------|-------|
| `id` | INTEGER | NO | Klucz główny | **PK** |
| `invoice_id` | INTEGER | NO | ID faktury | **FK → electricity_invoices.id** |
| `rok` | INTEGER | NO | Rok | |
| `data` | DATE | YES | Data (pobierana z rozliczenia) | |
| `strefa` | VARCHAR(10) | YES | "DZIENNA", "NOCNA" (dla taryfy dwutaryfowej) lub NULL/"CAŁODOBOWA" (dla taryfy całodobowej) | |
| `ilosc_kwh` | INTEGER | NO | Ilość (kWh) | |
| `cena_za_kwh` | DECIMAL(10,4) | NO | Cena (zł/kWh) | |
| `naleznosc` | DECIMAL(10,2) | NO | Należność | |
| `vat_procent` | DECIMAL(5,2) | NO | VAT (%) | |

### Indeksy:
- `INDEX(invoice_id)` - dla szybkiego wyszukiwania pozycji faktury
- `INDEX(rok)` - dla filtrowania po roku

---

## 5. Tabela: `electricity_invoice_oplaty_dystrybucyjne` (Opłaty dystrybucyjne)

**Opis**: Szczegółowe opłaty dystrybucyjne - jedna faktura może mieć wiele opłat różnych typów.

### Pola:

| Nazwa pola | Typ | Nullable | Opis | PK/FK |
|------------|-----|----------|------|-------|
| `id` | INTEGER | NO | Klucz główny | **PK** |
| `invoice_id` | INTEGER | NO | ID faktury | **FK → electricity_invoices.id** |
| `rok` | INTEGER | NO | Rok | |
| `typ_oplaty` | VARCHAR(50) | NO | Typ opłaty (np. "OPŁATA OZE", "OPŁATA JAKOŚCIOWA", "OPŁATA KOGENERACYJNA", "OPŁATA MOCOWA", "OPŁATA STAŁA SIECIOWA", "OPŁATA ZMIENNA SIECIOWA") | |
| `strefa` | VARCHAR(10) | YES | "DZIENNA", "NOCNA" (dla taryfy dwutaryfowej), "CAŁODOBOWA" lub NULL (dla opłat niezależnych od strefy) | |
| `jednostka` | VARCHAR(20) | NO | Jednostka (np. "kWh", "zł/mc") | |
| `data` | DATE | NO | Data | |
| `ilosc_kwh` | INTEGER | YES | Ilość kWh (NULL jeśli jednostka to "zł/mc") | |
| `ilosc_miesiecy` | INTEGER | YES | Ilość miesięcy (NULL jeśli jednostka to "kWh") | |
| `wspolczynnik` | DECIMAL(10,4) | YES | Współczynnik (dla opłaty stałej sieciowej) | |
| `cena` | DECIMAL(10,4) | NO | Cena | |
| `naleznosc` | DECIMAL(10,2) | NO | Należność | |
| `vat_procent` | DECIMAL(5,2) | NO | VAT (%) | |

### Indeksy:
- `INDEX(invoice_id)` - dla szybkiego wyszukiwania opłat faktury
- `INDEX(rok)` - dla filtrowania po roku
- `INDEX(typ_oplaty)` - dla analiz po typach opłat

---

## 6. Tabela: `electricity_invoice_rozliczenie_okresy` (Rozliczenie po okresach)

**Opis**: Rozliczenie po okresach - jedna faktura może mieć wiele okresów rozliczeniowych.

### Pola:

| Nazwa pola | Typ | Nullable | Opis | PK/FK |
|------------|-----|----------|------|-------|
| `id` | INTEGER | NO | Klucz główny | **PK** |
| `invoice_id` | INTEGER | NO | ID faktury | **FK → electricity_invoices.id** |
| `rok` | INTEGER | NO | Rok | |
| `data_okresu` | DATE | NO | Data okresu (np. 31/12/2020) | |
| `numer_okresu` | INTEGER | NO | Numer okresu w fakturze (1, 2, 3...) | |

### Indeksy:
- `INDEX(invoice_id)` - dla szybkiego wyszukiwania okresów faktury
- `INDEX(rok)` - dla filtrowania po roku
- `UNIQUE(invoice_id, numer_okresu)` - unikalność numeru okresu w fakturze

**Uwaga**: Ta tabela może być połączona z innymi tabelami przez `invoice_id` i `data_okresu`, aby powiązać odczyty, sprzedaż energii i opłaty dystrybucyjne z konkretnym okresem.

---

## Diagram relacji

```
electricity_invoices (1)
    │
    ├──→ (1:N) electricity_invoice_blankiety
    ├──→ (1:N) electricity_invoice_odczyty
    ├──→ (1:N) electricity_invoice_sprzedaz_energii
    ├──→ (1:N) electricity_invoice_oplaty_dystrybucyjne
    └──→ (1:N) electricity_invoice_rozliczenie_okresy
```

---

## Uwagi i sugestie zmian

### 1. **Pole `rok` we wszystkich tabelach**
   - ✅ **Zachowane** - ułatwia filtrowanie i grupowanie bez konieczności JOIN
   - Można rozważyć usunięcie dla normalizacji, ale wydajność może być ważniejsza

### 2. **Tabela `electricity_invoice_rozliczenie_okresy`**
   - ⚠️ **Uproszczona** - zawiera tylko datę i numer okresu
   - Można rozważyć dodanie pól z odczytami bezpośrednio tutaj, ale to by duplikowało dane z `electricity_invoice_odczyty`
   - **Zalecenie**: Zachować obecną strukturę - odczyty są w osobnej tabeli

### 3. **Pole `data` w `electricity_invoice_sprzedaz_energii`**
   - ✅ **Zachowane jako nullable** - nie wszystkie pozycje mogą mieć datę
   - Można powiązać z `electricity_invoice_rozliczenie_okresy` przez `data_okresu`, ale to wymaga dodatkowego JOIN

### 4. **Typy opłat dystrybucyjnych**
   - ✅ **Zachowane jako VARCHAR** - elastyczne rozwiązanie
   - Alternatywa: tabela słownikowa `electricity_oplaty_typy`, ale może być overkill dla małej liczby typów

### 5. **Dodatkowe pola w `electricity_invoices`**
   - ✅ Dodano `do_zaplaty` - przewidywana należność
   - ✅ Dodano `zuzycie_kwh` - zużycie z rozliczenia
   - ✅ Dodano `energia_lacznie_zuzyta_w_roku_kwh` - energia łącznie zużyta w roku

### 6. **Normalizacja vs. Wydajność**
   - Struktura jest zbalansowana między normalizacją a wydajnością
   - Pole `rok` jest zduplikowane, ale ułatwia zapytania
   - Wszystkie szczegółowe tabele mają FK do głównej tabeli faktur

### 7. **Typy danych**
   - `DECIMAL(10,2)` dla kwot - precyzja do groszy
   - `DECIMAL(10,4)` dla cen - precyzja do 4 miejsc po przecinku
   - `INTEGER` dla kWh - zużycie energii w całych kWh
   - `DATE` dla dat

### 8. **Obsługa taryfy całodobowej (jednotaryfowej)**
   - ✅ Dodano pole `typ_taryfy` w `electricity_invoices` - określa czy faktura używa taryfy dwutaryfowej czy całodobowej
   - ✅ W `electricity_invoice_blankiety`: `ilosc_dzienna_kwh` i `ilosc_nocna_kwh` są nullable, dodano `ilosc_calodobowa_kwh`
   - ✅ W `electricity_invoice_odczyty`: `strefa` jest nullable - dla taryfy całodobowej będzie NULL
   - ✅ W `electricity_invoice_sprzedaz_energii`: `strefa` jest nullable - dla taryfy całodobowej będzie NULL lub "CAŁODOBOWA"
   - ✅ W `electricity_invoice_oplaty_dystrybucyjne`: `strefa` już była nullable, teraz może przyjmować również "CAŁODOBOWA"
   - **Uwaga**: Dla taryfy całodobowej w blankietach należy wypełnić `ilosc_calodobowa_kwh`, a `ilosc_dzienna_kwh` i `ilosc_nocna_kwh` pozostawić jako NULL

### 9. **Brakujące pola (do rozważenia)**
   - ✅ W `electricity_invoices`: dodano pole `data_wystawienia` (data sprzedaży)
   - W `electricity_invoice_blankiety`: może brakować pola `status` (opłacony/nieopłacony)

---

## Przykładowe zapytania

### Pobranie pełnej faktury z wszystkimi szczegółami:
```sql
SELECT 
    i.*,
    COUNT(DISTINCT b.id) as liczba_blankietow,
    COUNT(DISTINCT o.id) as liczba_odczytow,
    COUNT(DISTINCT s.id) as liczba_pozycji_sprzedazy,
    COUNT(DISTINCT op.id) as liczba_oplat
FROM electricity_invoices i
LEFT JOIN electricity_invoice_blankiety b ON i.id = b.invoice_id
LEFT JOIN electricity_invoice_odczyty o ON i.id = o.invoice_id
LEFT JOIN electricity_invoice_sprzedaz_energii s ON i.id = s.invoice_id
LEFT JOIN electricity_invoice_oplaty_dystrybucyjne op ON i.id = op.invoice_id
WHERE i.numer_faktury = 'P/23666363/0001/21'
GROUP BY i.id;
```

### Suma opłat dystrybucyjnych po typach dla faktury:
```sql
SELECT 
    typ_oplaty,
    SUM(naleznosc) as suma_naleznosci
FROM electricity_invoice_oplaty_dystrybucyjne
WHERE invoice_id = ?
GROUP BY typ_oplaty;
```

### Pobranie odczytów z uwzględnieniem typu taryfy:
```sql
-- Dla taryfy dwutaryfowej
SELECT * FROM electricity_invoice_odczyty
WHERE invoice_id = ? AND strefa IS NOT NULL;

-- Dla taryfy całodobowej
SELECT * FROM electricity_invoice_odczyty
WHERE invoice_id = ? AND strefa IS NULL;
```

### Pobranie blankietów z uwzględnieniem typu taryfy:
```sql
-- Dla taryfy dwutaryfowej (dzienna + nocna)
SELECT 
    id,
    ilosc_dzienna_kwh,
    ilosc_nocna_kwh,
    (ilosc_dzienna_kwh + ilosc_nocna_kwh) as ilosc_laczna_kwh
FROM electricity_invoice_blankiety
WHERE invoice_id = ? AND ilosc_calodobowa_kwh IS NULL;

-- Dla taryfy całodobowej
SELECT 
    id,
    ilosc_calodobowa_kwh
FROM electricity_invoice_blankiety
WHERE invoice_id = ? AND ilosc_calodobowa_kwh IS NOT NULL;
```

