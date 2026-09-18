"""GenerationJob projection over Studio Job + ExecutionPlan.

Additive adapter — does not rename frozen ExecutionPlan fields (Law 16).
"""

from .contracts import CREATOR_STAGES, GenerationJob, GenerationJobStatus
from .project import attach_generation_job, execution_json, project_generation_job

__all__ = [
    "CREATOR_STAGES",
    "GenerationJob",
    "GenerationJobStatus",
    "attach_generation_job",
    "execution_json",
    "project_generation_job",
]
