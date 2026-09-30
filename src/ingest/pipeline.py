from pathlib import Path

from chunker import chunk_document
from loaders import load_vault

directory_path = Path("././data/sample-vault/")

file_vault_dict = load_vault(directory_path)

file_chunks = []

for key, value in file_vault_dict.items():
    chunks = chunk_document(value, key)
    file_chunks.extend(chunks)

for chunk in file_chunks[:5]:
    print(f"Source: {chunk['source']}")
    print(f"Header: {chunk['header_path']}")
    print(f"Content: {chunk['content'][:200]}")
    print("---")

print(f"Length of file_chunks: {len(file_chunks)}")