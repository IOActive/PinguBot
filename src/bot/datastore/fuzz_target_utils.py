
"""Helper functions related to fuzz target entities."""
from bot.datastore import data_types, data_handler


def get_fuzz_targets_for_target_jobs(target_jobs):
    """Return corresponding FuzzTargets for the given FuzzTargetJobs."""
    fuzz_targets = []
    for target_job in target_jobs:
        fuzz_target = data_handler.get_fuzz_target_by_id(target_job.fuzzing_target)
        fuzz_targets.append(fuzz_target)
    return fuzz_targets


def get_fuzz_target_jobs(engine=None,
                         job=None):
    """Return a Datastore query for fuzz target to job mappings."""

    if job:
        fuzz_target_jobs = data_handler.get_fuzz_target_job_by_job(job_id=job)
        return fuzz_target_jobs

    elif engine:
        fuzz_target_jobs = data_handler.get_fuzz_target_job_by_engine(engine=engine)
        return fuzz_target_jobs




