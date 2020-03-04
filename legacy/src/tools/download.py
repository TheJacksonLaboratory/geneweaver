#!/usr/bin/python

#Updated by Sam Itskin on 11/30/2015
#bare bones implementation of a CGI script
# converts using svg2rlg and renderPDF.drawToFile

import tempfile
import cgi
import StringIO

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM


inputFile = tempfile.NamedTemporaryFile("w+b")
outFile = StringIO.StringIO()


#this assuming using data tag for svg and output_format tag for the end format
form = cgi.FieldStorage()
formsvg = form.getvalue('data')
outFormat = form.getvalue('output_format')
inputFile.write(str(formsvg))
inputFile.flush()

drawing = svg2rlg(inputFile.name)

#for other output formats add on to the if statement with your desired format and code
if(outFormat == 'bmp'):
	print("Content-Disposition: attachment; filename=\"img.bmp\"\r\n")
	renderPM.drawToFile(drawing, outFile.name, dpi=600)

bmpOut = outFile.read()

print(bmpOut)

outFile.close()
inputFile.close()
