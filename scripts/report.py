import os

import django
import pandas as pd

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from core.models import Invoice  # noqa: E402


def main():
    rows = [
        {
            "invoice": invoice.number,
            "amount": float(invoice.amount),
            "allocated": float(invoice.allocated),
            "outstanding": float(invoice.outstanding),
        }
        for invoice in Invoice.objects.prefetch_related("allocations")
    ]

    df = pd.DataFrame(
        rows,
        columns=["invoice", "amount", "allocated", "outstanding"],
    )

    print(df.to_string(index=False))

    total_outstanding = round(df["outstanding"].sum(), 2)
    print("Total outstanding:", total_outstanding)


if __name__ == "__main__":
    main()
