#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import re
import sys
import math
import time
import json
import decimal
import hashlib
import logging
import logging.handlers
import psycopg2
import datetime
from flask import Flask, request, url_for, session, render_template, redirect, flash, abort
if sys.version_info[0] < 3:
    # TODO: Should be deprecated with python2
    from urllib2 import urlopen
else:
    from urllib.request import urlopen

## 2016.03.21 - new version of the NCBO Annotator
## Will replace the NCBO related functions found in this file.
import ncbo
import monarch as mi

app = Flask(__name__)
app.config.from_envvar('GENEWEAVER_CONFIG')
dbcon = psycopg2.connect(app.config['DB_CONNECT_STRING'])

#fh = logging.handlers.RotatingFileHandler(app.config['LOG_DIR']+'curation_server.log', maxBytes=10*1024*1024)
#fh.setLevel(getattr(logging, app.config['LOG_LEVEL']))
#fh.setFormatter(logging.Formatter('%%(asctime)s %12s:%%(levelname)-8s | %%(message)s' % ('curation',)))
#app.logger.addHandler(fh)

def login():
  user_email = request.form.get('email')
  passwd = request.form.get('password')
  if user_email is not None and passwd is not None:
    cur = dbcon.cursor()
    cur.execute('''SELECT u.usr_id,u.usr_email,g.grp_name,g.grp_id
       FROM production.usr u,production.grp g,production.usr2grp x
      WHERE usr_email=%s AND usr_password=%s AND u.usr_id=x.usr_id
        AND g.grp_id=x.grp_id AND u2g_privileges=1;''',
        (user_email,hashlib.md5(passwd).hexdigest()))
    #cur.execute('''SELECT u.usr_id,u.usr_email,g.grp_name,g.grp_id
    #   FROM production.usr u,production.grp g,production.usr2grp x
    #  WHERE usr_email=%s AND usr_password=%s AND u.usr_id=x.usr_id
    #    AND g.grp_id=x.grp_id AND x.u2g_status=2 AND u2g_privileges=1;''',
    #    (user_email,hashlib.md5(passwd).hexdigest()))

    if 'user_id' in session:
      del session['user_id']
    if 'user_email' in session:
      del session['user_email']
    session['groups']={}
    for row in cur:
      session['user_id']=row[0]
      session['user_email']=row[1]
      session['groups'][str(row[3])]=row[2]
      session['curgrp']='0'
      session['curstat']='1'
      session['curtier']='4'

    cur.execute('SELECT cur_id,cur_name FROM odestatic.curation_levels;')
    tiers = {}
    for row in cur:
      tiers[ str(row[0]) ] = row[1]
    session['tiers']=tiers

    cur.execute('SELECT stid,name,ordercode FROM gwcuration.status_types;')
    stati = {}
    stato = {}
    for row in cur:
      stati[ str(row[0]) ] = row[1]
      stato[ row[2] ] = str(row[0])
    session['stati']=stati
    session['stato']=[stato[x] for x in sorted(stato.keys())]

    if 'user_id' in session:
      return redirect(url_for('list_stubs'))
    flash('Invalid login - please check your Email and password', 'error')
  elif user_email is not None or passwd is not None:
    flash('Email and password must be provided', 'error')

  return render_template('login.html')

def list_generators():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  cur = dbcon.cursor()
  if request.args.get('refresh','')!='':
    refresh_stubs(cur, request.args.get('refresh'))
    return redirect(url_for('list_generators'))

  if request.args.get('delete','')!='':
    cur.execute('DELETE FROM gwcuration.stubgenerators WHERE name=%s AND usr_id=%s;',
        (request.args.get('delete').strip(), int(session['user_id'])))
    dbcon.commit()
    flash('Generator deleted.', 'info')
    return redirect(url_for('list_generators'))

  if request.form.get('name','')!='':
    cur.execute('INSERT INTO gwcuration.stubgenerators (name,querystring,grp_id,usr_id) values (%s,%s,%s,%s);',
        (request.form.get('name').strip(), request.form.get('querystring').strip(),
          int(request.form.get('forgroup')), int(session['user_id'])))
    dbcon.commit()
    flash('New Generator created!', 'info')

  cur.execute('SELECT name,querystring,last_update,grp_id FROM gwcuration.stubgenerators WHERE usr_id=%s OR grp_id=ANY(%s);',
      (int(session['user_id']), '{'+','.join(session['groups'].keys())+'}' ))
  gens=[]
  for row in cur:
    g = {'name': row[0], 'query': row[1], 'updated': row[2], 'group': session['groups'][str(row[3])]}
    gens.append(g)

  return render_template('list_generators.html', list=gens)

def list_stubs():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  cur = dbcon.cursor()

  chgchk = (None,None)
  if 'curstat' in session and 'curgrp' in session:
    chgchk = (session['curstat'],session['curgrp'])

  curstat=request.args.get('stat')
  if curstat is None and 'curstat' in session:
    curstat = session['curstat']

  if curstat is None or curstat not in session['stati']:
    # default to unreviewed
    curstat = '0'
  session['curstat'] = curstat

  curgrp = request.args.get('grp')
  if curgrp is None and 'curgrp' in session:
    curgrp = session['curgrp']

  curgrps = session['groups'].keys()
  if curgrp is None or curgrp not in session['groups']:
    # default to all groups
    curgrp = '0'
  else:
    curgrps = [curgrp]
  session['curgrp'] = curgrp

  if chgchk != (session['curstat'],session['curgrp']) and request.args.get('page','1')!='1':
    del session['num_results']
    del session['pages']
    del session['page']
    return redirect( url_for('list_stubs', stat=session['curstat'], grp=session['curgrp']) )

  cur.execute('''SELECT COUNT(stubid),stid FROM gwcuration.stub_status
      WHERE grp_id=ANY(%s) GROUP BY stid;''',
      ('{'+','.join(curgrps)+'}',))
  stati_counts={}
  for stid in session['stati']:
    stati_counts[stid]=0
  for row in cur:
    stati_counts[str(row[1])]=row[0]

  cur.execute('''SELECT ss.stubid,ss.status_comment,ss.priority,ss.rank,ss.grp_id,sg.name
      FROM gwcuration.stub_status ss,gwcuration.stubgenerators sg
      WHERE ss.stid=%s AND ss.grp_id=ANY(%s) AND sg.stubgenid=ss.stubgenid
      ORDER BY ss.priority DESC, ss.rank DESC, ss.stubid ASC;''',
      (int(curstat), '{'+','.join(curgrps)+'}' ))

  if chgchk != (session['curstat'],session['curgrp']) or 'num_results' not in session:
    session['num_results'] = cur.rowcount
    session['pages'] = cur.rowcount/25
    if cur.rowcount%25 > 0:
      session['pages']+=1
    session['page']=1
  elif request.args.get('page','1')!=str(session['page']):
    session['page']=int(request.args.get('page','1'))

  stubs={}
  try:
    cur.scroll(25*(int(session['page'])-1))
  except (psycopg2.ProgrammingError, IndexError) as exc:
    if cur.rowcount>0:
      abort(404)

  for row in cur.fetchmany(25):
    stubs[str(row[0])] = {'stubid': row[0], 'comment': row[1], 'priority': row[2], 'rank': row[3], 'group': session['groups'][str(row[4])], 'stubgenerator': row[5]}
    stubs[str(row[0])]['status'] = session['stati'][ curstat ]
    stubs[str(row[0])]['mod_url'] = url_for('mod_stub', stubid=row[0], grpid=row[4])
    stubs[str(row[0])]['view_url'] = url_for('view_stub', stubid=row[0])
    stubs[str(row[0])]['geneset_count'] = 0

  pmids={}
  cur.execute('SELECT stubid,title,abstract,authors,pubinfo,pmid,link_to_fulltext,added_on FROM gwcuration.stubs WHERE stubid=ANY(%s);', ('{'+','.join(stubs)+'}',))
  for row in cur:
    stubs[str(row[0])]['atitle'] = row[1].decode('utf-8')
    stubs[str(row[0])]['abstract'] = row[2].decode('utf-8')
    stubs[str(row[0])]['authors'] = row[3].decode('utf-8')
    stubs[str(row[0])]['pubinfo'] = row[4].decode('utf-8')
    stubs[str(row[0])]['pmid'] = row[5]
    stubs[str(row[0])]['fulltext'] = row[6]
    stubs[str(row[0])]['added'] = row[7]
    if row[5] not in pmids:
      pmids[row[5]]=set()
    pmids[row[5]].add(str(row[0]))

  cur.execute('''SELECT gs_id,pub_pubmed FROM production.geneset g,production.publication p where g.pub_id=p.pub_id AND pub_pubmed=ANY(%s) AND cur_id<=4 AND gs_groups='0' AND gs_status not like 'de%%';''',
      ('{'+','.join(pmids.keys())+'}',))
  for row in cur:
    for stub in pmids[row[1]]:
      stubs[stub]['geneset_count']+=1 

  def _sorter(a,b):
    p = b['priority']-a['priority']
    if p!=0:
      return p
    r = a['rank']-b['rank']
    if r!=0:
      return r

    if a['added']>b['added']:
      return -1
    if a['added']<b['added']:
      return 1
    return 0
  stubs = sorted(stubs.values(), cmp=_sorter)

  return render_template('list_stubs.html', list=stubs, stati_counts=stati_counts)

def add_manual_stubs(cur, pmids, grp_id, priority):
  import urllib

  cur.execute('SELECT stubgenid FROM gwcuration.stubgenerators WHERE name=\'Manual\' AND grp_id=%s;', (grp_id,))
  row = cur.fetchone()
  if row is None:
    cur.execute('INSERT INTO gwcuration.stubgenerators (name,querystring,grp_id) VALUES (\'Manual\',\'-\',%s) RETURNING stubgenid;',
      (grp_id,))
    row = cur.fetchone()

  geninfo = {'name':'Manual','querystring':'-','grp_id':grp_id,'stubgenid':row[0]}

  PM_DATA = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml'
  response = urlopen(PM_DATA % (','.join([str(x) for x in pmids]),)).read()

  _process_pubmed_response(cur,geninfo,response, priority)

  return geninfo['stubgenid']

def refresh_stubs(cur,genname):
  import urllib

  cur.execute('SELECT name,querystring,grp_id,stubgenid FROM gwcuration.stubgenerators WHERE name=%s AND (usr_id=%s OR grp_id=ANY(%s));',
    (genname, int(session['user_id']), '{'+','.join(session['groups'].keys())+'}' ))
  row = cur.fetchone()
  geninfo = {'name':row[0],'querystring':row[1],'grp_id':row[2],'stubgenid':row[3]}

  PM_SEARCH  = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=%s&usehistory=y'
  response = urlopen(PM_SEARCH % (urllib.quote(geninfo['querystring']),)).read()
  QueryKey = re.search('<QueryKey>([0-9]*)</QueryKey>', response).group(1)
  WebEnv = re.search('<WebEnv>([^<]*)</WebEnv>', response).group(1)
  count = re.search('<Count>([0-9]*)</Count>', response).group(1)

  # TODO: batch download these instead of all-at-once (10k max)
  #PM_DATA = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&usehistory=y&query_key=%s&WebEnv=%s'
  PM_DATA = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&usehistory=y&query_key=%s&WebEnv=%s&retmode=xml'
  response = urlopen(PM_DATA % (QueryKey,WebEnv)).read()

  return _process_pubmed_response(cur,geninfo,response)

def _process_pubmed_response(cur, geninfo, response, default_priority=0):
  nadded=0
  cur = dbcon.cursor()
  for match in re.finditer('<PubmedArticle>(.*?)</PubmedArticle>',response,re.S):
    article_ids={}
    abstract=''
    fulltext_link=None

    article=match.group(1)
    articleid_matches = re.finditer('<ArticleId IdType="([^"]*)">([^<]*?)</ArticleId>',article, re.S)
    abstract_matches = re.finditer('<AbstractText([^>]*)>([^<]*)</AbstractText>',article,re.S)
    articletitle = re.search('<ArticleTitle[^>]*>([^<]*)</ArticleTitle>',article,re.S).group(1).strip()

    for amatch in articleid_matches:
      article_ids[ amatch.group(1).strip() ] = amatch.group(2).strip()
    for amatch in abstract_matches:
      abstract += amatch.group(2).strip()+' '

    if 'pmc' in article_ids:
      fulltext_link = 'http://www.ncbi.nlm.nih.gov/pmc/articles/%s/' % (article_ids['pmc'],)
    elif 'doi' in article_ids:
      fulltext_link = 'http://dx.crossref.org/%s' % (article_ids['doi'],)
    pmid = article_ids['pubmed'].strip()

    author_matches = re.finditer('<Author [^>]*>(.*?)</Author>',article,re.S)
    authors = []
    for match in author_matches:
      name = ''
      try:
        name = re.search('<LastName>([^<]*)</LastName>',match.group(1),re.S).group(1).strip()
        name = name+' '+re.search('<Initials>([^<]*)</Initials>',match.group(1),re.S).group(1).strip()
      except:
        pass
      authors.append(name)

    authors = ', '.join(authors)

    pubdate = re.search('<PubDate>.*?<Year>([^<]*)</Year>.*?<Month>([^<]*)</Month>',article,re.S)
    journal = re.search('<MedlineTA>([^<]*)</MedlineTA>',article,re.S).group(1).strip()
    # year month journal
    tomonthname = {
        '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr', '5': 'May', '6': 'Jun',
        '7': 'Jul', '8': 'Aug', '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
        }
    pm = pubdate.group(2).strip()
    if pm in tomonthname:
      pm = tomonthname[pm]

    pubinfo = '%s %s %s' % (pubdate.group(1).strip(), pm, journal)

    # create the actual article stub
    cur.execute('SELECT stubid FROM gwcuration.stubs WHERE pmid=%s;', (pmid,))
    row = cur.fetchone()
    if row is not None:
      cur.execute('SELECT stid FROM gwcuration.stub_status WHERE stubid=%s AND grp_id=%s;', (row[0], geninfo['grp_id']))

      row2 = cur.fetchone()
      if row2 is not None:
        continue
    else:
      cur.execute('''INSERT INTO gwcuration.stubs (pmid,title,authors,abstract,link_to_fulltext,pubinfo)
          VALUES (%s,%s,%s,%s,%s,%s) RETURNING stubid;''',
          (pmid,articletitle,authors,abstract,fulltext_link,pubinfo))
      row = cur.fetchone()

    # create this group's stub reference
    cur.execute('''INSERT INTO gwcuration.stub_status (stubid,stid,grp_id,stubgenid,priority)
        VALUES (%s,%s,%s,%s,%s);''', (row[0],1,geninfo['grp_id'],geninfo['stubgenid'],default_priority))

    nadded+=1

  cur.execute('UPDATE gwcuration.stubgenerators SET last_update=NOW() WHERE name=%s AND (usr_id=%s OR grp_id=ANY(%s));',
    (geninfo['name'], int(session['user_id']), '{'+','.join(session['groups'].keys())+'}' ))
  dbcon.commit()
  return nadded

def mod_stub(stubid,grpid):
  newstid = request.args.get('stid')
  newpri = request.args.get('pri')
  cur = dbcon.cursor()
  if newstid is not None:
    cur.execute('UPDATE gwcuration.stub_status SET stid=%s WHERE stubid=%s and grp_id=%s and stid=%s;',
        (newstid, stubid, grpid, session['curstat']))
    if newstid=='':
      cur.execute('''UPDATE production.geneset SET gs_groups='0', cur_id=4 WHERE gs_id in (SELECT gs_id FROM stub2geneset WHERE stubid=%s);''', (stubid,))

  if newpri is not None:
    cur.execute('UPDATE gwcuration.stub_status SET priority=%s WHERE stubid=%s and grp_id=%s and stid=%s;',
        (int(newpri), stubid, grpid, session['curstat']))
  dbcon.commit()
  return redirect(request.referrer)

############################################
def _get_stubinfo(cur, stubid):
  cur.execute('''SELECT ss.stubid,ss.status_comment,ss.priority,ss.rank,ss.grp_id,sg.name
      FROM gwcuration.stub_status ss,gwcuration.stubgenerators sg
      WHERE ss.stubid=%s AND sg.stubgenid=ss.stubgenid;''', (stubid,))
  row = cur.fetchone()
  stub = {'stubid': row[0], 'comment': row[1], 'priority': row[2], 'rank': row[3], 'group': session['groups'][str(row[4])], 'stubgenerator': row[5]}
  stub['status'] = session['stati'][ session['curstat'] ]
  stub['mod_url'] = url_for('mod_stub', stubid=stubid, grpid=row[4])
  stub['add_url'] = url_for('create_from_stub', stubid=stubid)
  stub['view_url'] = url_for('view_stub', stubid=row[0])

  cur.execute('SELECT stubid,title,abstract,authors,pubinfo,pmid,link_to_fulltext,added_on FROM gwcuration.stubs WHERE stubid=%s;', (stubid,))
  row = cur.fetchone()
  stub['atitle'] = row[1].decode('utf-8')
  stub['abstract'] = row[2].decode('utf-8')
  stub['authors'] = row[3].decode('utf-8')
  stub['pubinfo'] = row[4].decode('utf-8')
  stub['pmid'] = row[5]
  stub['fulltext'] = row[6]
  stub['added'] = row[7]

  species={}
  cur.execute('select sp_id,sp_name from odestatic.species where sp_id!=0;')
  for row in cur:
    species[row[0]]=row[1]

  cur.execute('''SELECT g.gs_id,gs_name,gs_abbreviation,gs_description,sp_id,gs_count,cur_id,usr_email,gs_updated,gs_gene_id_type
    FROM production.publication p, production.geneset g, production.usr u
    WHERE g.usr_id=u.usr_id AND p.pub_pubmed=%s and p.pub_id=g.pub_id AND g.gs_status NOT LIKE 'de%%' AND g.cur_id<5;''', (stub['pmid'],))

  stub['genesets']=[]
  for row in cur:
    stub['genesets'].append({
      'gs_id': row[0],
      'gs_name': row[1].decode('utf-8'),
      'gs_abbreviation': row[2].decode('utf-8'),
      'gs_description': row[3].decode('utf-8'),

      'sp_id': row[4],
      'species': species[row[4]],
      'gs_count': row[5],
      'cur_id': row[6],
      'usr_email': row[7],
      'last_updated': row[8],
      'gs_gene_id_type': row[9],
      'pmid': stub['pmid'],
      'view_url': url_for('view_geneset', gsid=row[0]),
      })

  return stub

def view_stub(stubid):
  if 'user_id' not in session:
    return redirect(url_for('login'))

  cur = dbcon.cursor()
  stub = _get_stubinfo(cur,stubid)

  return render_template('view_stub.html', stub=stub)

def comment_stub(stubid):
  if 'user_id' not in session:
    return redirect(url_for('login'))

  comment = request.form.get('comment','')
  cur = dbcon.cursor()
  cur.execute('UPDATE gwcuration.stub_status SET status_comment=%s WHERE stubid=%s;', (comment,stubid))

  dbcon.commit()
  return comment

def create_from_stub(stubid):
  genedbs={}
  platforms={}
  species={}

  cur = dbcon.cursor()
  cur.execute('set search_path to production,odestatic,extsrc;')
  cur.execute('select sp_id,sp_name from odestatic.species where sp_id!=0;')
  for row in cur:
    species[row[0]]=row[1]
  cur.execute('select gdb_id,gdb_name from odestatic.genedb;')
  for row in cur:
    genedbs[row[0]]=row[1]
  cur.execute('select pf_id,pf_name from odestatic.platform;')
  for row in cur:
    platforms[row[0]]=row[1]

  stub = _get_stubinfo(cur,stubid)

  if request.form.get('gs_name','')!='':
    name=request.form.get('gs_name').decode('utf-8')
    label=request.form.get('gs_abbreviation').decode('utf-8')
    desc=request.form.get('gs_description').decode('utf-8')
    sp_id=int(request.form.get('sp_id'))
    idtype=int(request.form.get('id_type'))

    gs_file = request.form.get('gs_filetext','').strip()
    if gs_file=='':
      fn = request.files['gs_file'].filename
      gs_file = open(fn).read()
    gs_file=gs_file.replace('\r\n', '\n').replace('\r','\n')

    # create the pub_id if necessary
    cur.execute('SELECT pub_id FROM production.publication WHERE pub_pubmed=%s;', (stub['pmid'],))
    row = cur.fetchone()
    if row is None:
      cur.execute('''INSERT INTO production.publication (pub_pubmed,pub_title,pub_authors,pub_abstract)
          VALUES (%s,%s,%s,%s) RETURNING pub_id;''', (stub['pmid'],stub['atitle'],stub['authors'],stub['abstract']))
      row = cur.fetchone()
    pub_id = row[0]

    # create the file_id
    cur.execute('INSERT INTO production.file (file_contents,file_size) VALUES (%s,%s) RETURNING file_id;', (gs_file, len(gs_file)))
    row = cur.fetchone()
    file_id = row[0]

    # directly into tier 4
    # gs_threshold_type = 3
    # gs_threshold = 0.0
    cur.execute('''INSERT INTO production.geneset (gs_name,gs_abbreviation,gs_description,sp_id,gs_gene_id_type,
      usr_id,file_id,pub_id,gs_groups,cur_id,gs_status,gs_count,gs_threshold_type,gs_threshold)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,4,'normal',0,3,'0.0') RETURNING gs_id;''',
      (name,label,desc,sp_id,idtype, session['user_id'], file_id,pub_id,session['curgrp']))
    row = cur.fetchone()

    # process the uploaded file (match up gene ids/scores)
    cur.execute('SELECT production.reparse_geneset_file(%s);', (row[0],))
    # process thresholds
    cur.execute('SELECT production.process_thresholds(%s);', (row[0],))

    # update curation status to "in process"
    cur.execute('UPDATE gwcuration.stub_status SET stid=%s WHERE stubid=%s;', (5,stubid))
    cur.execute('INSERT INTO gwcuration.stub2geneset (stubid,gs_id) values (%s,%s);', (stubid,row[0]))

    dbcon.commit()
    cur.close()
    return redirect(url_for('view_stub', stubid=stubid))

  last_sp_id=None
  last_id_type=None
  if stub['genesets']:
    gs=stub['genesets'][-1]
    last_sp_id=gs['sp_id']
    last_id_type=gs['gs_gene_id_type']

  return render_template('create_geneset.html', species=species, platforms=platforms, genedbs=genedbs, stub=stub, last_sp_id=last_sp_id, last_id_type=last_id_type)

def quickadd():
  import re
  pmids = re.split('[ \r\n\t,;]+', request.form.get('pmids'))
  cur = dbcon.cursor()
  stubgenid = add_manual_stubs(cur, pmids, request.form.get('forgroup'), 3)
  dbcon.commit()
  session['curstat']='1'
  session['curgrp']=request.form.get('forgroup')
  return redirect( url_for('list_stubs') )

def dashboard():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  cur = dbcon.cursor()
  pris = ['low','medium','high','urgent']
  species={}
  cur.execute('select sp_id,sp_name from odestatic.species where sp_id!=0;')
  for row in cur:
    species[row[0]]=row[1]

  cur.execute('''SELECT g.gs_id,gs_name,gs_abbreviation,gs_description,sp_id,gs_count,cur_id,usr_email
    FROM production.usr u, production.geneset g
    WHERE u.usr_id=g.usr_id AND g.gs_status NOT LIKE 'de%%' AND g.cur_id>=4 AND gs_groups='0' LIMIT 10;''')

  pgenesets=[]
  for row in cur:
    pgenesets.append({
      'gs_id': row[0],
      'gs_name': row[1].decode('utf-8'),
      'gs_abbreviation': row[2].decode('utf-8'),
      'gs_description': row[3].decode('utf-8'),

      'species': species[row[4]],
      'gs_count': row[5],
      'cur_id': row[6],
      'usr_email': row[7],
      'view_url': url_for('view_geneset', gsid=row[0]),
      })

  cur.execute('''SELECT sg.stubgenid,sg.name,sg.last_update,ss.stid,ss.grp_id,COUNT(ss.stubid)
      FROM gwcuration.stub_status ss,gwcuration.stubgenerators sg,gwcuration.status_types st
      WHERE ss.grp_id=ANY(%s) AND sg.stubgenid=ss.stubgenid AND st.stid=ss.stid AND st.ordercode>=0
        AND ss.stid!=7
      GROUP BY sg.stubgenid,sg.name,sg.last_update,ss.stid,ss.grp_id;''',
      ('{'+','.join(session['groups'].keys())+'}',))

  stub_stats={}
  for row in cur:
    if row[0] not in stub_stats:
      stub_stats[row[0]] = {
        'stubgenid': row[0],
        'name': row[1],
        'updated': row[2],
        'group': session['groups'][str(row[4])],
        'view_url': url_for('list_stubs',grp=row[4]),
        'refresh_url': url_for('list_generators',refresh=row[1]),
        'counts': {},
        }
    stub_stats[row[0]]['counts'][ session['stati'][str(row[3])] ] = row[5]

  return render_template('dashboard.html', pending_genesets=pgenesets, stub_stats=stub_stats)

def list_genesets():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  chgchk = (None,None)
  if 'curtier' in session and 'curgrp' in session:
    chgchk = (session['curtier'],session['curgrp'])

  curtier=request.args.get('tier')
  if curtier is None and 'curtier' in session:
    curtier = session['curtier']

  if curtier is None or curtier not in session['tiers']:
    curtier = '4'
  session['curtier'] = curtier

  curgrp = request.args.get('grp')
  if curgrp is None and 'curgrp' in session:
    curgrp = session['curgrp']

  curgrps = session['groups'].keys()
  if curgrp is None or curgrp not in session['groups']:
    # default to all groups
    curgrp = '0'
  else:
    curgrps = [curgrp]
  session['curgrp'] = curgrp
  if curgrp=='0':
    curgrps += ['0']

  # if options chaged, make sure we're on page 1
  if chgchk != (session['curtier'],session['curgrp']) and request.args.get('page','1')!='1':
    del session['num_gs_results']
    del session['gs_pages']
    del session['gs_page']
    return redirect( url_for('list_genesets', tier=session['curtier'], grp=session['curgrp']) )

  cur = dbcon.cursor()
  cur.execute('''SELECT COUNT(cur_id),cur_id FROM production.geneset
      WHERE gs_groups='0' AND gs_status NOT LIKE 'de%%' 
        AND usr_id IN (SELECT usr_id FROM production.usr WHERE usr_email LIKE '%%@%%')
        GROUP BY cur_id;''',
      ('{'+','.join(curgrps)+'}',))

  tier_counts={}
  for tierid in session['tiers']:
    tier_counts[tierid]=0
  for row in cur:
    tier_counts[str(row[1])]=row[0]

  species={}
  cur.execute('select sp_id,sp_name from odestatic.species where sp_id!=0;')
  for row in cur:
    species[row[0]]=row[1]

  cur.execute('''SELECT g.gs_id,gs_name,gs_abbreviation,gs_description,sp_id,gs_count,cur_id,usr_email,gs_updated,p.pub_pubmed
    FROM production.usr u, production.geneset g LEFT OUTER JOIN production.publication p ON (g.pub_id=p.pub_id)
    WHERE u.usr_id=g.usr_id AND g.gs_status NOT LIKE 'de%%' AND u.usr_email like '%%@%%'
      AND string_to_array(gs_groups,',') && %s AND cur_id=%s;''',
      ('{'+','.join(curgrps)+'}',session['curtier']))

  if chgchk != (session['curtier'],session['curgrp']) or 'num_gs_results' not in session:
    session['num_gs_results'] = cur.rowcount
    session['gs_pages'] = cur.rowcount/25
    if cur.rowcount%25 > 0:
      session['gs_pages']+=1
    session['gs_page']=1
  elif request.args.get('page','1')!=str(session['gs_page']):
    session['gs_page']=int(request.args.get('page','1'))

  stubs={}
  try:
    cur.scroll(25*(int(session['gs_page'])-1))
  except (psycopg2.ProgrammingError, IndexError) as exc:
    if cur.rowcount>0:
      abort(404)

  pgenesets=[]
  for row in cur.fetchmany(25):
    pgenesets.append({
      'gs_id': row[0],
      'gs_name': row[1].decode('utf-8'),
      'gs_abbreviation': row[2].decode('utf-8'),
      'gs_description': row[3].decode('utf-8'),

      'species': species[row[4]],
      'gs_count': row[5],
      'cur_id': row[6],
      'usr_email': row[7],
      'last_updated': row[8],
      'pmid': row[9],
      'view_url': url_for('view_geneset', gsid=row[0]),
      })
  
  return render_template('list_genesets.html', list=pgenesets, tier_counts=tier_counts)

############################################
def _get_genesetinfo(cur, gsid):
  species={}
  cur.execute('select sp_id,sp_name from odestatic.species where sp_id!=0;')
  for row in cur:
    species[row[0]]=row[1]

  start=datetime.datetime.now()
  cur.execute('''SELECT g.gs_id,gs_name,gs_abbreviation,gs_description,sp_id,gs_count,cur_id,usr_email,gs_updated,
       gs_gene_id_type,gs_threshold,gs_threshold_type,p.pub_pubmed,file_id,gs_groups,
       _comments_author,_comments_curator,gs_attribution,gs_uri
    FROM production.geneset g LEFT OUTER JOIN production.publication p ON (g.pub_id=p.pub_id), production.usr u
    WHERE u.usr_id=g.usr_id AND gs_id=%s;''',
      (gsid,))

  row = cur.fetchone()
  if row is None:
      abort(404)

  start=datetime.datetime.now()
  geneid_type=None
  if row[9]>0:
    cur.execute("SELECT pf_name FROM odestatic.platform WHERE pf_id=%s;", (row[9],))
  else:
    cur.execute("SELECT gdb_name FROM odestatic.genedb WHERE gdb_id=%s;", (-row[9],))
  res=cur.fetchone()
  geneid_type=res[0]

  start=datetime.datetime.now()
  cur.execute("SELECT file_contents FROM production.file WHERE file_id=%s;", (row[13],))
  res=cur.fetchone()
  fcontents='(missing)'
  if res is not None:
    fcontents = res[0]

  start=datetime.datetime.now()
  cur.execute('''SELECT o.ont_id,ont_name||' ('||ont_ref_id||')',gso_ref_type FROM extsrc.geneset_ontology gso, extsrc.ontology o
      WHERE gso.ont_id=o.ont_id AND gs_id=%s;''', (row[0],))
  oterms={}
  for res in cur:
    if res[0] not in oterms:
      oterms[res[0]] = (res[1], set([res[2]]) )
    else:
      oterms[res[0]][1].add(res[2])
  otermarr=[]
  for ont_id,info in oterms.iteritems():
    otermarr.append( (ont_id, info[0], ", ".join(sorted(info[1]))) )
  def okey(x):
    pfx=''
    if x[2]=='Blacklist':
      pfx= '~~~~~~~~'       # sort to the end
    if x[2][:10]=='GeneWeaver':
      pfx= '        '+x[2]  # sort to beginning
    return pfx+x[1].lower()
  otermarr.sort(key=okey)

  start=datetime.datetime.now()
  cur.execute("""SELECT x.gs_id,x.jac_value,g.gs_name FROM production.geneset g,
      (SELECT CASE WHEN j.gs_id_left=%s THEN j.gs_id_right ELSE j.gs_id_left END as gs_id,j.jac_value
         FROM extsrc.geneset_jaccard j WHERE (j.gs_id_left=%s OR j.gs_id_right=%s) ORDER BY jac_value DESC LIMIT 1000) x
       WHERE x.gs_id=g.gs_id AND gs_status not like 'de%%' AND gs_groups='0' AND cur_id<=4 LIMIT 10;""", (row[0],row[0],row[0]))

  simgs=[]
  for res in cur:
    simgs.append( {'gs_id': res[0], 'sim': decimal.Decimal('%4.3f' % (res[1],)), 'gs_name': res[2]} )

  cur.execute('SELECT gsi_jac_completed FROM production.geneset_info WHERE gs_id=%s;', (gsid,))
  res=cur.fetchone()
  last_sim_check=res[0]

  threshold_desc = 'Score > %s' % (row[10],)
  if row[11]==1:
    threshold_desc = 'p-value < %s' % (row[10],)
  elif row[11]==2:
    threshold_desc = 'q-value < %s' % (row[10],)
  elif row[11]==4 or row[11]==5:
    threshold_desc = '%s < |Score| < %s' % tuple(row[10].split(','))
  elif row[11]==6:
    threshold_desc = '%s < Score < %s' % tuple(row[10].split(','))
  elif row[11]==7:
    threshold_desc = 'Score < %s or Score > %s' % tuple(row[10].split(','))
  elif row[11]==8:
    threshold_desc = 'Score = %s' % (row[10],)

  geneset = {
      'gs_id': row[0],
      'gs_name': row[1].decode('utf-8'),
      'gs_label': row[2].decode('utf-8'),
      'gs_description': row[3].decode('utf-8'),

      'species': species[row[4]],
      'gs_count': row[5],
      'cur_id': row[6],
      'usr_email': row[7],
      'last_updated': row[8],
      'geneid_type': geneid_type,
      'threshold': threshold_desc,
      'file_contents': fcontents,
      'ontology_terms': otermarr,
      'similarsets': simgs,
      'last_sim': last_sim_check,
      'pmid': row[12],
      'gs_groups': row[14].split(','),
      '_comments_author': row[15] or '',
      '_comments_curator': row[16] or '',
      'gs_attribution': row[17] or '',
      'gs_uri': row[18] or '',

      'view_url': url_for('view_geneset', gsid=row[0]),
      'ncbo_url': url_for('process_geneset', gsid=row[0], procname='ncbo'),
      'sims_url': url_for('process_geneset', gsid=row[0], procname='sims'),
      }

  return geneset

def view_geneset(gsid):
  if 'user_id' not in session:
    return redirect(url_for('login'))

  cur = dbcon.cursor()
  geneset = _get_genesetinfo(cur,gsid)

  for oassoc in geneset['ontology_terms']:
    if oassoc[2]=='GeneWeaver Data Type':
      geneset['data_type']=str(oassoc[0])
      break

  geneset_data_types={}
  cur.execute('''SELECT ont_id,ont_name FROM odestatic.special_terms s,extsrc.ontology o 
      WHERE s.specialset='data_types' AND s.ont_ref_id=o.ont_ref_id AND s.ontdb_id=o.ontdb_id;''')
  for row in cur:
    geneset_data_types[str(row[0])]=row[1]

  return render_template('view_geneset.html', geneset=geneset, geneset_data_types=geneset_data_types)

def process_geneset(gsid, procname):
  if procname=='ncbo':
    load_ncbo_ontologies(gsid)
    return 'done'
  if procname=='sims':
    cur=dbcon.cursor()
    cur.execute("SET search_path to production,odestatic,extsrc")
    cur.execute("UPDATE geneset_info SET gsi_jac_started=NOW() WHERE gs_id=%s;", (gsid,))
    cur.execute("SELECT calculate_jaccard(%s);", (gsid,))
    cur.execute("UPDATE geneset_info SET gsi_jac_completed=NOW() WHERE gs_id=%s;", (gsid,))
    dbcon.commit()
    return 'done'
  return 'nope'

def add_geneset_term(gsid, ontid):
  assoctype=request.args.get('assoctype','nr')

  cur = dbcon.cursor()
  cur.execute("DELETE FROM extsrc.geneset_ontology WHERE gs_id=%s AND ont_id=%s;", (gsid,ontid))
  if assoctype=='bl':
    cur.execute("INSERT INTO extsrc.geneset_ontology (gs_id,ont_id,gso_ref_type) VALUES (%s,%s,'Blacklist');", (gsid,ontid))
  if assoctype=='nr':
    cur.execute("INSERT INTO extsrc.geneset_ontology (gs_id,ont_id,gso_ref_type) VALUES (%s,%s,'Manual');", (gsid,ontid))
  if assoctype=='pr':
    cur.execute("INSERT INTO extsrc.geneset_ontology (gs_id,ont_id,gso_ref_type) VALUES (%s,%s,'GeneWeaver Primary Annotation');", (gsid,ontid))

  dbcon.commit()
  return 'ok'

def comment_geneset(gsid,kind):
  if kind not in ['author','curator']:
    abort(404)
  thecomment = request.args.get('content','')
  cur = dbcon.cursor()
  SQL = 'UPDATE production.geneset SET _comments_'+kind+'=%s WHERE gs_id=%s'
  cur.execute(SQL, (thecomment,gsid))
  dbcon.commit()
  return thecomment

def approve_geneset(gsid,cur_id):
  promote=request.args.get('promote','no')=='yes'

  cur = dbcon.cursor()
  cur.execute("UPDATE production.geneset SET gs_groups='0', cur_id=%s WHERE gs_id=%s;", (cur_id,gsid))
  if promote:
    cur.execute("INSERT INTO odestatic.special_terms (gs_id,specialset) values (%s,'promoted_genesets')", (gsid,))

  # TODO: send email also?
  dbcon.commit()
  return redirect(url_for('list_genesets'))

def reject_geneset(gsid):
  demote=request.args.get('demote','no')=='yes'

  cur = dbcon.cursor()
  if demote:
    cur.execute("UPDATE production.geneset SET gs_groups='-1', cur_id=5 WHERE gs_id=%s;", (gsid,))

  # TODO: send email also
  dbcon.commit()
  return redirect(url_for('list_genesets'))

########################################

def fetch_ncbo_terms(db_cur, text, pub_id=None):
  import urllib
  ncboids=set()
  db_cur.execute("SELECT ontdb_ncbo_vid FROM odestatic.ontologydb;")
  for row in db_cur:
    ncboids.add(str(row[0]))
  ncbo_list=",".join(ncboids);

  ## API Key for me - Jeremy.Jay@jax.org
  NCBO_URL="http://rest.bioontology.org/obs/annotator"
  params={'format': 'tabDelimited', 'withDefaultStopWords': 'true',
      'ontologiesToKeepInResult': ncbo_list, 'textToAnnotate': text,
      'isVirtualOntologyId': 'true', 'apikey': 'be3a088f-c9dc-4c1d-aef2-ad1b27aa649e'
      }

  ontologies=set()
  fails=None
  while fails is None or fails<3:
    try:
      f = urlopen(NCBO_URL, urllib.urlencode(params) )
      for line in f:
        fields = line.strip().split('\t')
        ontology_id=fields[1].split('/')[1]
        if ontology_id!='':
          ontologies.add(ontology_id)
      fails=10
    except:
      if fails is None:
        fails=1
      else:
        fails+=1
      print('HTTP Fail. Retry #%d' % (fails,))
      ontologies=set()

  return ontologies

def load_ncbo_ontologies(gs_id):
  db_cur = dbcon.cursor()
  SQL = """SELECT gs_id, gs_name, gs_name||' '||gs_description as gs_text, geneset.pub_id, pub_title||' '||pub_abstract as pub_text
           FROM production.geneset LEFT OUTER JOIN production.publication ON geneset.pub_id=publication.pub_id
           WHERE LENGTH(gs_name||gs_description)>30 AND gs_id=%s;"""
  db_cur.execute(SQL, (gs_id,))
  texts = db_cur.fetchone()
  if texts==None:
    return

  rem_sql = "DELETE FROM extsrc.geneset_ontology WHERE gs_id=%s AND gso_ref_type LIKE '%%, NCBO Annotator';"
  rem_sql_mi = "DELETE FROM extsrc.geneset_ontology WHERE gs_id=%s AND gso_ref_type LIKE '%%, MI Annotator';"
  db_cur.execute(rem_sql, (gs_id,))
  db_cur.execute(rem_sql_mi, (gs_id,))

  black_sql = "SELECT ont_id FROM extsrc.geneset_ontology WHERE gs_id=%s AND gso_ref_type='Blacklist';"
  db_cur.execute(black_sql, (gs_id,))
  blacklisted = [str(x[0]) for x in db_cur]

  num_added=0
  for thetext, refsrc, pub_id in [(texts[2], 'Description',None),(texts[4], 'Publication',texts[3])]:
    #ontologies = fetch_ncbo_terms(db_cur, thetext, pub_id)
    ncbo_onts = ncbo.fetch_ncbo_terms(thetext, ['MESH', 'GO', 'MP', 'MA'])
    ncbo_onts = ncbo.parse_ncbo_annotations(ncbo_onts)
    mi_onts = mi.fetch_monarch_annotations(thetext)
    mi_onts = mi.parse_monarch_annotations(mi_onts)
    mi_onts = mi.filter_monarch_annotations(mi_onts, ['MESH', 'MP', 'MA', 'GO'])
    ## Monarch initiative returns MESH annotations as MESH:D1234, while 
    ## NCBO and the GW DB just use the unique ID (D1234). 
    for i in range(len(mi_onts)):
      if mi_onts[i].find('MESH') != -1:
        mi_onts[i] = mi_onts[i].split(':')[1].strip()
        #print mi_onts[i]


    ins_sql_mi = """INSERT INTO extsrc.geneset_ontology (gs_id, ont_id, gso_ref_type)
                 SELECT %s, ont_id, %s||', MI Annotator'
                 FROM extsrc.ontology WHERE ont_ref_id=ANY(%s) AND NOT (ont_id=ANY(%s));"""
    ins_sql = """INSERT INTO extsrc.geneset_ontology (gs_id, ont_id, gso_ref_type)
                 SELECT %s, ont_id, %s||', NCBO Annotator'
                 FROM extsrc.ontology WHERE ont_ref_id=ANY(%s) AND NOT (ont_id=ANY(%s));"""
    db_cur.execute(ins_sql_mi, (gs_id, refsrc, '{'+','.join(mi_onts)+'}', '{'+','.join(blacklisted)+'}'))

    ## Prevent duplicate insertions, since some annotations from NCBO will
    ## already have been added using MI
    ncbo_onts = list(set(ncbo_onts) - set(mi_onts))
    db_cur.execute(ins_sql, (gs_id, refsrc, '{'+','.join(ncbo_onts)+'}', '{'+','.join(blacklisted)+'}'))
  dbcon.commit()

def _get_stats(cur):
  qmap = {
      'jobs': ('res_runhash', 'production.result where res_created'),
      'genesets': ('gs_id', 'production.geneset where gs_updated'),
      'projects': ('pj_id', 'production.project2geneset where modified_on'),
      }
  dmap = {1: '24h', 7: '1w', 30: '30d', 180: '6m'}

  stats = {}
  
  for qname,qwhere in qmap.items():
    for ndays,dname in dmap.items():
      cur.execute("SELECT count(distinct %s),count(*) FROM %s > NOW() - INTERVAL '%s days'" % (qwhere[0], qwhere[1], ndays))
      row=cur.fetchone()
      stats[ qname+'_'+dname ] = row[0]
      stats[ qname+'_'+dname+'_full' ] = row[1]

  # number of registered, active users
  cur.execute("SELECT count(*) FROM production.usr WHERE usr_email LIKE '%%@%%' AND (usr_id IN (SELECT DISTINCT usr_id FROM production.project) OR usr_id IN (SELECT DISTINCT usr_id FROM production.geneset));")
  row=cur.fetchone()
  stats['active_users_registered'] = row[0]

  # number of recently active visitors
  cur.execute("SELECT count(*) FROM production.usr WHERE (usr_id IN (SELECT DISTINCT usr_id FROM production.project) OR usr_id IN (SELECT DISTINCT usr_id FROM production.geneset));")
  row=cur.fetchone()
  stats['active_users'] = row[0]

  return stats

def _get_resources(cur):
	resinfo={}
	cur.execute("select count(*), max(gs_updated), gs_attribution from production.geneset where gs_status not like 'de%' and cur_id=1 group by gs_attribution;")
	for row in cur:
		resinfo[ row[2] ] = (row[1], row[0])

	return resinfo

def admin_main():
  admin_role = {
      '0': 'Normal User',
      '1': 'Editor',             # can edit any geneset on the site
      '2': 'Curator',            # can promote/demote any geneset
      '3': 'Site Administrator', # can update genes and data sources
    }
  admins={}
  db_cur = dbcon.cursor()
  db_cur.execute('SELECT usr_email, usr_admin FROM production.usr WHERE usr_admin>0;')
  for row in db_cur:
    admins[ row[0] ] = { 'admin_level': row[1], 'role': admin_role[str(row[1])]}

  db_cur.execute("SELECT * FROM odestatic.species WHERE sp_id<>0 ORDER BY sp_name;")
  allspecies=db_cur.fetchall()

  db_cur.execute("SELECT * FROM odestatic.genedb NATURAL JOIN odestatic.species WHERE gdb_name<>'Unannotated' ORDER BY sp_name,gdb_id;")
  allgenedbs = db_cur.fetchall()


  #db_cur.execute("SELECT *,x.probe_count,x.gene_count FROM platform, (SELECT pf_id,count(probe.prb_id) as probe_count,count(distinct probe2gene.prb_id) as probemap_count, count(distinct ode_gene_id) as gene_count FROM probe left outer join probe2gene ON (probe.prb_id=probe2gene.prb_id) GROUP BY pf_id) x WHERE x.pf_id=platform.pf_id AND pf_gpl_id IS NOT NULL ORDER BY CAST(SUBSTR(pf_gpl_id,4) AS INTEGER);")
  #allplatforms=db_cur.fetchall()

  #db_cur.execute("SELECT gdb_id,sp_id,count(distinct ode_ref_id) FROM gene GROUP BY gdb_id,sp_id;")
  #genecounts = db_cur.fetchall()

  #db_cur.execute("SELECT *,x.count as ontdb_count FROM ontologydb, (SELECT ontdb_id,count(ont_id) FROM ontology GROUP BY ontdb_id) x WHERE x.ontdb_id=ontologydb.ontdb_id ORDER BY ontdb_name;")
  #allonts = db_cur.fetchall()

  #db_cur.execute("SELECT hom_source_name, MAX(hom_date) AS hom_date FROM homology GROUP BY hom_source_name;")
  #homcounts = db_cur.fetchall()

  stats=_get_stats(db_cur)
  resources=_get_resources(db_cur)
  return render_template('admin_main.html', admins=admins, stats=stats, resources=resources, num_resources=len(resources))

#################################
app.add_url_rule('/curation/', 'dashboard', dashboard, methods=['GET'])
app.add_url_rule('/curation/login', 'login', login, methods=['GET','POST'])
app.add_url_rule('/curation/stubgens/', 'list_generators', list_generators, methods=['GET', 'POST'])
app.add_url_rule('/curation/stubs/quickadd', 'quickadd', quickadd, methods=['POST'])
app.add_url_rule('/curation/stubs/', 'list_stubs', list_stubs, methods=['GET'])
app.add_url_rule('/curation/stubs/<int:stubid>', 'view_stub', view_stub, methods=['GET'])
app.add_url_rule('/curation/stubs/<int:stubid>/mod/<int:grpid>', 'mod_stub', mod_stub, methods=['GET'])
app.add_url_rule('/curation/stubs/<int:stubid>/comment', 'comment_stub', comment_stub, methods=['POST'])
app.add_url_rule('/curation/stubs/<int:stubid>/create', 'create_from_stub', create_from_stub, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/', 'list_genesets', list_genesets, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/<int:gsid>', 'view_geneset', view_geneset, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/<int:gsid>/assoc/<int:ontid>', 'add_geneset_term', add_geneset_term, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/<int:gsid>/proc_<procname>', 'process_geneset', process_geneset, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/<int:gsid>/approve/<int:cur_id>', 'approve_geneset', approve_geneset, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/<int:gsid>/reject', 'reject_geneset', reject_geneset, methods=['GET', 'POST'])
app.add_url_rule('/curation/genesets/<int:gsid>/comment/<kind>', 'comment_geneset', comment_geneset, methods=['GET', 'POST'])

app.add_url_rule('/curation/admin/', 'admin_main', admin_main, methods=['GET', 'POST'])

if __name__ == '__main__':
  #from dbgbar.flask_debugtoolbar import DebugToolbarExtension
  #app.config['DEBUG']=True
  #app.config['TESTING']=True
  #app.config['DEBUG_TB_PROFILER_ENABLED']=True
  #app.config['DEBUG_TB_INTERCEPT_REDIRECTS']=False
  #app.debug=True
  #toolbar = DebugToolbarExtension(app, prefix='/curation')
  app.run(host='0.0.0.0', port=5005)
