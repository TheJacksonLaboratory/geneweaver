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
        return self.render('admin/adminindex.html')

class Viewers(Authentication, BaseView):
    @expose('/')
    def index(self):
        if self.endpoint == 'viewUsers':
	    the_users = geneweaverdb.get_all_users()
            return self.render('admin/adminUserViewer.html', the_users=the_users)
        elif self.endpoint == 'viewPublications':
	    the_pubs = geneweaverdb.get_all_publications()
            return self.render('admin/adminPublicationsViewer.html', the_pubs=the_pubs)
        elif self.endpoint == 'viewGroups':
	    the_groups = geneweaverdb.get_all_groups()
            return self.render('admin/adminGroupViewer.html', the_groups=the_groups)
	elif self.endpoint == 'viewGenesets':
	    genesets = geneweaverdb.get_all_genesets()
            return self.render('admin/adminGenesetViewer.html', genesets=genesets)
	elif self.endpoint == 'viewGenesetInfo':
	    genesets = geneweaverdb.get_all_genesets()
            return self.render('admin/adminGenesetViewer.html', genesets=genesets)
	elif self.endpoint == 'viewGeneInfo':
	    genesets = geneweaverdb.get_all_genesets()
            return self.render('admin/adminGenesetViewer.html', genesets=genesets)
	elif self.endpoint == 'viewProjects':
	    genesets = geneweaverdb.get_all_genesets()
            return self.render('admin/adminGenesetViewer.html', genesets=genesets)
	elif self.endpoint == 'viewGenes':
	    genesets = geneweaverdb.get_all_genesets()
            return self.render('admin/adminGenesetViewer.html', genesets=genesets)
 	else:
	    return self.render('admin/adminindex.html')


