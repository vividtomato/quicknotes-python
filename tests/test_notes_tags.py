from app.models import Note, Tag


def test_create_note(auth_client, db, user):
    auth_client.post("/notes", data={"content": "hello"})
    notes = db.query(Note).filter(Note.user_id == user.id).all()
    assert len(notes) == 1
    assert notes[0].content == "hello"
    assert notes[0].tag_id is None


def test_create_note_empty_ignored(auth_client, db, user):
    auth_client.post("/notes", data={"content": "   "})
    assert db.query(Note).filter(Note.user_id == user.id).count() == 0


def test_create_note_with_new_tag(auth_client, db, user):
    auth_client.post("/notes", data={"content": "task", "new_tag": "work"})
    note = db.query(Note).filter(Note.user_id == user.id).one()
    tag = db.query(Tag).filter(Tag.user_id == user.id).one()
    assert note.tag_id == tag.id
    assert tag.name == "work"


def test_create_tag(auth_client, db, user):
    auth_client.post("/tags", data={"name": "ideas"})
    tags = db.query(Tag).filter(Tag.user_id == user.id).all()
    assert len(tags) == 1
    assert tags[0].name == "ideas"


def test_create_tag_duplicate_ignored(auth_client, db, user):
    auth_client.post("/tags", data={"name": "ideas"})
    auth_client.post("/tags", data={"name": "ideas"})
    assert db.query(Tag).filter(Tag.user_id == user.id).count() == 1


def test_delete_note(auth_client, db, user):
    auth_client.post("/notes", data={"content": "gone"})
    note_id = db.query(Note).filter(Note.user_id == user.id).one().id
    auth_client.post(f"/notes/{note_id}/delete")
    assert db.query(Note).filter(Note.user_id == user.id).count() == 0


def test_delete_tag(auth_client, db, user):
    auth_client.post("/tags", data={"name": "tmp"})
    tag_id = db.query(Tag).filter(Tag.user_id == user.id).one().id
    auth_client.post(f"/tags/{tag_id}/delete")
    assert db.query(Tag).filter(Tag.user_id == user.id).count() == 0


def test_filter_by_tag(auth_client, db, user):
    auth_client.post("/tags", data={"name": "a"})
    auth_client.post("/tags", data={"name": "b"})
    tag_a = db.query(Tag).filter(Tag.name == "a", Tag.user_id == user.id).one()
    tag_b = db.query(Tag).filter(Tag.name == "b", Tag.user_id == user.id).one()
    auth_client.post("/notes", data={"content": "only a", "tag_id": str(tag_a.id)})
    auth_client.post("/notes", data={"content": "only b", "tag_id": str(tag_b.id)})
    r = auth_client.get(f"/?tag={tag_a.id}")
    assert r.status_code == 200
    assert "only a" in r.text
    assert "only b" not in r.text


def test_notes_isolated_between_users(client, db, user, other_user):
    client.post(
        "/login",
        data={"username": user.username, "password": "pass1234"},
    )
    client.post("/notes", data={"content": "mine"})
    client.post("/logout")
    client.post(
        "/login",
        data={"username": other_user.username, "password": "pass5678"},
    )
    r = client.get("/")
    assert "mine" not in r.text
    assert db.query(Note).filter(Note.user_id == other_user.id).count() == 0


def test_create_note_requires_login(client):
    r = client.post("/notes", data={"content": "x"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
