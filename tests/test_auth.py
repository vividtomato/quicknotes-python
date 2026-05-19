def test_home_redirects_anonymous(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_register_success(client):
    r = client.post(
        "/register",
        data={"username": "alice", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200


def test_register_short_username(client):
    r = client.post(
        "/register",
        data={"username": "a", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_register_short_password(client):
    r = client.post(
        "/register",
        data={"username": "alice", "password": "ab"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_register_duplicate(client):
    data = {"username": "bob", "password": "secret"}
    client.post("/register", data=data)
    r = client.post("/register", data=data, follow_redirects=False)
    assert r.status_code == 400


def test_login_success(client, user):
    r = client.post(
        "/login",
        data={"username": user.username, "password": "pass1234"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_login_wrong_password(client, user):
    r = client.post(
        "/login",
        data={"username": user.username, "password": "wrong"},
        follow_redirects=False,
    )
    assert r.status_code == 401


def test_logout(auth_client):
    r = auth_client.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    r = auth_client.get("/", follow_redirects=False)
    assert r.status_code == 303
