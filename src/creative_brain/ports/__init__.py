"""Ports: the contracts between the creative mind and everything else.

Inbound ports are driven *by* the outside world (CLI, future API).
Outbound ports are driven *by* the application towards the outside world
(LLMs, storage, research, clocks, buses).

No port implementation lives here — only the contracts.
"""
