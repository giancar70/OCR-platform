import pytest

PNG = ("test.png", b"fake-image-data", "image/png")
PDF = ("test.pdf", b"fake-pdf-data", "application/pdf")


async def _upload(client, headers, file=PNG):
    return await client.post("/v1/documents/", headers=headers, files={"file": file})


# ── list ───────────────────────────────────────────────────────────────────────

async def test_list_empty(client, auth_headers):
    r = await client.get("/v1/documents/", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


async def test_list_requires_auth(client):
    r = await client.get("/v1/documents/")
    assert r.status_code == 403


# ── upload ─────────────────────────────────────────────────────────────────────

async def test_upload_png(client, auth_headers):
    r = await _upload(client, auth_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "queued"
    assert data["original_filename"] == "test.png"
    assert data["mime_type"] == "image/png"


async def test_upload_pdf(client, auth_headers):
    r = await _upload(client, auth_headers, file=PDF)
    assert r.status_code == 201
    assert r.json()["mime_type"] == "application/pdf"


async def test_upload_invalid_type(client, auth_headers):
    r = await client.post(
        "/v1/documents/", headers=auth_headers,
        files={"file": ("doc.txt", b"text", "text/plain")},
    )
    assert r.status_code == 415


async def test_upload_too_large(client, auth_headers):
    big = b"x" * (10 * 1024 * 1024 + 1)
    r = await client.post(
        "/v1/documents/", headers=auth_headers,
        files={"file": ("big.png", big, "image/png")},
    )
    assert r.status_code == 413


async def test_upload_appears_in_list(client, auth_headers):
    await _upload(client, auth_headers)
    r = await client.get("/v1/documents/", headers=auth_headers)
    assert len(r.json()) == 1


# ── get ────────────────────────────────────────────────────────────────────────

async def test_get_document(client, auth_headers):
    doc_id = (await _upload(client, auth_headers)).json()["id"]
    r = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == doc_id


async def test_get_document_not_found(client, auth_headers):
    r = await client.get("/v1/documents/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert r.status_code == 404


async def test_get_document_other_user(client, auth_headers):
    doc_id = (await _upload(client, auth_headers)).json()["id"]

    await client.post("/v1/auth/register", json={"email": "other@example.com", "password": "password123"})
    login = await client.post("/v1/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.get(f"/v1/documents/{doc_id}", headers=other_headers)
    assert r.status_code == 404


# ── delete ─────────────────────────────────────────────────────────────────────

async def test_delete_document(client, auth_headers):
    doc_id = (await _upload(client, auth_headers)).json()["id"]

    r = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers)
    assert r.status_code == 204


async def test_deleted_document_not_in_list(client, auth_headers):
    doc_id = (await _upload(client, auth_headers)).json()["id"]
    await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers)

    ids = [d["id"] for d in (await client.get("/v1/documents/", headers=auth_headers)).json()]
    assert doc_id not in ids


async def test_deleted_document_not_accessible(client, auth_headers):
    doc_id = (await _upload(client, auth_headers)).json()["id"]
    await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers)

    r = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers)
    assert r.status_code == 404

