---
updated: 2026-08-19
status: u toku
odluka: D-017
---

# Merni prolaz po EU oglasnicima

> Cilj: pre nego što se uloži rad u konektore, izmeriti **ima li uopšte jeftinije
> robe nego u Nemačkoj**. Referenca je srpska preprodajna procena
> `rtx-3080-ti` = **380 €** (P25, n=9, ASKING) i landed cost = cena + 25 € prevoz
> + 15 € posrednik (D-015/D-016).

Prag: pri trošku dopreme od 40 €, nabavna cena mora biti **ispod ~290 €** da bi
kartica prošla oba BUY praga (ROI ≥ 18 %, profit ≥ 50 €) pri Low riziku.

## Izmereno

### Nemačka — `kleinanzeigen.de` (2026-08-19)

24 oglasa za RTX 3080 Ti, gole polovne kartice **245–600 €**, težište oko
300–420 €. Tri kandidata ocenjena: NEGOTIATE (245 €), WATCH (300 €), SKIP (350 €).
**Jedini izvor koji je do sada dao pozitivan verdikt.**

### Austrija — `willhaben.at` (2026-08-19)

80 oglasa za „rtx 3080 ti", ali velika većina su gotovi računari (1.100–1.650 €).
Gole kartice: **499, 500, 500, 550 €** (MSI, Zotac, EVGA FTW3, MSI sa vodenim
blokom).

**Zaključak: Austrija otpada.** Najjeftinija gola kartica je 499 €, što je iznad
srpske preprodajne procene od 380 € i pre bilo kakvog troška dopreme. Nije stvar
marže — cena izvora je viša od cene izlaza.

Zapažanje koje verovatno važi šire: nemačko tržište je jeftino zato što je
duboko. Mala tržišta imaju manju ponudu i više cene, pa blizina ne pomaže —
pogotovo jer je prevoz po D-016 isti za svaku EU zemlju.

### Mađarska — `hardverapro.hu` (2026-08-19)

Jedna jedina RTX 3080 Ti: **195.000 Ft**. Da bi to bilo ispod praga od 290 €,
kurs bi morao da bude ~672 HUF/€ — nije blizu stvarnog. **Otpada.**

Zapažanje sa strane: obična RTX 3080 (10/12 GB) je tamo česta i jeftina
(70.000-158.500 Ft). Nije u katalogu (D-011), pa nije ni računata. Ako se
katalog ikad širi, Mađarska je razlog da se pogleda baš taj model.

### Rumunija — `olx.ro` (2026-08-19)

Gole kartice: **2.200-2.400 lei** (ASUS TUF, Zotac Trinity, EVGA, Aorus Master,
Palit), jedna 3.170 lei. Da bi 2.200 lei bilo ispod 290 €, kurs bi morao da bude
~7,6 RON/€ — nije blizu stvarnog. **Otpada.**

### Hrvatska — `njuskalo.hr` (2026-08-19)

Hrvatska je u evrozoni, pa je poređenje direktno. Gole kartice: **300 €**
(Palit), pa skok na **490, 499, 500 €**. Ostalo su laptopovi i konfiguracije.
Najjeftinija je iznad praga od 290 €. **Otpada**, mada je 300 € najbliže od svih
ne-nemačkih izvora.

### Italija — `subito.it` (2026-08-19)

Gole kartice: **350, 420, 429, 430, 440, 450, 600, 650 €**. Težište 420-450 €.
Najjeftinija (350 €) je na gornjoj granici nemačkog raspona. **Otpada.**

## Ispravka nakon D-018/D-019: „skupo" je nalaz, ne odbacivanje

Prvi prolaz je svako tržište merio samo kao **izvor** i odbacivao ono što je
skupo. Sa matricom cena (D-018) i prikazom u evrima (D-019) vidi se druga
strana: tržište koje je skupo za kupovinu je kandidat za **prodaju**.

Rumunija je najjasniji primer. Kao izvor otpada (2.200 RON ≈ 419 € najjeftinija),
ali joj je medijana **452,79 €**, najviša od svih izmerenih. Sa nemačkim P25 od
338 € to je bruto razlika od **114,79 €**, odnosno **+89,79 € posle 25 € prevoza**
— duplo više nego DE→RS.

Uzorak: 8 rumunskih oglasa upisano, 6 preživelo IQR filter (3.170 i 3.589 RON
ispali kao odudarajući). Kurs: BNR, 19.08.2026, 1 EUR = 5,2452 RON.

**Ovo nije preporuka za trgovinu.** DE→RO je EU-interni koridor, dakle bez
carine, ali provizija platforme, porez i rizik prodaje na daljinu nisu ni
izmereni ni odlučeni (otvorena pitanja iz D-018).

## Zaključak mernog prolaza (kao izvor nabavke)

**Nemačka je jedini izvor ispod praga.** Svi ostali izmereni EU izvori počinju
tamo gde nemački raspon završava:

| Zemlja | Najjeftinija gola 3080 Ti | Ispod 290 €? |
|---|---|---|
| Nemačka | 245 € | **da** (više komada) |
| Hrvatska | 300 € | ne |
| Italija | 350 € | ne |
| Austrija | 499 € | ne |
| Rumunija | ~2.200 lei | ne |
| Mađarska | 195.000 Ft | ne |

Širenje na više zemalja **ne rešava problem tanke marže**. Prednost nije u
blizini — prevoz je ionako isti (D-016) — nego u dubini tržišta: Nemačka ima
dovoljno ponude da postoji donji rep cena, mala tržišta ga nemaju.

Praktična posledica za W6: paper trading ostaje na nemačkim oglasima; ostale
zemlje se ne prate dok se ne pojavi razlog (npr. drugi model, ili pad cena).

## Nije izmereno — čeka dozvolu domena u Chrome ekstenziji

Navigacija je blokirana („Navigation to this domain is not allowed") za sve
domene osim `kupujemprodajem.com`, `kleinanzeigen.de` i `willhaben.at`.

| Zemlja | Sajt | Status |
|---|---|---|
| Bugarska | `olx.bg` | blokiran |
| Slovenija | `bolha.com` | blokiran |
| Belgija/Holandija | `2dehands.be`, `marktplaats.nl` | nije probano |

Ova tri su najmanje zanimljiva: Slovenija i Bugarska su mala tržišta (isti
obrazac kao Austrija i Hrvatska), a Belgija/Holandija su veće, ali nijedan
izmereni izvor osim Nemačke nije prišao pragu.

## Metod

Pretraga po modelu u kategoriji grafičkih kartica, čitanje javno vidljivih
rezultata, bez prijave i bez zaobilaženja ičega (D-017). Iz uzorka se izbacuju:
gotovi računari i laptopovi, kuleri i vodeni blokovi, „tražim/otkup" oglasi i
prodavnički oglasi novih kartica. Cookie baner se odbija, ne prihvata.
