import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ingest.chunker import chunk_document
from src.ingest.loaders import load_vault


def run_ingestion(value_path: str) -> list:

    file_vault_dict = load_vault(value_path)

    file_chunks = []

    for key, value in file_vault_dict.items():
        chunks = chunk_document(value, key)
        file_chunks.extend(chunks)

    return file_chunks

if __name__ == "__main__":

    directory_path = Path("././data/sample-vault/")

    chunks = run_ingestion(directory_path)

    for chunk in chunks[:5]:
        print(f"Source: {chunk['source']}")
        print(f"Header: {chunk['header_path']}")
        print(f"Content: {chunk['content'][:200]}")
        print("---")

    print(f"Length of file_chunks: {len(chunks)}")