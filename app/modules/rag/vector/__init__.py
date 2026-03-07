from app.modules.rag.vector.lancedb import LanceDBDriver


class VectorDBService:
    _instances: dict[str, LanceDBDriver] = {}

    def get_or_create(self, kb_id: int, dimension: int) -> LanceDBDriver:
        key = f"kb_{kb_id}"
        if key not in self._instances:
            db_path = f"database/lancedb/kb_{kb_id}"
            driver = LanceDBDriver(db_path)
            driver.ensure_table(key, dimension)
            self._instances[key] = driver
        return self._instances[key]

    def clear_cache(self, kb_id: int = None):
        if kb_id:
            self._instances.pop(f"kb_{kb_id}", None)
        else:
            self._instances.clear()


vector_db_service = VectorDBService()
