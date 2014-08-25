import flask

jaccardsimilarity_blueprint = flask.Blueprint('JaccardSimilarity', __name__)

@jaccardsimilarity_blueprint.route('/run-jaccard-similarity.html')
def run_tool():
    pass
