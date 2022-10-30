"""Nautobot Network Importer SSOT Sync.

This job syncrhonizes data using the Nautobot SSOT sync pattern
"""
from nautobot.extras.jobs import BooleanVar, Job
from nautobot_ssot.jobs.base import DataSource

from diffsync import DiffSyncFlags

name = "SSoT - Network Importer"


class NetworkDeviceDataSource(DataSource, Job):
    """Network device data source."""

    debug = BooleanVar(description="Enable for verbose debug logging.")

    def __init__(self):
        """Initialization of Nautobot Plugin Network Importer SSOT."""
        super().__init__()
        self.diffsync_flags = DiffSyncFlags.CONTINUE_ON_FAILURE | DiffSyncFlags.SKIP_UNMATCHED_DST
