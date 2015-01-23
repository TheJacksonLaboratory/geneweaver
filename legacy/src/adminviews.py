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
            table = 'production.usr'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})

            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newUser",
                               table=table)

        elif self.endpoint == 'viewPublications':
            table = 'production.publication'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newPub",
                               table=table)

        elif self.endpoint == 'viewGroups':
            table = 'production.grp'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGroup",
                               table=table)

        elif self.endpoint == 'viewProjects':
            table = 'production.project'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newProject",
                               table=table)

        elif self.endpoint == 'viewGenesets':
            table = 'production.geneset'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGeneset",
                               table=table)

        elif self.endpoint == 'viewGenesetInfo':
            table = 'production.geneset_info'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGenesetInfo",
                               table=table)

        elif self.endpoint == 'viewGeneInfo':
            table = 'extsrc.gene_info'
            dbcols = geneweaverdb.get_all_columns(table)
            print dbcols
            columns = []
            # for col in dbcols:
            #	columns.append({'name': col['column_name']})

            columns = [{'name': 'ode_gene_id'}, {'name': 'gi_accession'}, {'name': 'gi_symbol'}, {'name': 'gi_name'},
                       {'name': 'gi_description'}, {'name': 'gi_type'}, {'name': 'gi_chromosome'},
                       {'name': 'gi_start_bp'}, {'name': 'gi_end_bp'}, {'name': 'gi_strand'}, {'name': 'sp_id'},
                       {'name': 'gi_date'}]
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGeneInfo",
                               table=table)

        elif self.endpoint == 'viewGenes':
            table = 'extsrc.gene'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGene",
                               table=table)

        elif self.endpoint == 'viewFiles':
            table = 'production.file'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGene",
                               table=table)

        elif self.endpoint == 'viewGenesetVals':
            table = 'extsrc.geneset_value'
            dbcols = geneweaverdb.get_all_columns(table)
            columns = []
            for col in dbcols:
                if col['column_name'] != 'gsv_value' and col['column_name'] != 'gsv_value_list':
                    columns.append({'name': col['column_name']})
            jcolumns = json.dumps(columns)
            return self.render('admin/adminViewer.html', jcolumns=jcolumns, columns=columns, route="newGene",
                               table=table)

        else:
            return self.render('admin/adminindex.html')


# Add endpoints that render input form using table columns that are not auto increment
class Add(Authentication, BaseView):
    @expose('/')
    def index(self):
        if self.endpoint == 'newUser':
            table = "production.usr"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="User",
                               table=table)

        elif self.endpoint == 'newPub':
            table = "production.publication"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Publication",
                               table=table)

        elif self.endpoint == 'newGeneset':
            table = "production.geneset"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Geneset",
                               table=table)

        elif self.endpoint == 'newProject':
            table = "production.project"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Project",
                               table=table)

        elif self.endpoint == 'newGenesetInfo':
            table = "production.geneset_info"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Geneset Info",
                               table=table)

        elif self.endpoint == 'newGroup':
            table = "production.grp"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Group",
                               table=table)

        elif self.endpoint == 'newGene':
            table = "extsrc.gene"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Gene",
                               table=table)

        elif self.endpoint == 'newGeneInfo':
            table = "extsrc.gene_info"
            columns = geneweaverdb.get_nullable_columns(table)
            requiredCols = geneweaverdb.get_required_columns(table)
            return self.render('admin/adminAdd.html', columns=columns, requiredCols=requiredCols, toadd="Gene Info",
                               table=table)

        else:
            return self.render('admin/adminindex.html')
