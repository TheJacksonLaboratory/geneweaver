from flask import Flask
from flask.ext.admin import Admin, BaseView, expose, AdminIndexView
import geneweaverdb
import flask
import json


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
	    dbcols=geneweaverdb.get_all_columns('usr')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})

	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newUser", table="production.usr")

        elif self.endpoint == 'viewPublications':
            dbcols=geneweaverdb.get_all_columns('publication')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newPub", table="production.publication")

        elif self.endpoint == 'viewGroups':	          
	    dbcols=geneweaverdb.get_all_columns('grp')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newGroup", table="production.grp")

	elif self.endpoint == 'viewProjects':
            dbcols=geneweaverdb.get_all_columns('project')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newProject", table="production.project")

	elif self.endpoint == 'viewGenesets':
            dbcols=geneweaverdb.get_all_columns('geneset')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newGeneset", table="production.geneset")

	elif self.endpoint == 'viewGenesetInfo':
	    dbcols=geneweaverdb.get_all_columns('geneset_info')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newGenesetInfo", table="production.geneset_info")

	elif self.endpoint == 'viewGeneInfo':
	    dbcols=geneweaverdb.get_all_columns('gene_info')	
	    print dbcols    
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newGeneInfo", table="extsrc.gene_info")

	elif self.endpoint == 'viewGenes':
	    dbcols=geneweaverdb.get_all_columns('gene')
            columns=[]
	    for col in dbcols:
		columns.append({'name': col['column_name']})
	    jcolumns=json.dumps(columns)
            return self.render('admin/adminViewer.html',jcolumns=jcolumns, columns=columns , route="newGene", table="extsrc.gene")

 	else:
	    return self.render('admin/adminindex.html')

class Add(Authentication, BaseView):
    @expose('/adminAdd', methods=('GET','POST' ))
    @expose('/')
    def index(self):
        if self.endpoint == 'newUser':
	    columns = geneweaverdb.get_table_columns('usr')
            return self.render('admin/adminAdd.html', columns=columns, toadd="User", table="production.usr")
        elif self.endpoint == 'newPub':
 	    columns = geneweaverdb.get_table_columns('publication')
            return self.render('admin/adminAdd.html', columns=columns, toadd="Publication", table="production.publication")
        elif self.endpoint == 'newGeneset':
	    columns = geneweaverdb.get_table_columns('geneset')
	    return self.render('admin/adminAdd.html', columns=columns, toadd="Geneset", table="production.geneset")
        elif self.endpoint == 'newProject':
	    columns = geneweaverdb.get_table_columns('project')
	    return self.render('admin/adminAdd.html', columns=columns, toadd="Project", table="production.project")
	elif self.endpoint == 'newGene':
	    columns = geneweaverdb.get_table_columns('gene')
	    return self.render('admin/adminAdd.html', columns=columns, toadd="Gene", table="extsrc.gene")
	elif self.endpoint == 'newGenesetInfo':
	    columns = geneweaverdb.get_table_columns('geneset_info')
	    return self.render('admin/adminAdd.html', columns=columns, toadd="Geneset Info", table="production.geneset_info")
	elif self.endpoint == 'newGeneInfo':
	    columns = geneweaverdb.get_table_columns('gene_info')
	    return self.render('admin/adminAdd.html', columns=columns, toadd="Gene Info", table="extsrc.gene_info")
	elif self.endpoint == 'newGroup':
	    columns = geneweaverdb.get_table_columns('grp')
	    return self.render('admin/adminAdd.html', columns=columns, toadd="Group", table="production.grp")
        else:
	    return self.render('admin/adminindex.html')


