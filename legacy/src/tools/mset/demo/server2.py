import os
from flask import Flask, request, redirect, url_for
from werkzeug import secure_filename
from subprocess import Popen, PIPE

UPLOAD_FOLDER = '/svr/demo'
ALLOWED_EXTENSIONS = set(['txt'])
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route("/results", methods=['GET'])
def results():
    global runningProcess
    current="nothing yet..."
    try:
        myfile=open('msetOutput.txt','r')
        current=myfile.read().replace('\n','<br/>')
    except IOError as e:
        print "file not ready yet..."
    return """
    <!doctype html>
    <meta http-equiv="refresh" content="1; url=/results" />
    <title>Upload new File</title>
    <img src="static/header.png"/>
    <h1>results</h1>
    <table border=1 style="font-family:Courier New;">
    <tr>
    <td>
    %s<br/>
    %s
    </td>
    </tr>
    """ % ("&nbsp"*80,current)

@app.route("/", methods=['GET', 'POST'])
def index():
    global runningProcess
    if request.method == 'POST':
        file = request.files['file']
        testNum= request.form['numToTest']
        samples= request.form['numSamples']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            runningProcess=Popen(['/svr/demo/prog', testNum, samples, '%s/%s' %
                (UPLOAD_FOLDER,filename)],stdout=PIPE, stderr=PIPE)
            return redirect(url_for('results'))
    return """
    <!doctype html>
    <title>Upload new File</title>
    <img src="static/header.png"/>
    <h1>Upload new File</h1>
    <form action="" method=post enctype=multipart/form-data>
      <table>
      <tr>
      <td>
          <table>
          <tr><td>geneset to test</td></tr>
          <tr><td><input type=file name=file></td></tr>
          </table>
      </td>
      <td>
          <table>
          <tr><td>number of results<br/>to test with</td></tr>
          <tr><td><input type=number name=numToTest></td></tr>
          </table>
      </td>
      <td>
          <table>
          <tr><td>number of samples<br/>to generate</td></tr>
          <tr><td><input type=number name=numSamples></td></tr>
          </table>
      </td>
      <td>
         <input type=submit value=Upload>
      </td>
      </tr>
      </table>
    </form>
    """

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
