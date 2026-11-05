"""Reproducible *synthetic* matching evaluation, not a production benchmark.

Ground truth is constructed explicitly and not inferred from the same rules.
A prediction is a proposed invoice ID, even if approval is still required.
"""

import csv
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.logic import suggest  # noqa: E402


def dataset():
    invoices, payments, truth = [], [], {}
    invoice_id, payment_id = 0, 0
    scenarios = [
        ("exact_reference", 20),
        ("invoice_hint", 20),
        ("amount_only", 20),
        ("partial_payment", 20),
        ("duplicate_reference", 10),
        ("unmatched", 10),
        ("ambiguous_amount", 10),
        ("wrong_invoice_hint", 10),
        ("overpayment", 10),
        ("fully_allocated", 10),
    ]
    for kind, quantity in scenarios:
        for index in range(quantity):
            invoice_id += 1
            payment_id += 1
            customer = (
                invoice_id  # distinct shops avoid accidental cross-case ambiguity
            )
            number = f"INV-{invoice_id:04}"
            amount = Decimal("1000") + invoice_id
            invoice = {
                "id": invoice_id,
                "customer_id": customer,
                "number": number,
                "amount": str(amount),
            }
            payment = {
                "id": payment_id,
                "customer_id": customer,
                "reference": f"BANK-{payment_id:04}",
                "invoice_hint": "",
                "amount": str(amount),
            }
            if kind == "exact_reference":
                payment["reference"] = number
                truth[str(payment_id)] = str(invoice_id)
            elif kind == "invoice_hint":
                payment["invoice_hint"] = number
                truth[str(payment_id)] = str(invoice_id)
            elif kind == "amount_only":
                truth[str(payment_id)] = str(invoice_id)
            elif kind == "partial_payment":
                payment["invoice_hint"] = number
                payment["amount"] = str((amount / 2).quantize(Decimal("0.01")))
                truth[str(payment_id)] = str(invoice_id)
            elif kind == "duplicate_reference":
                payment["invoice_hint"] = number
                second = dict(payment, id=payment_id + 100000)
                payments.append(second)
                truth[str(second["id"])] = (
                    None  # cannot identify true payer with certainty
                )
                truth[str(payment_id)] = None
            elif kind == "unmatched":
                truth[str(payment_id)] = None
                payment["amount"] = "13.13"
            elif kind == "ambiguous_amount":
                invoice_id += 1
                invoices.append(
                    {
                        "id": invoice_id,
                        "customer_id": customer,
                        "number": f"INV-{invoice_id:04}",
                        "amount": str(amount),
                    }
                )
                truth[str(payment_id)] = None  # indistinguishable equal-amount invoices
            elif kind == "wrong_invoice_hint":
                invoice_id += 1
                wrong_id = invoice_id
                invoices.append(
                    {
                        "id": wrong_id,
                        "customer_id": customer,
                        "number": f"INV-{wrong_id:04}",
                        "amount": str(amount + 50),
                    }
                )
                payment["invoice_hint"] = f"INV-{wrong_id:04}"
                truth[str(payment_id)] = str(
                    invoice["id"]
                )  # deliberately incorrect hint
            elif kind == "overpayment":
                payment["invoice_hint"] = number
                payment["amount"] = str(amount + Decimal("100"))
                truth[str(payment_id)] = str(
                    invoice_id
                )  # partial allocation, residual remains
            elif kind == "fully_allocated":
                invoice["outstanding"] = "0.00"
                payment["unallocated"] = "0.00"
                truth[str(payment_id)] = None
            invoices.append(invoice)
            payments.append(payment)
    return invoices, payments, truth


def evaluate():
    invoices, payments, truth = dataset()
    rows = []
    for label, baseline in [
        ("exact_reference_baseline", True),
        ("explainable_rules", False),
    ]:
        start = time.perf_counter()
        suggestions = suggest(invoices, payments, baseline=baseline)
        elapsed = time.perf_counter() - start
        guesses = {item["payment_id"]: item["invoice_id"] for item in suggestions}
        tp = sum(
            expected is not None and guesses.get(key) == expected
            for key, expected in truth.items()
        )
        fp = sum(
            predicted is not None and predicted != truth[key]
            for key, predicted in guesses.items()
        )
        fn = sum(
            expected is not None and guesses.get(key) != expected
            for key, expected in truth.items()
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        rows.append(
            {
                "method": label,
                "cases": len(payments),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(
                    (2 * precision * recall / (precision + recall))
                    if precision + recall
                    else 0,
                    4,
                ),
                "true_matches": tp,
                "false_matches": fp,
                "missed_matches": fn,
                "exception_flags": sum(
                    x["reason"]
                    in {
                        "AMOUNT_ONLY_REVIEW",
                        "AMBIGUOUS",
                        "DUPLICATE_REFERENCE",
                        "OVERPAYMENT_REVIEW",
                        "UNMATCHED",
                        "ALREADY_ALLOCATED",
                    }
                    for x in suggestions
                ),
                "elapsed_seconds": round(elapsed, 6),
            }
        )
    target = ROOT / "data" / "evaluation.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)
    return rows


if __name__ == "__main__":
    evaluate()
