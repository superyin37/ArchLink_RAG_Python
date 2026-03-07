import logging
import pyarrow as pa

logger = logging.getLogger(__name__)


class LanceDBDriver:
    def __init__(self, db_path: str):
        import lancedb
        self.db = lancedb.connect(db_path)

    def ensure_table(self, table_name: str, dimension: int):
        if table_name not in self.db.table_names():
            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), dimension)),
                    pa.field("document", pa.string()),
                    pa.field("doc_id", pa.int64()),
                    pa.field("chunk_id", pa.int64()),
                    pa.field("node_id", pa.string()),
                    pa.field("parent_id", pa.string()),
                    pa.field("level", pa.int32()),
                    pa.field("path", pa.string()),
                    pa.field("heading", pa.string()),
                    pa.field("type", pa.string()),
                ]
            )
            self.db.create_table(table_name, schema=schema)
            logger.info(f"Created LanceDB table: {table_name}")

    def add_vectors(self, table_name: str, records: list[dict]):
        table = self.db.open_table(table_name)
        table.add(records)

    def search(
        self,
        table_name: str,
        vector: list[float],
        top_k: int = 5,
        where: str = None,
    ) -> list[dict]:
        table = self.db.open_table(table_name)
        query = table.search(vector).limit(top_k).metric("cosine")
        if where:
            query = query.where(where)
        return query.to_list()

    def delete(self, table_name: str, where: str):
        if table_name in self.db.table_names():
            table = self.db.open_table(table_name)
            table.delete(where)

    def table_exists(self, table_name: str) -> bool:
        return table_name in self.db.table_names()

    def count(self, table_name: str) -> int:
        if not self.table_exists(table_name):
            return 0
        table = self.db.open_table(table_name)
        return table.count_rows()
