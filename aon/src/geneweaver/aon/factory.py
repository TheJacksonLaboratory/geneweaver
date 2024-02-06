"""
Factory for the flask app
"""

import logging
from flask import Flask
from flask_cors import CORS
from flask_restx import Api
from sqlalchemy.orm import scoped_session

# from cli import run_tests
from geneweaver.aon.auth import AUTHORIZATIONS
from geneweaver.aon.config import Config
from geneweaver.aon.database import SessionLocal
from geneweaver.aon.controller import NS as AGR
from geneweaver.aon.healthcheck import NS as HEALTH_CHECK
from geneweaver.aon.exceptions import AuthError


def create_app(app=None):
    """
    Create an instance of a flask app
    :param app: existing app if initialized
    :return:
    """

    app = app or Flask(__name__, static_url_path='/static', static_folder='static')

    app.config.from_object(Config)

    app.app_context().push()

    logging.basicConfig(level=app.config['LOG_LEVEL'])

    api = Api(
        title=app.config['TITLE'],
        version=app.config['VERSION'],
        description=app.config['DESCRIPTION'],
        authorizations=AUTHORIZATIONS
    )

    # Add our service and healthcheck endpoints
    api.add_namespace(HEALTH_CHECK)
    api.add_namespace(AGR)

    api.init_app(app)

    with app.app_context():
        CORS(app)

    app.session = scoped_session(SessionLocal)

    @app.teardown_request(Exception)
    def close_session():
        app.session.close()
        return {'message':'END'}

    # Handle Auth Errors
    @api.errorhandler(AuthError)
    def handle_auth_error(ex):
        return {'message': ex.error['description']}, ex.status_code

    # Add CLI
    # app.cli.add_command(run_tests)

    return app
