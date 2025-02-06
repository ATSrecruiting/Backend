# Makefile for Alembic commands

.PHONY: migrate upgrade

# Command to autogenerate a migration file
migrate:
	alembic revision --autogenerate -m "$(message)"

# Command to upgrade the database to the latest migration
upgrade:
	alembic upgrade head