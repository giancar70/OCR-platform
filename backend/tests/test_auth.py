import pytest


async def test_register_success(client):
    r = await client.post("/v1/auth/register", json={"email": "new@example.com", "password": "password123"})
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "new@example.com"
    assert "id" in data


async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    await client.post("/v1/auth/register", json=payload)
    r = await client.post("/v1/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_invalid_email(client):
    r = await client.post("/v1/auth/register", json={"email": "notanemail", "password": "password123"})
    assert r.status_code == 422


async def test_register_short_password(client):
    r = await client.post("/v1/auth/register", json={"email": "user@example.com", "password": "short"})
    assert r.status_code == 422


async def test_login_success(client, registered_user):
    r = await client.post("/v1/auth/login", json={"email": "test@example.com", "password": "password123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client, registered_user):
    r = await client.post("/v1/auth/login", json={"email": "test@example.com", "password": "wrongpassword"})
    assert r.status_code == 401


async def test_login_unknown_email(client):
    r = await client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert r.status_code == 401


async def test_email_normalized_to_lowercase(client):
    await client.post("/v1/auth/register", json={"email": "User@Example.COM", "password": "password123"})
    r = await client.post("/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert r.status_code == 200
