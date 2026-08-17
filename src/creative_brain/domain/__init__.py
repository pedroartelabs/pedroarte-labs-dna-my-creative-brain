"""The creative domain.

This package is the heart of the system and it depends on **nothing**: no LLM
SDK, no database, no framework, no filesystem, no HTTP. Only the Python
standard library. Everything the domain needs from the outside world arrives
through ``creative_brain.ports``.

The rule enforced by ``tests/architecture`` is simply::

    DEPENDENCIES POINT INWARD
"""
