"""
Endpoints to check on the services health
"""
from datetime import datetime
from flask_restx import Namespace, Resource

NS = Namespace(
    "healthcheck", description="Check on the health of Geneweaver Ortholog Normalizer"
)


@NS.route("")
class Healthcheck(Resource):
    """
    Checks whether the server is alive.
    """

    @NS.doc(security=None)
    def get(self):
        return {"status": "Available", "timestamp": datetime.now().isoformat()}
