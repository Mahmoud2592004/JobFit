"""
Job Aggregation Providers.
"""

from app.providers.jobs.arbeitnow import ArbeitnowProvider
from app.providers.jobs.base import JobProvider
from app.providers.jobs.linkedin_apify import LinkedInApifyProvider
from app.providers.jobs.remotive import RemotiveProvider

__all__ = [
    "JobProvider",
    "LinkedInApifyProvider",
    "RemotiveProvider",
    "ArbeitnowProvider",
]
