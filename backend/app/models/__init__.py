"""모델 11개 (명세 12.2). 테이블 1개 = 파일 1개.

Alembic이 모든 테이블을 알 수 있게 여기서 전부 import한다.
"""

from app.models.device_code import DeviceCode
from app.models.dog import Dog
from app.models.dog_vital import DogVital
from app.models.institution import Institution
from app.models.measure_session import MeasureSession
from app.models.purge_log import PurgeLog
from app.models.report import Report
from app.models.session_metric import SessionMetric
from app.models.shot import Shot
from app.models.staff import Staff
from app.models.walk_pass import WalkPass

__all__ = [
    "DeviceCode",
    "Dog",
    "DogVital",
    "Institution",
    "MeasureSession",
    "PurgeLog",
    "Report",
    "SessionMetric",
    "Shot",
    "Staff",
    "WalkPass",
]
