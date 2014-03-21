from flask import Flask, render_template
import collections
import geneweaverdb

app = Flask(__name__)
app.debug = True

newsArray = [("1", "One"), ("2", "Two"), ("3", "Three")]

def ode_link(action='', cmd='', other=''):

    url = 'index.html' if action == 'home' or not action else action + '.html'

    if cmd:
        url += '&cmd=' + cmd
    if other:
        url += '&' + other

    return url

def get_cmd():
    return flask.request.args.get('cmd')

@app.context_processor
def inject_globals():
    # TODO you need to care about escaping
    return {
        'ode_link': ode_link,
        'title': '',
        'topmenu': collections.OrderedDict([
            (ode_link('home'), 'Home'),
            (ode_link('search'), 'Search'),
            (ode_link('manage'), 'Manage GeneSets'),
            (ode_link('analyze'), 'Analyze GeneSets'),
            (ode_link('help', 'view', 'docid=acknowledgements'), 'About'),
        ]),
        'topsubmenu': {
            'Home': dict(),
            'About': dict(),
            'Search': collections.OrderedDict([
                (ode_link('search'), 'for GeneSets'),
                (ode_link('search', 'genes'), 'for Genes (ABBA)'),
            ]),
            'Manage GeneSets': collections.OrderedDict([
                (ode_link('manage', 'listgenesets'), 'My GeneSets'),
                (ode_link('manage', 'uploadgeneset'), 'Upload GeneSet'),
                (ode_link('manage', 'batchgeneset'), 'Batch Upload GeneSets'),
            ]),
            'Analyze GeneSets': collections.OrderedDict([
                (ode_link('analyze'), 'My Projects'),
                (ode_link('analyze', 'shared'), 'Shared Projects'),
                (ode_link('analyze', 'listresults'), 'Results'),
            ]),
        },
        'newsArray': newsArray,
        'persName': 'TODO ADD NAME',
    }

@app.route("/index")
def render_home_template():
    return render_template('index.html', title='meixiao', maintenance_mode=False, is_anonymous=True)

@app.route('/manage')
def render_manage():
    return render_template('my_genesets.html')


@app.route("/test")
def test():
	conn = geneweaverdb.pool._connect()
	cursor = conn.cursor()
	cursor.execute("select attname from pg_catalog.pg_attribute")
	result ="%d rows updated" % cursor.rowcount
	return result

if __name__ == '__main__':
    app.run()
