from apps.ingest.parsers.names import clean, display_name, search_name


def test_hangul_fillers_become_spaces():
    assert display_name("NBㅤVALSIᴰˢ") == "NB VALSIᴰˢ"
    assert display_name("S&UᅠLIGHT") == "S&U LIGHT"


def test_trailing_and_repeated_fillers_are_trimmed():
    assert display_name("SYN.ISAGI文ㅤㅤ") == "SYN.ISAGI文"
    assert display_name("SYNㅤㅤV!C3ㅤ") == "SYN V!C3"
    assert display_name("ㅤPHXㅤDEZ”") == "PHX DEZ”"


def test_odd_spaces_and_private_use():
    # How the same players appear in ReplayInfo.
    assert display_name("RBL AMK") == "RBL AMK"
    assert display_name("BLU BIG TIFE") == "BLU BIG TIFE"
    assert display_name("SYNㅤㅤV!C3ㅤ") == "SYN V!C3"


def test_same_player_matches_across_files():
    assert search_name("SYNㅤㅤV!C3ㅤ") == search_name("SYNㅤㅤV!C3ㅤ")
    assert search_name("RBL AMK") == search_name("RBL AMK")


def test_stylised_letters_kept_for_display_but_folded_for_search():
    name = clean("AX.Ｋ11")
    assert name.raw == "AX.Ｋ11"
    assert name.display == "AX.Ｋ11"
    assert name.search == "ax.k11"


def test_empty():
    assert display_name("ㅤ") == ""
