"""Pipeline orchestrator.

Sequences the parser, categorizer, analysis, and recommendation agents
by run_id in stage order, updating the run's status in the DB as each
stage starts/completes/fails. A linear sequencer, not a graph executor.
"""
