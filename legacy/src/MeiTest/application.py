from flask import Flask, render_template, url_for, request, session, g, redirect
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
def render_home():
	if 'username' in session:
		return render_template('index.html', title='home', action='home', maintenance_mode=False, persName=session['username'], is_anonymous=False, message='Welcome back ' + session['username'])
	return render_template('index.html', title='home', action='home', maintenance_mode=False, is_anonymous=True, message=False)

@app.route('/manage')
def render_manage():
    return render_template('my_genesets.html')

@app.route("/account/login")
def render_account_login():
	return render_template('login.html', title='Login', maintenance_mode=False, is_anonymous=True)

@app.route("/account/logout")
def render_account_logout():
	session.pop('username', None)
        return render_template('index.html', title='home', action='home', maintenance_mode=False, is_anonymous=True, message="You are now logged out of Geneweaver")


@app.route("/account/reg")
def render_account_reg():
	return render_template('register.html', title='Register', maintenance_mode=False, is_anonymous=True)

@app.route("/account/regcmd", methods=['POST'])
def render_account_regcmd():
	return request.form['persName'];


@app.route("/test")
def test():
	conn = geneweaverdb.pool._connect()
	cursor = conn.cursor()
	cursor.execute("select attname from pg_catalog.pg_attribute")
	result ="%d rows updated" % cursor.rowcount
	return result

@app.route("/test1")
def test1():
        conn = geneweaverdb.pool._connect()
        cursor = conn.cursor()
	result = "Start" 
        cursor.execute("select * from usr")
        return "%d rows updated" % cursor.rowcount

@app.route("/account/logincmd", methods=['POST'])
def login():
	error=None
	if request.method == 'POST':
		usr_email = request.form['useremail']
		usr_email = 'mei.xiao@jax.org'
		conn = geneweaverdb.pool._connect()
		cursor = conn.cursor()
		cursor.execute("select * from usr where usr_email = usr_email")
		if cursor.rowcount == 1:
			session['username'] = request.form['username']
			return redirect(url_for('render_home'))
		else:
			 return "%d row updated" % cursor.rowcount


app.secret_key = "A0ZR98ji/?2Yhz  RX~HKI!JNM8@lajI if'itis tover2102-==lakjdlaskd"
	
if __name__ == '__main__':
    app.run()
