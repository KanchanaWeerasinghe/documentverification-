from backend.app.domain.reference_ingestion_service import ReferenceIngestionService
from pathlib import Path
import sys



def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    service = ReferenceIngestionService()

    references_dir = Path(__file__).resolve().parents[2] / "backend" / "data" / "references"
    reference_files = sorted(references_dir.glob("*.docx"))
    if not reference_files:
        raise FileNotFoundError(f"No DOCX reference file found in {references_dir}")
    file_path = str(reference_files[0])

    print("=" * 80)
    print("TESTING REFERENCE DOCUMENT INGESTION")
    print("=" * 80)

    # Step 1: Parse document
    parsed = service.parse_document(file_path)

    print("\nTOTAL PARAGRAPHS:", len(parsed["paragraphs"]))

    # Step 2: Detect monographs
    monographs = service.detect_structure(parsed)

    print("TOTAL MONOGRAPHS:", len(monographs))

    # Step 3: Chunk each monograph
    total_chunks = 0

    for monograph in monographs:
        print("\n" + "=" * 80)
        print("MONOGRAPH:", monograph["title"])

        chunks = service.chunk_monograph(monograph)

        print("CHUNKS:", len(chunks))

        total_chunks += len(chunks)

        for i, chunk in enumerate(chunks):
            print("\n--- CHUNK", i, "---")
            print("Length:", len(chunk["content"]))
            print("Metadata:", chunk["metadata"])
            print(chunk["content"])

    print("\n" + "=" * 80)
    print("TOTAL CHUNKS:", total_chunks)
    print("=" * 80)


if __name__ == "__main__":
    main()