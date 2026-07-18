from app.retrieval.normalize import normalize_query


def test_lowercases_query():
    assert normalize_query("Terraform Drift") == "terraform drift"


def test_expands_known_alias():
    assert normalize_query("tf drift") == "terraform drift"


def test_expands_alias_regardless_of_case():
    assert normalize_query("K8S scaling") == "kubernetes scaling"


def test_does_not_expand_alias_substring_inside_another_word():
    # "tf" must not match inside "artful" — whole-token matching only
    assert normalize_query("artful dodger") == "artful dodger"


def test_normalizes_punctuation_and_whitespace():
    assert normalize_query("terraform,   drift!!") == "terraform drift"


def test_preserves_exact_technical_tokens_not_in_glossary():
    assert normalize_query("pve-dain OIDC") == "pve-dain oidc"
