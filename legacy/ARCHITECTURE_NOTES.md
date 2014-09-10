# Web Application Architecture

This is a description of GeneWeaver's web application architecture at a high
level. Note that GeneWeaver depends on several frameworks/technologies that
are not described here, but it is important to understand how these work in
order to understand the GeneWeaver architecture. These are:

* flask + jinja2
* celery + RabbitMQ
* bootstrap + jQuery

## Database Access and Data Representation

Most of the database code can be found in `geneweaverdb.py`. Notice toward the top
of the source code there are objects defined to use `psycopg2s`
`ThreadedConnectionPool`. These should always be used in favor of creating your
own DB connection directly. Note that `PooledCursor` can be used in a
`with` clause as in the following example:

    def get_user(user_id):
        """
        Looks up a User in the database
        :param user_id:     the user's ID
        :return:            the User matching the given ID or None if no such user is found
        """
        with PooledCursor() as cursor:
            cursor.execute('''SELECT * FROM usr WHERE usr_id=%s''', (user_id,))
            users = [User(row_dict) for row_dict in dictify_cursor(cursor)]
            return users[0] if len(users) == 1 else None

This example also uses the `dictify_cursor(...)` function which is a convenient
way to turn a cursor into a sequence of dictionaries. One thing that you have
to be careful to avoid is allowing the `cursor` object to leak outside of the
`with` block since its resources will have already been released at that point.
Note that returning the result of `dictify_cursor(...)` will cause a leak of
this sort to occur because it returns a python generator (ie a lazy sequence).
To avoid this leak you can simply construct a list from the generator as in:
`return list(dictify_cursor(...))`.

The database layer does not use an Object-Relational Mapping (ORM) framework.
Instead simple lists or dictionaries are returned in some instances and in
others cases where data structures were judged too complex to use a simple
dictionary, object representations are added to the code. This approach has
the disadvantage of requiring some extra boiler-plate code to the DB layer, but
allows for more flexibility in how the data is represented given that we are
working with an existing database schema.

## User and Session

When a user registers using the `register.html` template this causes a new user
to be inserted into the `usr` table via the `_form_register()` function.

flask provides a mechansim for having encrypted session data which is stored
as a cookie. GeneWeaver uses this mechanism to store the user ID for the user
that is currently logged in. Note that the encryption of this data relies on
`app.secret_key` remaining secret so for production versions of GeneWeaver
this `app.secret_key` must be changed from the key committed to the repository.
GeneWeaver uses `lookup_user_from_session` in `application.py` to check the
session cookie for a user ID which will then be used to extract a user object
from the database. This user object is then added to `flask.g` which is visible
to jinja2 templates.

## Blueprints

Flask provides blueprints as a mechanism for creating modules within a flask
application. GeneWeaver is currently using blueprints to define seperate
modules for geneset upload/edit/view as well as tool UI components. In general
you should consider using a blueprint if you have a sufficiently self-contained
component that you need to add to the web application.

## Tool Interfaces

GeneWeaver has a seperate repository for back-end development of tools, so this
section only deals with front-end aspects of tool development. You can use the
Geneset Viewer tool as an example for developing new tools.

In this section we will use the `${TOOL_CLASSNAME}` to refer to the name that
uniquely identifies a tool. These names can be found in
`odestatic.tool.tool_classname` in the database for each tool. In order to
present options for your tool you should implement the template found under
`src/templates/tool/${TOOL_CLASSNAME}_options.html`. Notice that in the
`analysis.html` there is a template include tag:
`{% include 'tool/' + tool.classname + '_options.html' %}` which assumes
the option template can be found in this location. Also note that in
`macros.html` there is a `tool_run_button` macro defined as:

    {% macro tool_run_button(tool) %}
        <input
            type='submit'
            value='Run'
            onclick='this.form.action="{{ url_for(tool.classname + '.run_tool') }}";'/>
    {% endmacro %}

This creates a form submit button which directs the form post to your tool
module's `run_tool` function. In this instance `url_for` will only correctly
resolve the `run_tool` function if it is bound to a blueprint whose name is
set to `${TOOL_CLASSNAME}`. To make this concrete we can look at how
`run_tool` is declared in `genesetviewerblueprint.py`:

    TOOL_CLASSNAME = 'GeneSetViewer'
    geneset_viewer_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)
    
    @geneset_viewer_blueprint.route('/run-geneset-viewer.html', methods=['POST'])
    def run_tool():
        ...

You can also look at the code in `genesetviewerblueprint.run_tool` to see how
this module uses celery to send tasks to worker processes and wait for
a response. You can see that a unique URL is used to reference the task ID
corresponding to the active tool run. Also notice that `view_result` will
use `render_tool_pending(...)` to render a status page until the task has
completed.

## Genesets

TODO: fill in description of how genesets work

## Remaining Architectural Work

TODO: fill in details about what needs to be done w.r.t.

* system error messages
* finishing up geneset work
* better statusing for tool tasks
* search functionality

