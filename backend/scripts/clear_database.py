import os
import sys

from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres",
)

engine = create_engine(DATABASE_URL)


def main() -> None:
    tables = [
        "job_stages",
        "verification_results",
        "jobs",
        "document_chunks",
        "documents",
        "reference_chunks",
        "reference_documents",
    ]

    print("This will delete all rows from the known application tables.")
    print("Tables, schema, migrations, and the pgvector extension will be preserved.")

    confirmation = input("Type DELETE to continue: ")
    if confirmation != "DELETE":
        print("Cancelled.")
        return

    try:
        with engine.begin() as db:
            existing_tables = db.execute(
                text(
                    """
                    SELECT tablename
                    FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                      AND tablename = ANY(:table_names)
                    ORDER BY tablename
                    """
                ),
                {"table_names": tables},
            ).scalars().all()

            if not existing_tables:
                print("No known application tables exist.")
                return

            print("\nApplication tables found:")
            for table in existing_tables:
                columns = db.execute(
                    text(
                        """
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = :table_name
                        ORDER BY ordinal_position
                        """
                    ),
                    {"table_name": table},
                ).all()

                print(f"\n  {table}")
                for column_name, data_type, is_nullable in columns:
                    print(
                        f"    - {column_name}: {data_type}, "
                        f"nullable={is_nullable}"
                    )

            quoted_tables = ", ".join(
                f'public."{table.replace(chr(34), chr(34) * 2)}"'
                for table in existing_tables
            )
            db.execute(
                text(
                    f"TRUNCATE TABLE {quoted_tables} "
                    "RESTART IDENTITY CASCADE"
                )
            )

        print("Database records deleted successfully.")
        print("Cleared: " + ", ".join(existing_tables))
    except Exception as error:
        print(f"Database cleanup failed: {error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
