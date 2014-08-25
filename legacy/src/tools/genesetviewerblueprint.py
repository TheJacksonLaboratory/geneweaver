import flask

from tools import toolcommon


geneset_viewer_blueprint = flask.Blueprint('GeneSetViewer', __name__)

@geneset_viewer_blueprint.route('/run-geneset-viewer.html', methods=['POST'])
def run_tool():
    form = flask.request.form

    print form

    # pull out the selected geneset IDs
    selected_geneset_ids = toolcommon.selected_geneset_ids(form)
    print 'selected IDs: ', selected_geneset_ids

    return "hi world"