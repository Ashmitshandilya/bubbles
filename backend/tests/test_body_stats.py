import pytest
from body_stats import auto_save_body_stats, feet_inches, parse_height_cm


@pytest.mark.parametrize("text,cm", [
    ("my height is 6'1", 185.4),
    ("My height is 6'1\"", 185.4),
    ("I am 6 feet 1 inch tall", 185.4),
    ("i'm 185 cm", 185.0),
    ("my height: 170cm", 170.0),
    ("hi. I am 5'7 tall.", 170.2),
])
def test_parses_own_height(text, cm):
    assert parse_height_cm(text) == pytest.approx(cm, abs=0.1)


@pytest.mark.parametrize("text", [
    "what is a good height for a bed?", "my brother's height is 6'1", "I am 5 feet away from the door",
    "I am not 6'1", "if my height is 6'1 how much should I weigh?", "my height is 9'9", "I am 90 cm", "I am 6 feet from you",
])
def test_ignores_everything_else(text):
    assert parse_height_cm(text) is None


def test_feet_inches():
    assert feet_inches(185.4) == "6'1\""


class _Q:
    def __init__(self, db, table): self.db, self.table, self.row = db, table, None
    def update(self, row): self.row = row; return self
    def eq(self, *_a): return self
    def execute(self): self.db.writes.append((self.table, self.row)); return self


class _Db:
    def __init__(self): self.writes = []
    def table(self, name): return _Q(self, name)


@pytest.fixture(autouse=True)
def _consent_given(monkeypatch):
    import consent
    monkeypatch.setattr(consent, "is_granted", lambda db, uid, purpose: purpose == "health_memory_from_chat")


def test_nothing_is_saved_without_the_chat_memory_consent(monkeypatch):
    import consent
    monkeypatch.setattr(consent, "is_granted", lambda db, uid, purpose: False)
    db = _Db()
    assert auto_save_body_stats(db, "u1", "my height is 6'1", []) == []
    assert db.writes == []


def test_saves_height_to_profile_row(monkeypatch):
    import doc_store
    saved = {}
    monkeypatch.setattr(doc_store, "get", lambda *a, **k: {"birth_date": "1990-01-01"})
    monkeypatch.setattr(doc_store, "put", lambda db, uid, kind, key, body: saved.update(body))
    db = _Db()
    notes = auto_save_body_stats(db, "u1", "my height is 6'1", [])
    assert notes == ["Updated your height to 185.4 cm (6'1\")."]
    assert db.writes[0][0] == "profiles" and db.writes[0][1]["height_cm"] == 185.4
    assert saved == {"birth_date": "1990-01-01", "height_cm": 185.4}


def test_nothing_stated_nothing_saved():
    db = _Db()
    assert auto_save_body_stats(db, "u1", "I slept badly", []) == []
    assert db.writes == []

