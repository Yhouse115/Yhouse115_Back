from app.repositories.transaction_repository import normalize_apartment_name


def test_normalize_mokdong_new_town_apartment_name():
    assert normalize_apartment_name("목동신시가지1") == "신시가지아파트1단지"
    assert normalize_apartment_name("목동신시가지아파트 1단지") == "신시가지아파트1단지"


def test_normalize_apartment_name_keeps_other_complexes():
    assert normalize_apartment_name("현대하이페리온") == "현대하이페리온"
    assert normalize_apartment_name("312-5빌라") == "312-5빌라"
    assert normalize_apartment_name("삼성빌라3") == "삼성빌라3"
    assert normalize_apartment_name("목동센트럴2") == "목동센트럴2"
    assert normalize_apartment_name(None) is None
