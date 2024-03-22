
"""Profiling functions."""
from bot.metrics import logs
from bot.system import environment
from bot.utils import utils


def start_if_needed(service):
    """Start Google Cloud Profiler if |USE_PYTHON_PROFILER| environment variable
  is set."""
    if not environment.get_value('USE_PYTHON_PROFILER'):
        return True

    project_id = utils.get_application_id()
    service_with_platform = '{service}_{platform}'.format(
        service=service, platform=environment.platform().lower())

    try:
        # Import the package here since it is only needed when profiler is enabled.
        # Also, this is supported on Linux only.
        import googlecloudprofiler
        googlecloudprofiler.start(
            project_id=project_id, service=service_with_platform)
    except Exception:
        logs.log_error(
            'Failed to start the profiler for service %s.' % service_with_platform)
        return False

    return True
