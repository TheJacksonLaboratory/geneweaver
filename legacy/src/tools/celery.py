from __future__ import absolute_import

from celery import Celery,Task,current_task
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

__all__ = ['logger','current_task','Task','celery']

logger = get_task_logger(__name__)

#BROKER_URL = 'redis://ode-db3:6379/0'
#CELERY_RESULT_BACKEND = 'redis://ode-db3:6379/0'
BROKER_URL = 'amqp://ode-db3'
CELERY_RESULT_BACKEND = 'amqp://ode-db3'
#BROKER_URL = 'amqp://odeadmin:ontological@ode-db3/'
#CELERY_RESULT_BACKEND = 'amqp://odeadmin:ontological@ode-db3/'

celery = Celery('geneweaver.tools',broker=BROKER_URL,backend=CELERY_RESULT_BACKEND,
        include=['tools.PhenomeMap','tools.GeneSetViewer','tools.Combine','tools.HyperGeometric','tools.JaccardSimilarity','tools.JaccardClustering'])

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_TASK_SERIALIZER='json',
    CELERY_RESULT_SERIALIZER = "json",
    CELERY_TASK_RESULT_EXPIRES = None,
		CELERYD_TASK_SOFT_TIME_LIMIT = 600,
		CELERYD_TASK_TIME_LIMIT = 600,
)

if __name__ == '__main__':
    celery.start()
