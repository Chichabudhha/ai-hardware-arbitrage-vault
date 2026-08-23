from decimal import Decimal

from src.scrapers.html_parse import fields_from_json_ld, parse_price, soup_of

JSON_LD_PAGE = """
<html><head><script type="application/ld+json">
{"@type":"Product","name":"RTX 3090 24GB","description":"Kao nova",
 "offers":{"@type":"Offer","price":"620.00","priceCurrency":"EUR"}}
</script></head><body></body></html>
"""


def test_parse_price_european_format():
    assert parse_price("1.250,00 €") == (Decimal("1250.00"), "EUR")


def test_parse_price_rsd_thousands():
    amount, currency = parse_price("149.900 RSD")
    assert (amount, currency) == (Decimal("149900"), "RSD")


def test_parse_price_unknown_is_none():
    assert parse_price(None) == (None, None)
    assert parse_price("po dogovoru")[0] is None


def test_json_ld_extraction():
    fields = fields_from_json_ld(soup_of(JSON_LD_PAGE))
    assert fields.title == "RTX 3090 24GB"
    assert fields.price_amount == Decimal("620.00")
    assert fields.currency == "EUR"
