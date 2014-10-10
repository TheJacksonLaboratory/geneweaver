from flask import Flask
from flask.ext.admin import Admin, BaseView, expose, AdminIndexView
from flask.ext.admin.contrib.sqla import ModelView
import geneweaverdb
import flask


class Authentication(object):
    def is_accessible(self):
	if "user" in flask.g and flask.g.user.is_admin:
	    return True;
	return False;

class AdminHome(Authentication, AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('adminindex.html')

class Users(Authentication, BaseView):
    @expose('/')
    def index(self):
	return self.render('testAdminView.html')


class ReturnHome(BaseView):
    @expose('/')
    def index(self):
	return flask.render_template('index.html')

