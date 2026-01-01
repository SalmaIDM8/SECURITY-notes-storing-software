from app.utils import auth_hash


def test_hash_and_verify():
    pw = "correct horse battery staple"
    h = auth_hash.hash_password(pw)
    assert isinstance(h, str) and len(h) > 0
    assert auth_hash.verify_password(pw, h) is True


def test_wrong_password_fails():
    pw = "s3cret"
    h = auth_hash.hash_password(pw)
    assert auth_hash.verify_password("wrong", h) is False


def test_hashes_differ_for_same_password():
    pw = "repeatable"
    h1 = auth_hash.hash_password(pw)
    h2 = auth_hash.hash_password(pw)
    # bcrypt should salt so two hashes differ
    assert h1 != h2
    assert auth_hash.verify_password(pw, h1)
    assert auth_hash.verify_password(pw, h2)
