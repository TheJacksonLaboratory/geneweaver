"""
Definition of our API interface
"""

from flask_restx import Namespace, Resource, fields
# TODO: Import functionality from service.py
# from src.service import

# Namespaces group API endpoints
# TODO: Fix namespace name and description
NS = Namespace('examples', description='An example namespace')

# TODO: Replace example code
example_model = NS.model('example', {
    'name': fields.String(),
    'location': fields.Url(),
    'ready': fields.Boolean()
})

EXAMPLES = {
    1: {
        'name': 'delete_me',
        'location': 'https://fakelocation.jax.org',
        'ready': False
    }
}

# Resources
# @NS.route('/')
# class ExampleList(Resource):
#     @NS.doc('list_viewers')
#     @NS.marshal_list_with(example_model)
#     def get(self):
#         return [e for _, e in Examples.items()]
#
#     @NS.doc('create_viewer')
#     @NS.expect(qtlviewer_create_request_model)
#     @NS.marshal_with(qtlviewer_model)
#     def post(self):
#         posted_example = NS.payload
#         # TODO: Act on posted payload
#         return posted_example
#
# @NS.route('/<example_id>')
# class Example(Resource):
#     @NS.doc('get_details_on_viewer')
#     @NS.marshal_with(qtlviewer_model)
#     def get(self, example_id):
#         return EXAMPLES.get(example_id)
# END TODO
