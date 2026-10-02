from alembic import context

connection = context.config.attributes["connection"]
context.configure(connection=connection, compare_type=True)
with context.begin_transaction():
    context.run_migrations()
