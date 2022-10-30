"""Main dispatcher for nornir."""
import logging
import importlib

# from nornir.core.exceptions import NornirSubTaskError
from nornir.core.task import Result, Task

from django.conf import settings

# TODO: Adding configuration settings, was: import nautobot_device_onboarding.network_importer.config as config

LOGGER = logging.getLogger("network-importer")
PLUGIN_SETTINGS = settings.PLUGINS_CONFIG.get("nautobot_device_onboarding", {})


def dispatcher(task: Task, method: str) -> Result:
    """Helper Task to retrieve a given Nornir task for a given platform
    Args:
        task (Nornir Task):  Nornir Task object
        method (Nornir Task):  Nornir Task object
    Returns:
        Result: Nornir Task result
    """

    LOGGER.debug("Executing dispatcher for %s (%s)", task.host.name, task.host.platform)

    # Get the platform specific driver, if not available, get the default driver
    driver = (
        PLUGIN_SETTINGS.get("drivers", {})
        .get("mapping", {})
        .get(task.host.platform, PLUGIN_SETTINGS.get("drivers", {}).get("mapping", {}).get("default"))
    )
    LOGGER.debug("Found driver %s", driver)

    if not driver:
        LOGGER.warning(
            "%s | Unable to find the driver for %s for platform : %s", task.host.name, method, task.host.platform
        )
        return Result(host=task.host, failed=True)

    driver_class = getattr(importlib.import_module(driver), "NetworkImporterDriver")

    if not driver_class:
        LOGGER.error("%s | Unable to locate the class %s", task.host.name, driver)
        return Result(host=task.host, failed=True)

    try:
        driver_task = getattr(driver_class, method)
    except AttributeError:
        LOGGER.error("%s | Unable to locate the method %s for %s", task.host.name, method, driver)
        return Result(host=task.host, failed=True)

    result = task.run(task=driver_task)

    return Result(host=task.host, result=result)
