## This file contains all of the exception handling code for this application.
## The app is designed to fail gracefully, presenting the user with a nice
## message and redirecting them back to where they were, while emailing an
## administrator about the nature of the error.
#
import flask
import logging
import sys
from datetime import datetime
from flask import request, session
from logging import StreamHandler
from logging import Formatter

stream_handler = StreamHandler(sys.stdout)
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(Formatter('''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
'''))

#app = flask.Flask(__name__)

def format_error_message(e):
    """
    Formats message containing information about the exception that
    occurred and the circumstances that caused it.
    """
    info = '''
URL:            %s
Request type:   %s
IP:             %s
User agent:     %s
Time:           %s
User ID:        %s
Exception:      %s
'''
    args = ''
    form = ''

    if session and 'usr_id' in session:
        usr_id = session['usr_id']
    else:
        usr_id = 'Guest'

    info = info % (request.url, request.method, request.remote_addr,
                   request.headers['User-Agent'], datetime.now(), usr_id, e)

    if not request.args:
        args = 'Request args: None'
    else:
        args = 'Request args: ' + str(request.args)

    if not request.form:
        form = 'Form data: None'
    else:
        form = 'Form data: ' + str(request.form)

    msg = info + '\n' + args + '\n\n' + form

    return msg

def bad_request(e):
    """
    Handles 400 (bad request) errors, redirecting users to the 400 page.
    Occurs when a user's browser sends a bad or malformed request the server
    can't process.
    """

    return flask.render_template('error/400.html')

def unauthorized(e):
    """
    Handles 401 (unauthorized) errors, redirecting users to the 401 page.
    Occurs when users visit a page prior to authenticating.
    """

    return flask.render_template('error/401.html')

def forbidden(e):
    """
    Handles 403 (forbidden) errors, redirecting users to the 403 page.
    Occurs when users visit a page or directory that can't be accessed from
    the website.
    """

    return flask.render_template('error/403.html')

def page_not_found(e):
    """
    Handles 404 (page not found) errors, redirecting users to the 404 page.
    """

    return flask.render_template('error/404.html')

def internal_server_error(e):
    """
    Handles 500 (internal server) errors. This is basically a catch all,
    handling any and all exceptions that aren't previously handled using the
    above functions. Since these are generally more severe (e.g. some
    application component has shit the bed), the function shoots off a couple
    emails containing urls, stack traces, and user information.
    """

    print format_error_message(e)

    return flask.render_template('error/500.html')
