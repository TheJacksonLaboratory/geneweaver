# -*- coding: utf-8 -*-
"""wsgi
~~~~.

pfs_api wsgi module
"""
from geneweaver.aon.factory import create_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

app = create_app()
application = DispatcherMiddleware(app)

try:
    import uwsgi

    def postfork():
        app.config["db_engine"].dispose()

    uwsgi.post_fork_hook = postfork

except ImportError:
    pass

if __name__ == "__main__":
    run_simple("localhost", 8000, application, use_reloader=True, use_debugger=True)
