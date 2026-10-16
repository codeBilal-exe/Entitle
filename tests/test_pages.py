"""UI smoke: key pages render with the gazette design system."""


def test_home_uses_masthead_and_ledger(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "masthead" in body
    assert "Living entitlements registry" in body
    assert "ledger" in body
    assert "Newsreader" in body or "Figtree" in body
    assert "Keep entitlements alive" in body


def test_login_and_curator_pages(api_client):
    assert api_client.get("/login").status_code == 200
    api_client.post(
        "/login",
        data={"email": "curator@demo.rightpath", "password": "demo1234"},
        follow_redirects=False,
    )
    curator = api_client.get("/curator")
    assert curator.status_code == 200
    assert "Curator desk" in curator.text
    assert "sheet" in curator.text
