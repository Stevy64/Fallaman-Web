from apps.core.utils import format_fcfa, looks_like_money_request, normalize_text


def test_format_fcfa():
    assert format_fcfa(200000) == "200 000 FCFA"


def test_normalize_and_money_detection():
    assert "menagere" in normalize_text("ménagère")
    assert looks_like_money_request("Envoyez 5000 FCFA pour votre inscription")
