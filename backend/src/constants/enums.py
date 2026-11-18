from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'

class HandoverStatus(str, Enum):
    pending = 'pending'
    running = 'running'
    completed = 'completed'
    failed = 'failed'

class HandoverPhase(str, Enum):
    datasets = 'datasets'
    jobs = 'jobs'
    deliveries = 'deliveries'
    done = 'done'
