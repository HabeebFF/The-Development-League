from datetime import datetime

from apps.ingest.parsers import match_id, safe_zone

BOM_CRLF = "﻿-101,125\r\n".encode()


def test_match_id_from_filename():
    result = match_id.parse("MatchId_2103980121133858816_2026-09-26-23-48-55.log", "﻿".encode())
    assert result.data.match_id == 2103980121133858816
    assert result.data.started_at == datetime(2026, 9, 26, 23, 48, 55)
    assert result.warning_count == 0


def test_match_id_bad_name():
    result = match_id.parse("whatever.log")
    assert result.data is None
    assert result.warnings[0].code == "bad_filename"


def test_safe_zone_sample_line():
    result = safe_zone.parse("SafeZone_2103980121133858816_2026-09-26-23-52-22.log", BOM_CRLF)
    zone = result.data
    assert (zone.x, zone.z) == (-101.0, 125.0)
    assert zone.match_id == 2103980121133858816
    assert result.warning_count == 0


def test_safe_zone_decimals_and_spaces():
    result = safe_zone.parse("SafeZone_1_2026-09-26-23-52-22.log", " -87.5 , 12.25 ")
    assert (result.data.x, result.data.z) == (-87.5, 12.25)


def test_safe_zone_garbage_never_raises():
    result = safe_zone.parse("SafeZone_1_2026-09-26-23-52-22.log", "hello\n")
    assert result.data is None
    assert result.warnings[0].code == "unparsed_line"
    assert safe_zone.parse("SafeZone_1_2026-09-26-23-52-22.log", "").warnings[0].code == "empty"


def test_safe_zones_ordered_by_timestamp():
    later = safe_zone.parse("SafeZone_1_2026-09-26-23-59-00.log", "1,1").data
    earlier = safe_zone.parse("SafeZone_1_2026-09-26-23-50-00.log", "2,2").data
    assert safe_zone.order_safe_zones([later, earlier]) == [earlier, later]
