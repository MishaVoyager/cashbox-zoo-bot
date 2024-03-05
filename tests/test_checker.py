import pytest

from helpers import checker


@pytest.mark.parametrize("email", ["mnoskov@skbkontur.ru", "a.ivanov@skbkontur.ru"])
def test_is_kontur_email(email):
    assert checker.is_kontur_email(email).string == email


@pytest.mark.parametrize("email", ["mnoskov@skontur.ru", "nnn@gmail.com"])
def test_is_kontur_email_negative_cases(email):
    assert checker.is_kontur_email(email) is None
