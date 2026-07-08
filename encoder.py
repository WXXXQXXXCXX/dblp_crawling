import ast
import csv

from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import AgglomerativeClustering

class ExpertiseMatcher:
    def __init__(self, model: SentenceTransformer, file: str):
        self.model = model
        self.file = file
        existing = []
        with open(file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                existing.append(ast.literal_eval(row[2]))
        self.existing = np.asarray(existing, dtype=np.float32)
        self.existing /= np.linalg.norm(self.existing, axis=1, keepdims=True)

    def encode(self, text: list[str]):
        return self.model.encode(text, batch_size=32)

    def cluster(self, embeddings: np.ndarray):
        if len(embeddings) == 0:
            return []
        if len(embeddings) == 1:
            print(type(embeddings), np.asarray(embeddings).shape)
            return [embeddings[[0]].mean(axis=0)]

        clustering_model = AgglomerativeClustering(
            n_clusters=None, distance_threshold=1.5
        )
        clustering_model.fit(embeddings)
        cluster_assignment = clustering_model.labels_
        clustered_embeddings = {}
        for idx, cluster_id in enumerate(cluster_assignment):
            if cluster_id not in clustered_embeddings:
                clustered_embeddings[cluster_id] = []

            clustered_embeddings[cluster_id].append(idx)
        res = []
        for grp in clustered_embeddings.values():
            avg = embeddings[grp].mean(axis=0)
            res.append(avg)
        return res

    def find_matches(self, embeddings: list, cosine_threshold: float=0.6) -> list[int | None]:
        if len(embeddings) == 0:
            return []
        queries = np.asarray(embeddings, dtype=np.float32)
        queries /= np.linalg.norm(queries, axis=1, keepdims=True)

        similarities = queries @ self.existing.T

        best_indices = np.argmax(similarities, axis=1)
        best_scores = similarities[np.arange(len(queries)), best_indices]

        return [int(idx) if score >= cosine_threshold else None for idx, score in zip(best_indices, best_scores)]
