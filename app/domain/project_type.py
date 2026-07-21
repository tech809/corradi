from enum import Enum


class ProjectType(str, Enum):
    YOUTH_EXCHANGE = "YOUTH_EXCHANGE"
    TRAINING_COURSE = "TRAINING_COURSE"
    VOLUNTEERING = "VOLUNTEERING"
    WORKSHOP = "WORKSHOP"


class ProjectStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
