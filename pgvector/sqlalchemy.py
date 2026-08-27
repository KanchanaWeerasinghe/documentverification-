from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """SQLAlchemy type for PostgreSQL pgvector columns."""

    cache_ok = True

    def __init__(self, dim=None):
        self.dim = dim

    def get_col_spec(self, **kwargs):
        return f"VECTOR({self.dim})" if self.dim is not None else "VECTOR"

    def __repr__(self):
        return f"Vector({self.dim})"
