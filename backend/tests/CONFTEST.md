# conftest.py — Detalle

Archivo de configuración compartida para todos los tests. pytest lo carga automáticamente antes de ejecutar cualquier test.

---

## URLs de base de datos

```python
_TEST_ASYNC_URL = settings.DATABASE_URL.replace("/ocr_db", "/ocr_test_db")
_TEST_SYNC_URL  = ...replace("asyncpg", "psycopg2")
_ADMIN_SYNC_URL = ...replace("/ocr_test_db", "/postgres")
```

Se derivan tres URLs a partir del `DATABASE_URL` definido en `backend/.env`:

| Variable | Driver | Propósito |
|----------|--------|-----------|
| `_TEST_ASYNC_URL` | asyncpg | Sesión async que usa FastAPI en los tests |
| `_TEST_SYNC_URL` | psycopg2 | Crear/borrar tablas y limpiar datos entre tests |
| `_ADMIN_SYNC_URL` | psycopg2 | Crear/borrar la base de datos `ocr_test_db` (requiere conectarse a `postgres`) |

---

## `setup_test_database` — una vez por sesión

```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
```

- `scope="session"` → se ejecuta una sola vez para toda la corrida de tests
- `autouse=True` → se activa automáticamente sin que ningún test lo pida

**Antes de los tests:**
1. Se conecta a la base de datos `postgres` (admin)
2. Elimina `ocr_test_db` si existe (`DROP DATABASE IF EXISTS`)
3. Crea `ocr_test_db` limpia
4. Crea todas las tablas (`users`, `documents`, `log`)

**Después de todos los tests (después del `yield`):**
1. Elimina todas las tablas
2. Elimina `ocr_test_db`

---

## `clean_tables` — después de cada test

```python
@pytest.fixture(autouse=True)
def clean_tables():
    yield
    # borra todas las filas de todas las tablas
```

- Sin `scope` → se ejecuta una vez por cada test (scope por defecto es `function`)
- `autouse=True` → se activa automáticamente

Después de cada test borra todas las filas en orden inverso de dependencia (hijos antes que padres) para respetar las foreign keys. Esto garantiza que los datos de un test no afecten al siguiente.

---

## `db` — sesión de base de datos async

```python
@pytest_asyncio.fixture
async def db():
    async with _TestSession() as session:
        yield session
```

Abre una sesión SQLAlchemy async apuntando a `ocr_test_db`. Cada test que declare `db` como parámetro recibe su propia sesión.

---

## `client` — cliente HTTP de tests

```python
@pytest_asyncio.fixture
async def client(db):
```

El fixture más importante. Hace cuatro cosas:

### 1. Reemplaza la dependencia de base de datos

```python
app.dependency_overrides[get_db] = override_get_db
```

Hace que FastAPI use la sesión de `ocr_test_db` en lugar de la base de datos real.

### 2. Mockea todos los servicios externos

Los tests no necesitan MinIO, Celery ni Redis corriendo:

| Mock | Servicio reemplazado |
|------|----------------------|
| `upload_file` | Subida de archivos a MinIO |
| `delete_file` | Eliminación de archivos en MinIO |
| `ensure_bucket_exists` | Verificación del bucket MinIO |
| `process_document.delay` | Despacho de tarea Celery |
| `publish_async` | Publicación en Redis pub/sub |
| `celery_app.control.revoke` | Revocación de tarea Celery |

### 3. Simula un task ID de Celery

```python
mock_delay.return_value = MagicMock(id="test-celery-task-id")
```

La subida de documentos guarda el `task_id` en la base de datos. Sin esto el flujo de upload fallaría.

### 4. Crea el cliente HTTP

```python
AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
```

Llama directamente a la aplicación FastAPI en memoria — sin red real, sin puerto, sin servidor corriendo.

---

## `registered_user` — crea un usuario antes del test

```python
@pytest_asyncio.fixture
async def registered_user(client):
    r = await client.post("/v1/auth/register", ...)
    return r.json()
```

Registra un usuario vía la API antes de que el test comience. Cualquier test que lo declare como parámetro ya tiene un usuario disponible.

---

## `auth_headers` — headers de autenticación listos

```python
@pytest_asyncio.fixture
async def auth_headers(client, registered_user):
    r = await client.post("/v1/auth/login", ...)
    return {"Authorization": f"Bearer {token}"}
```

Hace login y devuelve el header `Authorization` listo para usar en cualquier request. Cualquier test que declare `auth_headers` como parámetro tiene un usuario autenticado automáticamente.

**Ejemplo de uso en un test:**

```python
async def test_list_empty(client, auth_headers):
    r = await client.get("/v1/documents/", headers=auth_headers)
    assert r.status_code == 200
```

---

## Flujo completo de un test

```
pytest inicia
    │
    ├─ setup_test_database()  →  crea ocr_test_db y tablas
    │
    │  Por cada test:
    │  ├─ db()           →  abre sesión async
    │  ├─ client()       →  override DB + mocks + cliente HTTP
    │  ├─ registered_user() →  POST /v1/auth/register
    │  ├─ auth_headers() →  POST /v1/auth/login → Bearer token
    │  │
    │  ├─ [se ejecuta el test]
    │  │
    │  └─ clean_tables() →  borra todas las filas
    │
    └─ setup_test_database() teardown  →  elimina ocr_test_db
```
