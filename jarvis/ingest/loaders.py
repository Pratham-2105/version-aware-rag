import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

def load_vault(directory_path: str) -> dict:
    
    file_dict = {}

    for directory, subFolders, files in os.walk(directory_path):
        if "skip" in directory:
            continue

        for file in files:
            full_file_path =  os.path.join(directory, file)
            file_realtive_path = os.path.relpath(full_file_path, directory_path)

            with open(full_file_path, 'r', encoding='utf-8') as current_file:
                content = current_file.read()
            
                file_key = file_realtive_path
                file_content = content  

                file_dict[file_key] = file_content

    return file_dict

if __name__ == "__main__":
    directory_path = Path("././data/sample-vault/")
    check_dict = load_vault(directory_path)
    
    for key, value in check_dict.items():
        print(f"KEY: {key}")
        
        # print just first 50 chars so it doesn't flood the terminal
        print("CONTENT: ")
        print(value[:51])

    print(f"\nLoaded: {len(check_dict)} files")