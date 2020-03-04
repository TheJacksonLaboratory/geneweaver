## This file contains all of the exception handling code for this application.
## The app is designed to fail gracefully, presenting the user with a nice
## message and redirecting them back to where they were, while emailing an
## administrator about the nature of the error.
#
# TODO: Should be deprecated with python2
from __future__ import print_function

import flask
import smtplib
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from flask import request, session
from sys import exc_info

## List of people to email about errors
DEVS = ['timothy_reynolds@baylor.edu']

def write_sos(msg):
    """
    A backup function that is called when sending an error email fails.
    Appends the error message to a file.
    """

    with open('gw-exceptions.txt', 'a') as fl:
        print('', file=fl)
        print(msg, file=fl)

def send_sos(msg):
    """
    Sends an email to a list of people with details about an error that
    occurred.
    """

    me = 'sos@geneweaver.org'

    emsg = MIMEText(msg)
    emsg['Subject'] = 'GeneWeaver needs your help!'
    emsg['From'] = me
    emsg['To'] = ', '.join(DEVS)

    try:
        s = smtplib.SMTP('localhost')
        s.sendmail(me, DEVS, emsg.as_string())
        s.quit()

    ## The most common reason for this failing is the SMTP server isn't running
    except Exception as e:
        write_sos('Email failed with ' + str(e))
        write_sos(msg)

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
    exception = traceback.format_exception_only(e[0], e[1])[0]

    #for ln in traceback.format_stack(limit=40):
    #for ln in traceback.format_exception(*e):
    for ln in traceback.format_tb(e[2]):
        stack += '\t' + ln

    asciisession = {}

    ## Damn unicode shitting over everything
    for key, val in session.items():
        if type(key) == unicode:
            key = key.encode('ascii', 'ignore')

        if type(val) == unicode:
            val = val.encode('ascii', 'ignore')

        asciisession[key] = val

    if asciisession and 'usr_id' in asciisession:
        usr_id = asciisession['usr_id']
    ## There's seriously a fucking page somewhere that puts user_id instead
    ## of usr_id. I have yet to find it.
    elif asciisession and 'user_id' in asciisession:
        usr_id = asciisession['user_id']
    else:
        usr_id = 'Guest'

    info = info % (request.url, request.method, request.remote_addr,
                   request.headers['User-Agent'], datetime.now(), usr_id,
                   exception)

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

    ## This grabs the exception info and traceback for the last exception
    ## that occurred. If we give the exception/traceback passed to this
    ## function (argument e), the stack trace will be incorrect when we
    ## later print it.
    exc = exc_info()

    errmsg = format_error_message(exc)
    send_sos(errmsg)

    return flask.render_template('error/500.html')

