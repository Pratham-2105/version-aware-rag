"""
Stage 5 — structured extraction of project records, one document at a time.

The LLM fills in only WHAT the document says (name, status, reason, ...).
Provenance (source file, version date) is attached by our code, never by the model.
"""

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

OLLAMA_URL = "http://127.0.0.1:11434"
EXTRACTION_MODEL = "qwen2.5:7b"

Status = Literal["active", "paused", "done", "abandoned", "planned", "unclear"]


class ProjectMention(BaseModel):
    """One project as described in ONE document. Fields are generated in this order."""

    name: str = Field(
        description="Short project name only, without subtitle or description, e.g. 'PixelNet' (not 'PixelNet — Image Classifier')."
    )
    description: str = Field(
        description="One sentence on what the project is. Empty string if not described."
    )
    status_evidence: str = Field(
        description="Short phrase copied from the document that shows the project's status. Empty string if status is not stated."
    )
    status: Status = Field(
        description=(
            "Status of the project according to THIS document, based on the evidence above. "
            "active = being worked on; paused = stopped for now, may resume; "
            "done = finished or shipped; abandoned = dropped for good; "
            "planned = not started yet; unclear = described but status not stated."
        )
    )
    status_reason: str = Field(
        description=(
            "WHY the project has this status, if the document says so (e.g. why it was paused or dropped). "
            "Not the status word itself, and not a description of the project. Empty string if no reason is given."
        )
    )
    next_step: str = Field(
        description="Stated next step for the project. Empty string if not stated."
    )
    key_metric: str = Field(
        description=(
            "A measured result that contains a number, e.g. '91.3% accuracy' or '40% complete'. "
            "Not a feature or a description. Empty string if no number is stated."
        )
    )
    tech: list[str] = Field(
        max_length=8,
        description=(
            "Up to 8 languages, frameworks, libraries or platforms used, e.g. 'NumPy', 'FastAPI', 'Railway'. "
            "Not concepts or techniques like 'backpropagation' or 'dropout'. Empty list if none."
        ),
    )


class DocumentExtraction(BaseModel):
    """All projects described in one document."""

    projects: list[ProjectMention] = Field(
        description="Every project this document describes. Empty list if it describes none."
    )


SYSTEM_PROMPT = """You extract project records from a student's personal notes.

Rules:
- Only use what THIS document says. Do not guess or use outside knowledge.
- Include a project only if the document describes it, not a passing one-word mention.
- A course, exam, job application or skill is not a project.
- Copy numbers exactly as written.
- If something is not stated, use an empty string or an empty list."""

HUMAN_TEMPLATE = """Document path: {source}

Document:
{document}"""


def build_extraction_chain():
    """prompt | structured model  ->  a Runnable: dict in, DocumentExtraction out."""
    llm = ChatOllama(
        model=EXTRACTION_MODEL,
        base_url=OLLAMA_URL,
        temperature=0,
        seed=42,
        num_ctx=8192,
        num_predict=1024,  # hard cap on output tokens — stops runaway JSON
        client_kwargs={"timeout": 120},  # give up on one doc after 2 min
    )
    structured_llm = llm.with_structured_output(
        DocumentExtraction, method="json_schema"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ]
    )
    return prompt | structured_llm


def extract_from_document(chain, source, text, meta):
    """Run the chain on one document; attach provenance from our ingestion metadata."""
    result = chain.invoke({"source": source, "document": text})
    mentions = []
    for project in result.projects:
        record = project.model_dump()
        record.update(
            {
                "source": source,
                "version_date": meta["version_date"],
                "date_source": meta["date_source"],
                "doc_group_id": meta["doc_group_id"],
                "is_latest": meta["is_latest"],
            }
        )
        mentions.append(record)
    return mentions
