from app.config import get_settings
settings = get_settings()
print(f"Storage path: {settings.notebooklm_storage_path}")
