# Przykłady użycia API

## Dodawanie faktury ręcznie

### POST /invoices/

Ręczne dodawanie faktury do bazy danych. **Uwaga:** Możesz dodać wiele faktur dla tego samego okresu (np. z powodu podwyżki kosztów):

```bash
curl -X POST "http://localhost:8000/invoices/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02" \
  -d "usage=45.5" \
  -d "water_cost_m3=15.20" \
  -d "sewage_cost_m3=12.50" \
  -d "nr_of_subscription=2" \
  -d "water_subscr_cost=18.50" \
  -d "sewage_subscr_cost=16.00" \
  -d "vat=0.08" \
  -d "period_start=2025-01-01" \
  -d "period_stop=2025-02-28" \
  -d "invoice_number=FV-2025-002" \
  -d "gross_sum=1560.50"
```

### Wszystkie parametry:

- **data** (string): Okres rozliczeniowy w formacie 'YYYY-MM' (np. '2025-02')
- **usage** (float): Zużycie wody w m³
- **water_cost_m3** (float): Koszt wody za m³
- **sewage_cost_m3** (float): Koszt ścieków za m³
- **nr_of_subscription** (int): Liczba miesięcy abonamentu
- **water_subscr_cost** (float): Koszt abonamentu wody za miesiąc
- **sewage_subscr_cost** (float): Koszt abonamentu ścieków za miesiąc
- **vat** (float): Podatek VAT (np. 0.08 dla 8%)
- **period_start** (string): Data początku okresu w formacie 'YYYY-MM-DD'
- **period_stop** (string): Data końca okresu w formacie 'YYYY-MM-DD'
- **invoice_number** (string): Numer faktury
- **gross_sum** (float): Suma brutto faktury

## Dodawanie odczytu liczników

### POST /readings/

```bash
curl -X POST "http://localhost:8000/readings/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "data=2025-02" \
  -d "water_meter_main=150.5" \
  -d "water_meter_5=45.0" \
  -d "water_meter_5b=38.0"
```

## Dodawanie lokalizacji

### POST /locals/

```bash
curl -X POST "http://localhost:8000/locals/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "water_meter_name=water_meter_5" \
  -d "tenant=Jan Kowalski" \
  -d "local=gora"
```

## Generowanie rachunków

### POST /bills/generate/{period}

```bash
curl -X POST "http://localhost:8000/bills/generate/2025-02"
```

## Pobieranie listy faktur

### GET /invoices/

```bash
curl -X GET "http://localhost:8000/invoices/"
```

## Pobieranie rachunku PDF

### GET /bills/download/{bill_id}

```bash
curl -X GET "http://localhost:8000/bills/download/1" -o bill.pdf
```

## Usuwanie rachunków

### DELETE /bills/{bill_id} - Usuń pojedynczy rachunek

```bash
curl -X DELETE "http://localhost:8000/bills/1"
```

### DELETE /bills/period/{period} - Usuń rachunki dla okresu

```bash
curl -X DELETE "http://localhost:8000/bills/period/2025-02"
```

### DELETE /bills/ - Usuń wszystkie rachunki

```bash
curl -X DELETE "http://localhost:8000/bills/"
```

**Uwaga:** Endpoint `DELETE /bills/` usuwa wszystkie rachunki z bazy danych. Używaj ostrożnie!

