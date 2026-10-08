"""Hybrid retrieval: dense (Chroma) + sparse (BM25) fused with Reciprocal Rank Fusion."""
from collections import defaultdict

from jarvis.retrieval.bm25 import BM25Index
from jarvis.retrieval.vector_store import query_vectorstore

RRF_K = 60
CANDIDATES = 20


def reciprocal_rank_fusion(ranked_lists, k=RRF_K):
    """ranked_lists: list of lists of ids, best first. Returns fused id list."""
    scores = defaultdict(float)
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)


class HybridRetriever:
    def __init__(self, collection):
        self.collection = collection
        self.bm25 = BM25Index.from_collection(collection)
        self.by_id = {
            i: (d, m)
            for i, d, m in zip(self.bm25.ids, self.bm25.documents, self.bm25.metadatas)
        }

    def search(self, query, top_k=5, where=None, mode="hybrid"):
        """mode: 'dense', 'sparse', or 'hybrid'. Returns Chroma-shaped results."""
        dense_ids = []
        if mode in ("dense", "hybrid"):
            dense = query_vectorstore(self.collection, query, top_k=CANDIDATES, where=where)
            dense_ids = dense["ids"][0]

        sparse_ids = []
        if mode in ("sparse", "hybrid"):
            sparse_ids = [i for i, _ in self.bm25.search(query, top_k=CANDIDATES, where=where)]

        if mode == "dense":
            fused = dense_ids
        elif mode == "sparse":
            fused = sparse_ids
        else:
            fused = reciprocal_rank_fusion([dense_ids, sparse_ids])

        top = fused[:top_k]
        return {
            "ids": [top],
            "documents": [[self.by_id[i][0] for i in top]],
            "metadatas": [[self.by_id[i][1] for i in top]],
        }