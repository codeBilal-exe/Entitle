"""UI smoke: empty sign-in, roles, and the citizen home."""


def _login(client, email="admin@rightpath.local", password="test-admin-pass"):
    return client.post(
        "/login",
        data={"email": email, "password": password, "next_path": "/"},
        follow_redirects=False,
    )


def test_root_requires_login(api_client):
    response = api_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_login_is_an_empty_form(api_client):
    response = api_client.get("/login")
    assert response.status_code == 200
    body = response.text
    assert "Sign in" in body
    assert "Sign up" in body
    assert "A person approves a rule change." in body
    assert "A person releases bad news." in body
    assert "approves the exact packet" in body
    assert 'type="password"' in body
    assert 'value="demo1234"' not in body
    assert "Amina" not in body
    assert "Demo accounts" not in body
    assert "Citizen view" not in body
    assert "Staff view" not in body


def test_signup_lands_on_an_empty_profile(api_client):
    created = api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/profile"

    from app.db import SessionLocal
    from app.models import Profile, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "hina@example.com").one()
        assert user.role == "citizen"
        assert db.query(Profile).filter(Profile.user_id == user.id).first() is None
    finally:
        db.close()

    page = api_client.get("/profile")
    assert page.status_code == 200
    assert "No profile yet" in page.text
    assert 'name="age"' in page.text
    assert 'required value=""' in page.text


def test_citizen_home_after_profile(api_client):
    api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    saved = api_client.post(
        "/profile",
        data={"age": "22", "education_level": "secondary"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    home = api_client.get("/")
    assert home.status_code == 200
    assert "masthead" in home.text
    assert "What matches you" in home.text
    assert "HEC scholarships and grants" in home.text
    assert "Citizen view" not in home.text
    assert "Demo sample" not in home.text


def test_staff_desk_and_curator(api_client):
    _login(api_client, "staff.one@rightpath.local", "test-staff-1")
    home = api_client.get("/")
    assert home.status_code == 200
    assert "Staff desk" in home.text
    curator = api_client.get("/curator")
    assert curator.status_code == 200
    assert "Watched sources" in curator.text
    assert "Check sources now" in curator.text
    assert "Turn sending" not in curator.text
    assert api_client.get("/timeline").status_code == 403


def test_admin_sees_sending_switch_and_activity(api_client):
    _login(api_client)
    curator = api_client.get("/curator")
    assert "Turn sending" in curator.text
    assert api_client.get("/timeline").status_code == 200
