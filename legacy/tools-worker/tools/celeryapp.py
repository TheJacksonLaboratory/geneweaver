from __future__ import absolute_import

from celery import Celery
from celery import Task, current_task
from celery.utils.log import get_task_logger

# If you change the name of the tools directory (it's "tools" by default) then
# you need to change the "tools" package here to match.
import tools.config as config

__all__ = ['logger', 'current_task', 'Task', 'celery']

logger = get_task_logger(__name__)

broker_url = config.get('celery', 'url')
result_backend = config.get('celery', 'backend')

celery = Celery(
    'geneweaver.tools',
    broker=broker_url,
    backend=result_backend,
    include=[
        'tools.PhenomeMap',
        'tools.GeneSetViewer',
        'tools.Combine',
        # 'tools.HyperGeometric',
        'tools.JaccardSimilarity',
        'tools.JaccardClustering',
        'tools.BooleanAlgebra',
        'tools.TricliqueViewer',
        'tools.ABBA',
        'tools.DBSCAN',
        'tools.MSET',
        'tools.SimilarGenesets',
        'tools.ProcessLargeGeneset'
        # 'tools.UpSet'
    ])

# celery.control.time_limit('tools.SimilarGenesets.SimilarGenesets', soft=0, hard=0, reply=True)

# Optional configuration, see the application user guide.
celery.conf.update(
    task_serializer='json',
    result_serializer="json",
    result_expires=None,
    # Task time limits are now managed in toolbase.py. If they are set here,
    # we can't control limits on a per task basis and this is needed for the
    # SimilarGenesets tool.
    # task_soft_time_limit = 2,
    # task_time_limit = 2,
)

# This doesn't work for whatever reason, it just causes the connection to
# reset
# celery.control.time_limit('tools.SimilarGenesets.SimilarGenesets', soft=90000, hard=9000000, reply=True)
# celery.control.time_limit('tools.SimilarGenesets', soft=90000, hard=9000000, reply=True)
# celery.control.time_limit('SimilarGenesets', soft=90000, hard=9000000, reply=True)

if __name__ == '__main__':
    celery.start()
