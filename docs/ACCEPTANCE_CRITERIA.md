# Acceptance criteria

- **AC-01:** An unauthenticated user cannot access financial records through the UI or APIs.
- **AC-02:** Staff can create customers, invoices and payments; viewers cannot submit changes.
- **AC-03:** Staff can run matching through the UI; matching writes only suggestions, not allocations.
- **AC-04:** Staff can confirm or reject a suggested match; ambiguous and duplicate-reference cases cannot be directly confirmed.
- **AC-05:** Sum of allocations never exceeds the invoice or payment amounts; invoice/payment customers must agree.
- **AC-06:** Two concurrent MySQL workers cannot allocate more than the available invoice balance.
- **AC-07:** Dashboard totals reconcile to posted allocations, including partial payments.
- **AC-08:** Invalid, negative, NaN and overprecision amounts fail validation.
- **AC-09:** If Flask is unavailable, the UI shows an error rather than inventing matches.
- **AC-10:** A local Windows 11 user can start the SQLite demo without Docker.

**Evidence:** Pure matching cases for AC-04/08 passed in the isolated test run; Django/Flask/MySQL/Windows checks are pending. Read `EXECUTION_REPORT.md` rather than treating written tests as completed acceptance.
