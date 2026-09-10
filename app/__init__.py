"""
VisionIQ Enterprise - Application Package
==========================================
Layered architecture:
  app.core        - cross-cutting concerns (config, security, logging, exceptions)
  app.db          - database infrastructure (connection pool, schema, repositories)
  app.services    - business logic (orchestrates repositories + detectors)
  app.api         - HTTP API layer (FastAPI factory, middleware, versioned routes)
  app.pipeline    - detection engine (scheduler, circuit breaker, frame grabber)
  app.detectors   - ML inference wrappers (pure functions, no DB/config deps)
"""

__version__ = "2.0.0"
__author__ = "VisionIQ Engineering"