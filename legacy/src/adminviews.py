from flask import Flask
from flask.ext.admin import Admin, BaseView, expose, AdminIndexView
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
            return self.render('admin/adminUserViewer.html')
        elif self.endpoint == 'viewPublications':
            return self.render('admin/adminPublicationsViewer.html')
        elif self.endpoint == 'viewGroups':
	    the_groups = geneweaverdb.get_all_groups()
            return self.render('admin/adminGroupViewer.html', the_groups=the_groups)
	elif self.endpoint == 'viewGenesets':
            return self.render('admin/adminGenesetViewer.html')
	elif self.endpoint == 'viewGenesetInfo':
	    genesetsinfo = geneweaverdb.get_all_geneset_info()
            return self.render('admin/adminGenesetInfoViewer.html', genesetsinfo=genesetsinfo)
	elif self.endpoint == 'viewGeneInfo':
	    genesinfo = geneweaverdb.get_all_gene_info()
            return self.render('admin/adminGeneInfoViewer.html', genesinfo=genesinfo)
	elif self.endpoint == 'viewProjects':
            return self.render('admin/adminProjectViewer.html')
	elif self.endpoint == 'viewGenes':
	    genes = geneweaverdb.get_all_genes()
            return self.render('admin/adminGeneViewer.html', genes=genes)
 	else:
	    return self.render('admin/adminindex.html')

class Add(Authentication, BaseView):
    @expose('/')
    def index(self):
        if self.endpoint == 'newUser':
	    columns = geneweaverdb.get_table_columns('usr')
            return self.render('admin/add.html', columns=columns)
        elif self.endpoint == 'newPub':
 	    columns = geneweaverdb.get_table_columns('publication')
            return self.render('admin/add.html', columns=columns)
        elif self.endpoint == 'newGeneset':
	    columns = geneweaverdb.get_table_columns('geneset')
	    return self.render('admin/add.html', columns=columns)
        elif self.endpoint == 'newProject':
	    columns = geneweaverdb.get_table_columns('project')
	    return self.render('admin/add.html', columns=columns)
	elif self.endpoint == 'newGene':
	    columns = geneweaverdb.get_table_columns('gene')
	    return self.render('admin/add.html', columns=columns)
	elif self.endpoint == 'newGenesetInfo':
	    columns = geneweaverdb.get_table_columns('geneset_info')
	    return self.render('admin/add.html', columns=columns)
	elif self.endpoint == 'newGeneInfo':
	    columns = geneweaverdb.get_table_columns('gene_info')
	    return self.render('admin/add.html', columns=columns)
	elif self.endpoint == 'newGroup':
	    columns = geneweaverdb.get_table_columns('grp')
	    return self.render('admin/add.html', columns=columns)
        else:
	    return self.render('admin/adminindex.html')


