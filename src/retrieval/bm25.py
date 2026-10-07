"""BM25 keyword index over the chunks stored in Chroma."""
import re

from rank_bm25 import BM25Okapi

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self, ids, documents, metadatas):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas
        corpus = [
            tokenize(f"{m.get('source', '')} {m.get('header_path', '')} {d}")
            for d, m in zip(documents, metadatas)
        ]
        self.token_sets = [set(tokens) for tokens in corpus]
        self.bm25 = BM25Okapi(corpus)

    @classmethod
    def from_collection(cls, collection):
        data = collection.get(include=["documents", "metadatas"])
        return cls(data["ids"], data["documents"], data["metadatas"])

    def search(self, query, top_k=20, where=None):
        """Returns [(chunk_id, score), ...] best first.
        A chunk is a candidate only if it shares at least one token with the query.
        Scores can be negative (terms in >half the corpus), so sign is NOT used as a cutoff.
        where: simple equality filter, e.g. {"is_latest": True}."""
        query_tokens = tokenize(query)
        query_set = set(query_tokens)
        scores = self.bm25.get_scores(query_tokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results = []
        for i in order:
            if not query_set & self.token_sets[i]:
                continue
            if where and not all(self.metadatas[i].get(k) == v for k, v in where.items()):
                continue
            results.append((self.ids[i], float(scores[i])))
            if len(results) == top_k:
                break
        return results