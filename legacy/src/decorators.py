from functools import wraps, update_wrapper
import geneweaverdb
import flask


def login_required(json=False, allow_guests=False):
    """
    A factory/decorator to handle login logic for both html and json routes.
    :param json: A boolean value indicating if the request is html or json.
    :param allow_guests: A boolean indicating if this view allows users that are not registered
    :return: The decorator with the applicable json setting.
    """
    def decorator(f):
        def wrapped(*args, **kwargs):
            if flask.g.user is None or (flask.g.user.is_guest and allow_guests):
                if json:
                    return flask.jsonify({"error": "You must be signed in to perform this action"})
                else:
                    return flask.redirect(flask.url_for('register_or_login'))
            return f(*args, **kwargs)
        return update_wrapper(wrapped, f)
    return decorator


def restrict_to_current_user(f):
    """
    This is a decorator which checks that the user_id associated with a request argument matches the user_id of the
    session. This is useful when you want to make sure that a user is only affecting settings they own.
    :param f: The function to decorate.
    :return: The decorated function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        req_uid = int(flask.request.args['user_id'])
        ses_uid = int(flask.session.get('user_id'))
        if req_uid != ses_uid:
            flask.abort(403)
        return f(*args, **kwargs)
    return decorated


def create_guest(f):
    """
    This is a decorator to create a new guest and register it with the session.
    :param f: The function to decorate.
    :return: The decorated function.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if flask.g.user is None:
            user = geneweaverdb.new_guest()
            if user is not None:
                flask.g.user = user
                flask.session['user_id'] = user.user_id
                remote_addr = flask.request.remote_addr
                if remote_addr:
                    flask.session['remote_addr'] = remote_addr
        return f(*args, **kwargs)
    return decorated

