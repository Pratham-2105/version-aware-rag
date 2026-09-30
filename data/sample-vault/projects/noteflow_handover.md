# NoteFlow — AI-Powered Note Intelligence

## Status: ACTIVE (main build as of October 2026)

### What It Is
An AI-powered app where you point it at a folder of notes and it can:
- Answer questions about your notes with citations
- Summarize across multiple documents
- Track how your thinking on a topic evolved over time
- Tell you when notes contradict each other

### Why I'm Building This
Every semester I accumulate tons of notes, handovers, plans, and project docs. I can never find anything. Existing tools (Notion AI, Obsidian plugins) don't handle the version problem — when I have 5 versions of a plan, they retrieve whichever is most similar to my question, not the most recent one.

### Architecture (planned)
- **Ingestion:** load markdown/docx/pdf → chunk with section awareness → embed → store in Chroma
- **Retrieval:** hybrid search (dense embeddings + BM25 keyword) → version-aware reranking
- **Agent:** LangChain agent with tools for search, status lookup, timeline queries
- **Interface:** CLI first, then FastAPI endpoint, potentially MCP server

### Current Progress (~40% as of October 2026)
- File loaders working (md + docx)
- Basic chunking implemented (split on headers)
- Chroma vector store set up
- Dense retrieval working (but no version awareness yet)
- CLI chat loop working with basic RAG

### What's Left
- BM25 / hybrid retrieval
- Document dedup and version grouping
- Version-aware ranking
- Structured project registry
- Proper evaluation harness
- Agent with tools
- FastAPI deployment

### Tech Stack
Python, FastAPI, LangChain, Chroma, potentially LangGraph later

### Repository
github.com/arjunmehta/noteflow (private for now, will open-source at MVP)
