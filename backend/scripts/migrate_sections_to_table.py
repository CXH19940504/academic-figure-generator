#!/usr/bin/env python3
"""Migration script: Migrate Document.sections JSON to Section table.

This script reads the sections JSON from the documents table and creates
corresponding Section records in the sections table.

Usage:
    python -m scripts.migrate_sections_to_table

"""

import json
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.base import Base
from app.models.document import Section


def migrate_sections():
    """Migrate Document.sections JSON to Section table."""
    settings = get_settings()

    # Create engine with synchronous connection for migration
    db_url = settings.DATABASE_URL
    if "sqlite+aiosqlite" in db_url:
        db_url = db_url.replace("sqlite+aiosqlite", "sqlite")
    elif "mysql+asyncmy" in db_url:
        db_url = db_url.replace("mysql+asyncmy", "mysql+pymysql")
    elif "mysql+aiomysql" in db_url:
        db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")
    engine = create_engine(db_url)

    # Create sections table if not exists
    Base.metadata.create_all(engine, tables=[Section.__table__])

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    with Session(engine) as session:
        # Check if the old 'sections' column still exists
        check_sql = text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'documents' AND column_name = 'sections'"
        )
        try:
            col_exists = session.execute(check_sql).scalar()
        except Exception:
            col_exists = 0

        if not col_exists:
            print("The 'sections' column does not exist in the documents table.")
            print("Migration may have already been completed or column was already dropped.")
        else:
            # Read documents with non-null sections using raw SQL
            raw_sql = text(
                "SELECT id, sections FROM documents WHERE sections IS NOT NULL"
            )
            rows = session.execute(raw_sql).fetchall()

            print(f"Found {len(rows)} documents with sections to migrate...")

            for row in rows:
                doc_id = row[0]
                sections_raw = row[1]

                if not sections_raw:
                    skipped_count += 1
                    continue

                # Handle both list (JSON) and string formats
                if isinstance(sections_raw, str):
                    try:
                        sections_data = json.loads(sections_raw)
                    except json.JSONDecodeError:
                        print(f"  Warning: Document {doc_id} has invalid JSON in sections, skipping...")
                        error_count += 1
                        continue
                elif isinstance(sections_raw, list):
                    sections_data = sections_raw
                else:
                    print(f"  Warning: Document {doc_id} sections is unexpected type {type(sections_raw)}, skipping...")
                    error_count += 1
                    continue

                if not isinstance(sections_data, list):
                    print(f"  Warning: Document {doc_id} sections is not a list, skipping...")
                    error_count += 1
                    continue

                for idx, section_data in enumerate(sections_data):
                    if not isinstance(section_data, dict):
                        continue

                    try:
                        section = Section(
                            document_id=doc_id,
                            title=section_data.get("title", f"Section {idx + 1}"),
                            level=section_data.get("level", 1),
                            content=section_data.get("content", ""),
                            page_start=section_data.get("page_start"),
                            page_end=section_data.get("page_end"),
                            order_index=idx,
                        )
                        session.add(section)
                        migrated_count += 1
                    except Exception as e:
                        print(f"  Error creating section for document {doc_id}: {e}")
                        error_count += 1

                # Clear the JSON sections field after migration
                update_sql = text(
                    "UPDATE documents SET sections = NULL WHERE id = :doc_id"
                )
                session.execute(update_sql, {"doc_id": doc_id})

            session.commit()

        print(f"\nMigration complete!")
        print(f"  Sections migrated: {migrated_count}")
        print(f"  Documents skipped (no sections): {skipped_count}")
        print(f"  Errors: {error_count}")

        # Verify migration
        count_sql = text("SELECT COUNT(*) FROM sections")
        section_count = session.execute(count_sql).scalar()
        print(f"\nVerification: {section_count} total sections in sections table")


if __name__ == "__main__":
    migrate_sections()
