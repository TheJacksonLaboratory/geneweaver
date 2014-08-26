from celery import Celery

BROKER_URL = 'amqp://guest@localhost//'
CELERY_RESULT_BACKEND = 'db+sqlite:////Users/kss/projects/GeneWeaver/results.db'

celery_app = Celery(
    'geneweaver.tools',
    broker=BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Optional configuration, see the application user guide.
celery_app.conf.update(
    CELERY_TASK_SERIALIZER='json',
    CELERY_RESULT_SERIALIZER='json',
    CELERY_TASK_RESULT_EXPIRES=None,
    CELERYD_TASK_SOFT_TIME_LIMIT=600,
    CELERYD_TASK_TIME_LIMIT=600,
)

geneset_html_id_prefix = "geneset_"


def selected_geneset_ids(form):
    """
    this function takes a submitted form and extracts IDs for
    all selected geneset checkboxes
    :param form:    flask form (as in flask.request.form)
    :return: the list of geneset IDs
    """
    prefix_len = len(geneset_html_id_prefix)
    return [
        id_with_prefix[prefix_len:]
        for id_with_prefix in form.iterkeys()
        if id_with_prefix.startswith(geneset_html_id_prefix)
    ]

def fully_qualified_name(tool_class_name):
    """
    Takes the given tool classname and returns the fully-qualified
    version. Suitable for use with send_task
    :param tool_class_name: the tool classname
    :return: the fully qualified name
    """
    return 'tools.' + tool_class_name + '.' + tool_class_name