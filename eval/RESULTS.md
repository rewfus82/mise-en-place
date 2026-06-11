# Retrieval evaluation (23 gold questions)

| Method | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---|---|---|---|
| Dense (sqlite-vec) | 0.652 | 0.913 | 0.957 | 0.791 |
| Sparse (BM25) | 0.565 | 0.870 | 0.913 | 0.733 |
| **Hybrid (RRF)** | 0.609 | 0.957 | 0.957 | 0.782 |

Scored at (document, section) granularity — the chunk that feeds the prompt. Hit@k = share of questions with a correct chunk in the top k; MRR = mean reciprocal rank of the first correct chunk.
