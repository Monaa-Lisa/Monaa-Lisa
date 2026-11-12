# Database migrations

The database schema is defined only here, as plain SQL files run by
[dbmate](https://github.com/amacneil/dbmate). The backend (Kysely) and the
Python pipeline (SQLAlchemy) both work against this schema, neither of them
creates tables.

`docker compose up` runs the `migrate` service first, it applies every
migration that is not applied yet and exits.

## Add a migration

1. Create a file `db/migrations/<YYYYMMDDHHMMSS>_<what_it_does>.sql`:

   ```sql
   -- migrate:up
   ALTER TABLE paper ADD COLUMN example TEXT;

   -- migrate:down
   ALTER TABLE paper DROP COLUMN example;
   ```

2. Apply it: `docker compose run --rm migrate`
3. Update the backend types from the database:
   `cd MonaaLisa/src/Backend && DATABASE_URL=postgres://... npm run db:types`
4. If the Python pipeline uses the table, update `MonaaLisa/src/Database/db_models.py`.

## Existing databases from the Prisma times

The first migration (`..._baseline.sql`) only uses `CREATE ... IF NOT EXISTS`.
On a database that was set up by the old Prisma migrations it changes nothing,
the later migrations then bring it up to date and remove `_prisma_migrations`.
