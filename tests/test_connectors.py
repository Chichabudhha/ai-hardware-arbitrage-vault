from decimal import Decimal

from src.core.models import AutomationStatus
from src.scrapers.base import payload_hash
from src.scrapers.kleinanzeigen import KleinanzeigenConnector
from src.scrapers.kupujemprodajem import KupujemProdajemConnector
from src.scrapers.manual_import import import_file

KP_PAGE = """
<html><body>
<h1>RTX 3090 24GB Gigabyte</h1>
<div class="price">89.900 din</div>
<div class="description">Kupljena 2022, racun postoji.</div>
<div class="userName">Marko</div>
<div class="location">Novi Sad</div>
</body></html>
"""

KA_SEARCH = """
<html><body>
<li><a href="/s-anzeige/rtx-3090/2233445566">RTX 3090</a></li>
<li><a href="/s-anzeige/rtx-4090/9988776655">RTX 4090</a></li>
<li><a href="/s-anzeige/rtx-3090/2233445566">duplikat</a></li>
</body></html>
"""


def test_kp_normalizes_manual_observation(tmp_path):
    saved = tmp_path / "oglas.html"
    saved.write_text(KP_PAGE, encoding="utf-8")

    listing = import_file(
        saved, "kupujemprodajem", "111", "https://www.kupujemprodajem.com/oglas/111"
    )

    assert listing.title == "RTX 3090 24GB Gigabyte"
    assert listing.price_amount == Decimal("89900")
    assert listing.currency == "RSD"
    assert listing.seller_name == "Marko"
    assert listing.location == "Novi Sad"
    assert listing.has_financial_minimum()
    assert listing.provenance.method.endswith(AutomationStatus.MANUAL.value)


def test_search_page_parsing_dedupes_listings():
    connector = KleinanzeigenConnector()
    observations = connector.parse_search_page(KA_SEARCH, "https://www.kleinanzeigen.de/s-x/k0")
    ids = [observation.source_listing_id for observation in observations]
    assert ids == ["2233445566", "9988776655"]


def test_listing_id_extraction():
    assert KupujemProdajemConnector.listing_id_from_url("/oglas/graficka-karta/98765") == "98765"
    assert KupujemProdajemConnector.listing_id_from_url("/pretraga?x=1") is None
    assert (
        KleinanzeigenConnector.listing_id_from_url("/s-anzeige/rtx-3090/2233445566")
        == "2233445566"
    )


def test_raw_payload_hash_is_stable():
    assert payload_hash("abc") == payload_hash("abc")
    assert payload_hash("abc") != payload_hash("abd")
