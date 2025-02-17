# Makefile for Alembic commands

.PHONY: migrate upgrade


startdb:
	sudo docker start atd-postgers

# Command to autogenerate a migration file
migrate:
	alembic revision --autogenerate -m "$(filter-out $@,$(MAKECMDGOALS))"

# Command to upgrade the database to the latest migration
upgrade:
	alembic upgrade head 