import flask

phenomemap_blueprint = flask.Blueprint('PhenomeMap', __name__)

@phenomemap_blueprint.route('/run-phenome-map.html')
def run_tool():
    pass