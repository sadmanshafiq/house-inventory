import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://inventory:inventory_pass_hpb@postgres:5432/inventory"
)
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/data/media"))
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10, open=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    pool.open()
    with pool.connection() as conn:
        conn.execute(SCHEMA_PATH.read_text())
    yield
    pool.close()


app = FastAPI(title="House Inventory", lifespan=lifespan)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def save_raw_upload(upload: UploadFile) -> str:
    ext = Path(upload.filename or "").suffix.lower() or ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = MEDIA_DIR / filename
    with dest.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return filename


@app.post("/api/locations")
def create_location(
    name: str = Form(...),
    parent_id: Optional[int] = Form(None),
    photo: Optional[UploadFile] = File(None),
):
    photo_filename = save_raw_upload(photo) if photo else None
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO locations (name, parent_id, photo_filename)
                VALUES (%s, %s, %s)
                RETURNING id, name, parent_id, photo_filename
                """,
                (name, parent_id, photo_filename),
            )
            return cur.fetchone()


@app.get("/api/locations/{location_id}/path")
def get_location_hierarchy(location_id: int):
    """Returns full breadcrumb path (e.g., Garage -> Metal Shelf -> Red Bin)"""
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH RECURSIVE loc_path AS (
                    SELECT id, name, parent_id, photo_filename, 1 AS depth
                    FROM locations WHERE id = %s
                    UNION ALL
                    SELECT l.id, l.name, l.parent_id, l.photo_filename, lp.depth + 1
                    FROM locations l
                    JOIN loc_path lp ON l.id = lp.parent_id
                )
                SELECT id, name, photo_filename FROM loc_path ORDER BY depth DESC;
                """,
                (location_id,),
            )
            return cur.fetchall()


@app.post("/api/items")
def create_item(
    name: str = Form(...),
    location_id: int = Form(...),
    description: str = Form(""),
    tags: str = Form(""),  # Comma-separated: "camping,winter"
    photo: Optional[UploadFile] = File(None),
):
    photo_filename = save_raw_upload(photo) if photo else None
    tag_list = list({t.strip().lower() for t in tags.split(",") if t.strip()})

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO items (name, description, location_id, tags, photo_filename)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, description, location_id, tags, photo_filename, updated_at
                """,
                (name, description, location_id, tag_list, photo_filename),
            )
            return cur.fetchone()


@app.get("/api/items")
def search_items(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    location_id: Optional[int] = None,
):
    query = """
        SELECT i.id, i.name, i.description, i.tags, i.photo_filename, i.updated_at,
               l.id AS location_id, l.name AS location_name
        FROM items i
        JOIN locations l ON i.location_id = l.id
        WHERE 1=1
    """
    params = []

    if q:
        # Prefix-matching tsquery so partial words match immediately
        query += " AND i.search_vector @@ websearch_to_tsquery('english', %s)"
        params.append(q)
    if tag:
        # Postgres array containment operator (@>) uses the GIN index
        query += " AND i.tags @> ARRAY[%s]::text[]"
        params.append(tag.lower())
    if location_id:
        query += " AND i.location_id = %s"
        params.append(location_id)

    query += " ORDER BY i.updated_at DESC"

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            for r in rows:
                r["photo_url"] = f"/media/{r['photo_filename']}" if r["photo_filename"] else None
            return rows