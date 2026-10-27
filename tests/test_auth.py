from tests.conftest import login


def test_login_success_jefe(client):
    r = login(client, "christian")
    assert r.status_code == 200
    assert b"Panel del taller" in r.data


def test_login_wrong_password(client):
    r = login(client, "christian", "mala")
    assert b"incorrectos" in r.data


def test_employee_cannot_access_jefe_area(client):
    login(client, "humberto")
    r = client.get("/jefe/empleados")
    assert r.status_code == 403


def test_logout(client):
    login(client, "christian")
    r = client.post("/logout", follow_redirects=True)
    assert b"Ingresar" in r.data or b"Usuario" in r.data
