"""Base agent contract.

Defines the BaseAgent ABC that every pipeline agent implements. Agents
do not call each other directly: each agent reads its input for a given
run_id from the DB and writes its output back for the DB, so the
orchestrator can sequence them linearly without shared in-memory state.
"""
