## This file contains all of the exception handling code for this application.
## The app is designed to fail gracefully, presenting the user with a nice
## message and redirecting them back to where they were, while emailing an
## administrator about the nature of the error.
#
import flask
import logging
import sys
import traceback
from datetime import datetime
from flask import request, session

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
    stack = 'Stack trace:\n'

    for ln in traceback.format_stack():
        stack += '\t' + ln

    if session and 'usr_id' in session:
        usr_id = session['usr_id']
    else:
        usr_id = 'Guest'

    info = info % (request.url, request.method, request.remote_addr,
                   request.headers['User-Agent'], datetime.now(), usr_id, e)

    if not request.args:
        args = 'Request args: None'
    else:
        args = 'Request args:\n'

        for key, val in request.args.items():
            key = key.encode('ascii', 'ignore')
            val = val.encode('ascii', 'ignore')
            args += '\t%s: %s\n' % (key, val)

    if not request.form:
        form = 'Form data: None'
    else:
        form = 'Form data:\n'

        for key, val in request.form.items():
            key = key.encode('ascii', 'ignore')
            val = val.encode('ascii', 'ignore')
            form += '\t%s: %s\n' % (key, val)

    #msg = stack + '\n' + info + '\n\n' + args + '\n\n' + form
    msg = info + '\n' + args + '\n\n' + form + '\n\n' + stack

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
