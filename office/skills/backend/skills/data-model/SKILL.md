---
name: data-model
description: Use when the change stores or reads data: a schema, a migration, a model, a query. Keeps data safe, consistent and fast.
---

# Data model

1. Start with the simplest storage that fits: a JSON file or SQLite for a prototype or a single user; Postgres when several users write at once or the data must survive a redeploy.
2. Model explicitly: types, which fields are required, unique keys, and foreign keys between tables. Tables are plural nouns and columns `snake_case`.
3. Change the schema only through migrations committed with the code, and never edit a migration that has already run; add a new one.
4. Use parameterized queries or the ORM's query builder. Never put input into SQL with string formatting.
5. Index the columns you filter, sort or join on.
6. Wrap writes that must happen together in one transaction.
7. Development data comes from a seed script, not from editing the database by hand.
8. Tests use a fresh database (a temporary SQLite file or a test schema), never real data.
