from sqlalchemy import create_engine, text


# ============================================================
# DATABASE CONNECTION
# ============================================================

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"

engine = create_engine(DATABASE_URL)


def main():

    print("=" * 100)
    print("POSTGRESQL + PGVECTOR DATA")
    print("=" * 100)

    try:

        with engine.connect() as db:

            # ====================================================
            # 1. PostgreSQL
            # ====================================================

            print("\n[1] POSTGRESQL")

            result = db.execute(
                text("SELECT version();")
            )

            print(result.scalar())


            # ====================================================
            # 2. pgvector
            # ====================================================

            print("\n[2] PGVECTOR")

            result = db.execute(
                text("""
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname = 'vector';
                """)
            )

            vector = result.fetchone()

            if vector:
                print("Status  : INSTALLED")
                print("Version :", vector[1])
            else:
                print("Status  : NOT INSTALLED")


            # ====================================================
            # 3. Tables
            # ====================================================

            print("\n[3] TABLES")

            result = db.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
            )

            tables = [row[0] for row in result.fetchall()]

            for table in tables:
                print(f"  {table}")


            # ====================================================
            # 4. Row counts
            # ====================================================

            print("\n[4] ROW COUNTS")

            for table in tables:

                result = db.execute(
                    text(
                        f'SELECT COUNT(*) FROM public."{table}"'
                    )
                )

                count = result.scalar()

                print(
                    f"  {table}: {count} rows"
                )


            # ====================================================
            # 5. Show data from every table
            # ====================================================

            print("\n[5] DATA")

            for table in tables:

                print("\n")
                print("=" * 100)
                print(f"TABLE: {table}")
                print("=" * 100)

                # Get columns
                result = db.execute(
                    text("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = :table
                        ORDER BY ordinal_position;
                    """),
                    {"table": table}
                )

                columns = [
                    row[0]
                    for row in result.fetchall()
                ]

                if not columns:
                    continue

                column_sql = ", ".join(
                    f'"{column}"'
                    for column in columns
                )

                # Get rows
                result = db.execute(
                    text(
                        f"""
                        SELECT {column_sql}
                        FROM public."{table}"
                        LIMIT 20;
                        """
                    )
                )

                rows = result.fetchall()

                if not rows:
                    print("NO DATA")
                    continue


                # ==================================================
                # Display rows
                # ==================================================

                for row_number, row in enumerate(
                    rows,
                    start=1
                ):

                    print("\n" + "-" * 100)
                    print(f"ROW {row_number}")
                    print("-" * 100)

                    for column, value in zip(
                        columns,
                        row
                    ):

                        # ------------------------------------------
                        # Vector / embedding
                        # ------------------------------------------

                        if column.lower() in (
                            "embedding",
                            "vector",
                        ):

                            if value is None:

                                print(
                                    f"{column}: NULL"
                                )

                            else:

                                print(
                                    f"{column}: VECTOR EXISTS"
                                )

                                # Try to show dimension
                                try:
                                    result = db.execute(
                                        text(
                                            f"""
                                            SELECT vector_dims(
                                                "{column}"
                                            )
                                            FROM public."{table}"
                                            LIMIT 1;
                                            """
                                        )
                                    )

                                    dimension = result.scalar()

                                    print(
                                        f"{column} dimension: "
                                        f"{dimension}"
                                    )

                                except Exception:
                                    pass


                        # ------------------------------------------
                        # Chunk/content fields
                        # ------------------------------------------

                        elif column.lower() in (
                            "content",
                            "chunk",
                            "chunk_text",
                            "text",
                            "content_text",
                        ):

                            print(
                                f"\n{column}:"
                            )

                            print(value)


                        # ------------------------------------------
                        # Everything else
                        # ------------------------------------------

                        else:

                            print(
                                f"{column}: {value}"
                            )


            # ====================================================
            # 6. Vector columns
            # ====================================================

            print("\n")
            print("=" * 100)
            print("[6] PGVECTOR COLUMNS")
            print("=" * 100)

            result = db.execute(
                text("""
                    SELECT
                        table_name,
                        column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND udt_name = 'vector'
                    ORDER BY table_name;
                """)
            )

            vector_columns = result.fetchall()

            if not vector_columns:

                print("No vector columns found.")

            else:

                for table, column in vector_columns:

                    print(
                        f"\nTable  : {table}"
                    )

                    print(
                        f"Column : {column}"
                    )

                    # Count vectors
                    result = db.execute(
                        text(
                            f"""
                            SELECT COUNT(*)
                            FROM public."{table}"
                            WHERE "{column}" IS NOT NULL;
                            """
                        )
                    )

                    count = result.scalar()

                    print(
                        f"Vectors stored: {count}"
                    )


            # ====================================================
            # DONE
            # ====================================================

            print("\n")
            print("=" * 100)
            print("DONE")
            print("=" * 100)


    except Exception as e:

        print("\n")
        print("=" * 100)
        print("DATABASE CONNECTION ERROR")
        print("=" * 100)

        print(e)


if __name__ == "__main__":
    main()