import flask

jaccardclustering_blueprint = flask.Blueprint('JaccardClustering', __name__)

@jaccardclustering_blueprint.route('/run-jaccard-clustering.html')
def run_tool():
    pass
