from flask import Flask, render_template, request
app = Flask(__name__)
app.debug = True

def get_cmd():
	return request.args.get('cmd')

@app.route('/index')
def index():
#       return render_template('test.html', name='meixiaohtmlhello')
#        return render_template('index.html')
 	return get_cmd()


@app.route('/hello')
def hello():
        return 'Hello World, how are you doing'


if __name__ == '__main__':
	app.run()
