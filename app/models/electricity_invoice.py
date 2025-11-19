"""
Modele SQLAlchemy dla szczegółowych faktur prądu.
Definiuje tabele zgodnie ze schematem z propozycja_tabel_prąd.md:
- electricity_invoices (główna tabela faktur)
- electricity_invoice_blankiety (blankiety prognozowe)
- electricity_invoice_odczyty (odczyty liczników)
- electricity_invoice_sprzedaz_energii (sprzedaż energii szczegółowo)
- electricity_invoice_oplaty_dystrybucyjne (opłaty dystrybucyjne)
- electricity_invoice_rozliczenie_okresy (rozliczenie po okresach)
"""

from sqlalchemy import Column, String, Float, Integer, Date, ForeignKey, UniqueConstraint, Index, Numeric, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class ElectricityInvoice(Base):
    """
    Główna tabela faktur prądu - dane ogólne faktury.
    Jedna faktura = jeden rekord.
    """
    __tablename__ = "electricity_invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rok = Column(Integer, nullable=False, index=True)  # Rok rozliczeniowy (np. 2021)
    numer_faktury = Column(String(100), nullable=False)  # Numer faktury (np. "P/23666363/0001/21")
    data_wystawienia = Column(Date, nullable=False)  # Data wystawienia faktury (data sprzedaży)
    data_poczatku_okresu = Column(Date, nullable=False)  # Data początku okresu rozliczeniowego
    data_konca_okresu = Column(Date, nullable=False)  # Data końca okresu rozliczeniowego
    
    # Podsumowanie finansowe
    naleznosc_za_okres = Column(Numeric(10, 2), nullable=False)
    wartosc_prognozy = Column(Numeric(10, 2), nullable=False)
    faktury_korygujace = Column(Numeric(10, 2), nullable=False)
    odsetki = Column(Numeric(10, 2), nullable=False)
    wynik_rozliczenia = Column(Numeric(10, 2), nullable=False)
    kwota_nadplacona = Column(Numeric(10, 2), nullable=False)
    saldo_z_rozliczenia = Column(Numeric(10, 2), nullable=False)
    niedoplata_nadplata = Column(Numeric(10, 2), nullable=False)
    
    # Akcyza
    energia_do_akcyzy_kwh = Column(Integer, nullable=False)
    akcyza = Column(Numeric(10, 2), nullable=False)
    
    # Inne
    do_zaplaty = Column(Numeric(10, 2), nullable=False)  # Do zapłaty (przewidywana należność)
    zuzycie_kwh = Column(Integer, nullable=False)  # Zużycie: 7.461 kWh
    ogolem_sprzedaz_energii = Column(Numeric(10, 2), nullable=False)
    ogolem_usluga_dystrybucji = Column(Numeric(10, 2), nullable=False)
    grupa_taryfowa = Column(String(10), nullable=False)  # Grupa taryfowa (np. "G12", "G11")
    typ_taryfy = Column(String(20), nullable=False)  # "DWUTARYFOWA" lub "CAŁODOBOWA"
    energia_lacznie_zuzyta_w_roku_kwh = Column(Integer, nullable=False)
    
    # Flaga
    is_flagged = Column(Boolean, nullable=False, default=False)  # Flaga do oznaczenia podejrzanych/niewłaściwych faktur
    
    # Relacje
    bills = relationship("ElectricityBill", back_populates="invoice", cascade="all, delete-orphan")
    blankiety = relationship("ElectricityInvoiceBlankiet", back_populates="invoice", cascade="all, delete-orphan")
    odczyty = relationship("ElectricityInvoiceOdczyt", back_populates="invoice", cascade="all, delete-orphan")
    sprzedaz_energii = relationship("ElectricityInvoiceSprzedazEnergii", back_populates="invoice", cascade="all, delete-orphan")
    oplaty_dystrybucyjne = relationship("ElectricityInvoiceOplataDystrybucyjna", back_populates="invoice", cascade="all, delete-orphan")
    rozliczenie_okresy = relationship("ElectricityInvoiceRozliczenieOkres", back_populates="invoice", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('numer_faktury', 'rok', name='uq_invoice_number_year'),
        Index('idx_rok', 'rok'),
    )


class ElectricityInvoiceBlankiet(Base):
    """
    Blankiety prognozowe - jedna faktura może mieć wiele blankietów.
    """
    __tablename__ = "electricity_invoice_blankiety"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'), nullable=False, index=True)
    rok = Column(Integer, nullable=False, index=True)
    numer_blankietu = Column(String(100), nullable=False)
    poczatek_podokresu = Column(Date, nullable=True)
    koniec_podokresu = Column(Date, nullable=True)
    
    # Ilości energii - dla taryfy dwutaryfowej
    ilosc_dzienna_kwh = Column(Integer, nullable=True)  # NULL dla taryfy całodobowej
    ilosc_nocna_kwh = Column(Integer, nullable=True)  # NULL dla taryfy całodobowej
    
    # Ilość energii - dla taryfy całodobowej
    ilosc_calodobowa_kwh = Column(Integer, nullable=True)  # NULL dla taryfy dwutaryfowej
    
    # Finanse
    kwota_brutto = Column(Numeric(10, 2), nullable=False)
    akcyza = Column(Numeric(10, 2), nullable=False)
    energia_do_akcyzy_kwh = Column(Integer, nullable=False)
    nadplata_niedoplata = Column(Numeric(10, 2), nullable=False)
    odsetki = Column(Numeric(10, 2), nullable=False)
    termin_platnosci = Column(Date, nullable=False)
    do_zaplaty = Column(Numeric(10, 2), nullable=False)
    
    # Relacje
    invoice = relationship("ElectricityInvoice", back_populates="blankiety")
    
    __table_args__ = (
        Index('idx_invoice_id', 'invoice_id'),
        Index('idx_rok', 'rok'),
    )


class ElectricityInvoiceOdczyt(Base):
    """
    Odczyty liczników z faktury.
    
    Dla taryfy dwutaryfowej: dzienna pobrana, nocna pobrana, dzienna oddana, nocna oddana (4 rekordy).
    Dla taryfy całodobowej: pobrana, oddana (2 rekordy, strefa = NULL).
    """
    __tablename__ = "electricity_invoice_odczyty"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'), nullable=False, index=True)
    rok = Column(Integer, nullable=False, index=True)
    typ_energii = Column(String(20), nullable=False)  # "POBRANA" lub "ODDANA"
    strefa = Column(String(10), nullable=True)  # "DZIENNA", "NOCNA" (dla dwutaryfowej) lub NULL (dla całodobowej)
    data_odczytu = Column(Date, nullable=False)
    biezacy_odczyt = Column(Integer, nullable=False)
    poprzedni_odczyt = Column(Integer, nullable=False)
    mnozna = Column(Integer, nullable=False)
    ilosc_kwh = Column(Integer, nullable=False)
    straty_kwh = Column(Integer, nullable=False)
    razem_kwh = Column(Integer, nullable=False)
    
    # Relacje
    invoice = relationship("ElectricityInvoice", back_populates="odczyty")
    
    __table_args__ = (
        Index('idx_invoice_id', 'invoice_id'),
        Index('idx_rok', 'rok'),
        UniqueConstraint('invoice_id', 'typ_energii', 'strefa', 'data_odczytu', name='uq_invoice_energy_type_zone_date'),
    )


class ElectricityInvoiceSprzedazEnergii(Base):
    """
    Szczegółowe pozycje sprzedaży energii - jedna faktura może mieć wiele pozycji.
    
    Dla taryfy dwutaryfowej: pozycje z strefa = "DZIENNA" lub "NOCNA".
    Dla taryfy całodobowej: pozycje z strefa = NULL lub "CAŁODOBOWA".
    """
    __tablename__ = "electricity_invoice_sprzedaz_energii"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'), nullable=False, index=True)
    rok = Column(Integer, nullable=False, index=True)
    data = Column(Date, nullable=True)  # Data (pobierana z rozliczenia)
    strefa = Column(String(10), nullable=True)  # "DZIENNA", "NOCNA" (dla dwutaryfowej) lub NULL/"CAŁODOBOWA" (dla całodobowej)
    ilosc_kwh = Column(Integer, nullable=False)
    cena_za_kwh = Column(Numeric(10, 4), nullable=False)
    naleznosc = Column(Numeric(10, 2), nullable=False)
    vat_procent = Column(Numeric(5, 2), nullable=False)  # VAT (%)
    
    # Relacje
    invoice = relationship("ElectricityInvoice", back_populates="sprzedaz_energii")
    
    __table_args__ = (
        Index('idx_invoice_id', 'invoice_id'),
        Index('idx_rok', 'rok'),
    )


class ElectricityInvoiceOplataDystrybucyjna(Base):
    """
    Szczegółowe opłaty dystrybucyjne - jedna faktura może mieć wiele opłat różnych typów.
    """
    __tablename__ = "electricity_invoice_oplaty_dystrybucyjne"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'), nullable=False, index=True)
    rok = Column(Integer, nullable=False, index=True)
    typ_oplaty = Column(String(50), nullable=False)  # np. "OPŁATA OZE", "OPŁATA JAKOŚCIOWA", etc.
    strefa = Column(String(10), nullable=True)  # "DZIENNA", "NOCNA" (dla dwutaryfowej), "CAŁODOBOWA" lub NULL
    jednostka = Column(String(20), nullable=False)  # np. "kWh", "zł/mc"
    data = Column(Date, nullable=False)
    ilosc_kwh = Column(Integer, nullable=True)  # NULL jeśli jednostka to "zł/mc"
    ilosc_miesiecy = Column(Integer, nullable=True)  # NULL jeśli jednostka to "kWh"
    wspolczynnik = Column(Numeric(10, 4), nullable=True)  # Współczynnik (dla opłaty stałej sieciowej)
    cena = Column(Numeric(10, 4), nullable=False)
    naleznosc = Column(Numeric(10, 2), nullable=False)
    vat_procent = Column(Numeric(5, 2), nullable=False)  # VAT (%)
    
    # Relacje
    invoice = relationship("ElectricityInvoice", back_populates="oplaty_dystrybucyjne")
    
    __table_args__ = (
        Index('idx_invoice_id', 'invoice_id'),
        Index('idx_rok', 'rok'),
        Index('idx_typ_oplaty', 'typ_oplaty'),
    )


class ElectricityInvoiceRozliczenieOkres(Base):
    """
    Rozliczenie po okresach - jedna faktura może mieć wiele okresów rozliczeniowych.
    """
    __tablename__ = "electricity_invoice_rozliczenie_okresy"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('electricity_invoices.id'), nullable=False, index=True)
    rok = Column(Integer, nullable=False, index=True)
    data_okresu = Column(Date, nullable=False)  # Data okresu (np. 31/12/2020)
    numer_okresu = Column(Integer, nullable=False)  # Numer okresu w fakturze (1, 2, 3...)
    
    # Relacje
    invoice = relationship("ElectricityInvoice", back_populates="rozliczenie_okresy")
    
    __table_args__ = (
        Index('idx_invoice_id', 'invoice_id'),
        Index('idx_rok', 'rok'),
        UniqueConstraint('invoice_id', 'numer_okresu', name='uq_invoice_period_number'),
    )

