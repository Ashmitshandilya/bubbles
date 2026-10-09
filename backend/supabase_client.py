import os

import env_compat  # noqa: F401  (loads .env and maps legacy COCO_* names to BUBBLES_*)
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Backend credentials are intentionally server-only.


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError("SUPABASE_SECRET_KEY is missing from .env")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)