import re


def chunk_document(text: str, relative_path: str) -> list:
    """
    Split markdown text on headers. Each chunk carries its header path
    and source file path.
    """
    lines = text.split("\n")
    chunks = []
    
    # Track current header at each level: {1: "Title", 2: "Section", 3: "Subsection"}
    header_stack = {}
    
    current_content_lines = []
    current_header_level = 0
    
    for line in lines:
        # Check if line is a markdown header
        header_match = re.match(r'^(#{1,6})\s+(.*)', line)
        
        if header_match:
            # Save the previous chunk before starting a new one
            if current_content_lines:
                content = "\n".join(current_content_lines).strip()
                if content:
                    header_path = build_header_path(header_stack, current_header_level)
                    chunks.append({
                        "content": content,
                        "header_path": header_path,
                        "source": relative_path
                    })
            
            # Update header stack
            level = len(header_match.group(1))  # number of # symbols
            header_text = header_match.group(2).strip()
            header_stack[level] = header_text
            
            # Clear any deeper headers (if we go from ### back to ##)
            for deeper in list(header_stack.keys()):
                if deeper > level:
                    del header_stack[deeper]
            
            current_header_level = level
            current_content_lines = []
        else:
            current_content_lines.append(line)
    
    # Don't forget the last chunk
    if current_content_lines:
        content = "\n".join(current_content_lines).strip()
        if content:
            header_path = build_header_path(header_stack, current_header_level)
            chunks.append({
                "content": content,
                "header_path": header_path,
                "source": relative_path
            })
    
    # If no headers found at all, whole text is one chunk
    if not chunks and text.strip():
        chunks.append({
            "content": text.strip(),
            "header_path": "",
            "source": relative_path
        })
    
    return chunks


def build_header_path(header_stack: dict, current_level: int) -> str:
    """
    Build a path like "Master Handoff > Project Statuses > PixelNet"
    from all active headers up to current_level.
    """
    path_parts = []
    for level in sorted(header_stack.keys()):
        if level <= current_level:
            path_parts.append(header_stack[level])
    return " > ".join(path_parts)


if __name__ == "__main__":
    # Quick test with a small markdown string
    test_md = """# Arjun Mehta — Master Handoff
## October 10, 2026

### Who I Am
B.Tech CS, 3rd year.

### Projects
Some project info here.

#### PixelNet
91.3% accuracy on CIFAR-10.

#### NoteFlow
About 40% done.

### Competitive Programming
CF rating: 1550.
"""
    
    chunks = chunk_document(test_md, "handovers/test_file.md")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i} ---")
        print(f"Header path: {chunk['header_path']}")
        print(f"Source: {chunk['source']}")
        print(f"Content: {chunk['content'][:100]}...")