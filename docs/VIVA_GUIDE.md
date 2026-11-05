# Viva guide — ReconDesk

**What is the problem?** A small business stores invoices and bank payment receipts separately. Invoice numbers may be missing from payment references, so basic exact-reference lookup misses legitimate payments. Careless amount matching can choose the wrong invoice.

**What is the solution?** Django provides the UI and financial database; a small Flask endpoint uses explainable rules to suggest candidates. A staff user checks each candidate before the transactional Django service posts an allocation. This is easier to audit than automatic posting.

**Why Django and Flask?** Django owns users, CRUD, REST APIs and database writes. Flask is a narrowly scoped matching API, included because the target EY JD names both frameworks. It is not justified as a production-scale microservice.

**Why SQLite and MySQL?** SQLite is convenient for a laptop demo without Docker; MySQL 8.4 is the target relational database for server-side testing. SQLite's locking is not proof of InnoDB concurrency safety.

**Why Decimal?** Binary floating point can misrepresent cents. `Decimal` strings with two-decimal validation are used for allocation checks.

**What is the main limitation?** A plausible but wrong invoice hint may yield the wrong suggestion. The 150-case synthetic evaluation intentionally documents 10 such false links. Human approval is required.

**What did you validate?** 26 standalone Python matching tests and a reproducible synthetic evaluation ran in the generation sandbox. Do not claim that Django, Flask, Windows, MySQL or GitHub CI passed until you execute them.

**How is Agile/SDLC represented?** Requirements, user stories, backlog, acceptance criteria, traceability matrix, test plan and release checklist are included. They are planning artifacts and don't imply real past Scrum ceremonies.
