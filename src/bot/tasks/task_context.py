from pingu_sdk.datastore.models import Project, Job
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client
from pingu_sdk.system.tasks import Task

class TaskContext:
    def __init__(self, task: Task, project: Project, job: Job, fuzzer_name: str = None):
        self.task = task
        self.job = job
        self.project = project
        self.fuzzer = None
        self.fuzzer_name = fuzzer_name
        if self.fuzzer_name:
            fuzzer = get_api_client().fuzzer_api.get_fuzzer(name=fuzzer_name)
            self.fuzzer = fuzzer