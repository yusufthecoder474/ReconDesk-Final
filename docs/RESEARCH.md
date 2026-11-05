# Applied research context and limitations

**Question:** How do deterministic, explainable invoice-payment matching rules compare with an exact-invoice-reference baseline on a controlled synthetic dataset?

Relevant academic context to independently verify from publishers before formal academic submission:

- Munoz, Jalili and Tafakori (2025), *Enhancing bookkeeper decision support through graph representation learning for bank reconciliation*, Journal of Finance and Data Science, DOI 10.1016/j.jfds.2025.100170. This examines bank reconciliation; the project does **not** reproduce its graph model.
- Dadopoulos and Moschidis (2026), *Beyond Fuzzy Matching: A Dual-Augmentation RAG System for Robust Product Reconciliation in Accounting*, Journal of Risk and Financial Management 19(6), 402. Product-description reconciliation is distinct from this invoice-payment task.
- NIST AI Risk Management Framework 1.0 (2023): governance and review guidance, **not** a reconciliation accuracy experiment.

These references were drawn from the earlier project brief and **their publisher metadata was not independently verified during this build**. Do not claim a research gap is established, new algorithmic novelty, or state-of-the-art performance.

`python scripts/evaluate.py` generates a deterministic 150-payment evaluation. Scenarios include correct and incorrect invoice hints, unmatched amounts, duplicate references, already-allocated money, ambiguity, partial payments and overpayments. Ground-truth safe target IDs are labeled independently in code. All recommendations require human review in the live application.

**Measured sandbox outputs:** baseline precision 1.00, recall 0.20, F1 0.3333; explainable rules precision/recall/F1 0.90. The 10 wrong candidate links are caused by deliberately misleading invoice hints. This evaluation is synthetic and not evidence of realistic prevalence, generalization, or production suitability. No third-party dataset, human audit, confidence interval or cross-institutional study was performed.
