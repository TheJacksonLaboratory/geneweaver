"""Alembic version definitions.

We're using versions sligtly differently than the default Alembic versioning.

The first version creates a table to be shared across schemas (data loads)
and subsequent versions create the per-data-load tables, and must be run individually
against a specified schema.

This can be done by using the builtin gwaon commands, or by using the -x option, e.g

`-x tenant=$SCHEMA_NAME`
"""
