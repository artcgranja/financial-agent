from __future__ import annotations
import json
import datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import (
    Column, String, DateTime, Text, create_engine, select, Index, UniqueConstraint
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()

def _ns_to_str(namespace: Tuple[str, ...] | Iterable[str]) -> str:
    return "/".join(list(namespace))

class MemoryRow(Base):
    __tablename__ = "memories"
    # namespace e key definem a identidade de uma memória
    namespace = Column(String(512), primary_key=True)
    key = Column(String(256), primary_key=True)
    value = Column(SQLITE_JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: dt.datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=lambda: dt.datetime.utcnow(), onupdate=lambda: dt.datetime.utcnow())

    __table_args__ = (
        UniqueConstraint("namespace", "key", name="uq_memories_ns_key"),
        Index("ix_memories_ns", "namespace"),
    )

class PersistentSQLiteStore:
    """
    Store persistente e simples para long-term memory.
    API mínima inspirada no BaseStore do LangGraph:
      - put(namespace, key, value)
      - get(namespace, key) -> Item-like
      - search(namespace, query=None, filter=None, limit=50) -> list[Item-like]
    """
    def __init__(self, path: str = "store.db"):
        self.engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self.engine)

    # ----- helpers -----
    def _to_item(self, row: MemoryRow) -> Dict[str, Any]:
        return {
            "value": row.value,
            "key": row.key,
            "namespace": row.namespace.split("/"),
            "created_at": row.created_at.isoformat() + "Z",
            "updated_at": row.updated_at.isoformat() + "Z",
        }

    # ----- public API -----
    def put(self, namespace: Tuple[str, ...] | Iterable[str], key: str, value: Dict[str, Any]) -> None:
        ns = _ns_to_str(tuple(namespace))
        with Session(self.engine) as s:
            existing = s.get(MemoryRow, {"namespace": ns, "key": key})
            if existing:
                existing.value = value
            else:
                s.add(MemoryRow(namespace=ns, key=key, value=value))
            s.commit()

    def get(self, namespace: Tuple[str, ...] | Iterable[str], key: str) -> Optional[Dict[str, Any]]:
        ns = _ns_to_str(tuple(namespace))
        with Session(self.engine) as s:
            row = s.get(MemoryRow, {"namespace": ns, "key": key})
            return self._to_item(row) if row else None

    def search(
        self,
        namespace: Tuple[str, ...] | Iterable[str],
        query: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Busca simples:
          - se 'filter' vier, exige igualdade exata nos campos top-level do JSON.
          - se 'query' vier, faz LIKE no JSON serializado (limitado, mas útil p/ MVP).
        """
        ns = _ns_to_str(tuple(namespace))
        with Session(self.engine) as s:
            stmt = select(MemoryRow).where(MemoryRow.namespace == ns)

            # Filtro exato em campos top-level do JSON
            if filter:
                # Para SQLite JSON, a maneira simples é filtrar via LIKE no JSON serializado
                # (para MVP; em prod use JSON1/PRAGMA ou um DB com JSON melhor)
                for k, v in filter.items():
                    like_piece = f'"{k}": {json.dumps(v)}'
                    stmt = stmt.where(MemoryRow.value.like(f"%{like_piece}%"))

            # Query textual simples
            if query:
                stmt = stmt.where(MemoryRow.value.cast(Text).like(f"%{query}%"))

            stmt = stmt.limit(limit)
            rows = s.execute(stmt).scalars().all()
            return [self._to_item(r) for r in rows]