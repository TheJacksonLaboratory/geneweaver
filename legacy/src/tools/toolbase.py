#!/usr/bin/env python
#
# abstract ODE Tool interface
#

import os
import re
import sys
import json
import time
import psycopg2

from celery import Task,current_task,logger,SoftTimeLimitExceeded

# //////////////////////////////////////////////////////

class GeneWeaverToolBase(Task):
    abstract = True

    TOOL_DIR='/srv/tools'
    OUTPUT_DIR='/srv/www/results'

    TOOLSET_SQL = [
    # 0
    r'''SELECT gs_id, gsv.ode_gene_id, ode_ref_id FROM geneset_value gsv, gene gid
    WHERE gsv_in_threshold AND gs_id=ANY(%s) AND gsv.ode_gene_id=gid.ode_gene_id AND gid.ode_pref;''',

    # 1
    r'''SELECT a.ode_gene_id as "left_ode_gene_id", b.ode_gene_id as "right_ode_gene_id", a.hom_id
    FROM homology a, homology b
    WHERE a.hom_id=b.hom_id and a.ode_gene_id<>b.ode_gene_id
     AND a.ode_gene_id IN (SELECT DISTINCT ode_gene_id FROM geneset_value WHERE gsv_in_threshold and gs_id=ANY(%s))
     AND b.ode_gene_id IN (SELECT DISTINCT ode_gene_id FROM geneset_value WHERE gsv_in_threshold and gs_id=ANY(%s))
    GROUP BY left_ode_gene_id, right_ode_gene_id, a.hom_id
    ''',

    # 2
    r'SELECT gs_id, gs_name, gs_abbreviation FROM geneset WHERE gs_id=ANY(%s);',

    # 3
    r'SELECT gs_id, sp_id, gs_gene_id_type FROM geneset WHERE gs_id=%s;',

    # 4
    r'SELECT COUNT(DISTINCT ode_gene_id) FROM geneset_value WHERE gs_id IN (%s,%s)',

    # 5
    r'''SELECT COUNT(DISTINCT ode_gene_id) FROM probe2gene p2g, platform m, probe p
     WHERE p2g.prb_id=p.prb_id AND p.pf_id=m.pf_id AND (m.pf_id=%s OR m.pf_set=%s)''',

    # 6
    r'''(SELECT ode_gene_id FROM probe2gene p2g, platform m, probe p
     WHERE p2g.prb_id=p.prb_id AND p.pf_id=m.pf_id AND (m.pf_id=%s OR m.pf_set=%s))
        INTERSECT
     (SELECT ode_gene_id FROM probe2gene p2g, platform m, probe p
     WHERE p2g.prb_id=p.prb_id AND p.pf_id=m.pf_id AND (m.pf_id=%s OR m.pf_set=%s))'''

    ]

    def __init__(self,subclassname,*args,**kwargs):
        logger.info('base init\'ed tool "%s"' % (subclassname,))
        self.init(subclassname)

    def init(self,subclassname):
        logger.info('init\'ed tool "%s"' % (subclassname,))
        os.chdir(self.OUTPUT_DIR)
        #self.db = psycopg2.connect("host=ode-db1 dbname=ODE user=odeweb")
        self.db = psycopg2.connect("host=ode-db3 dbname=ODE user=odeweb")

        self._files = {}
        self._parameters = {}
        self._results = {}
        self._progress = {}
        self._matrix = {}
        self._pairwisedeletion_matrix = {}

        self._start_time = time.time()
        self._last_status_time = self._start_time

        cur = self.db.cursor()
        cur.execute("SET search_path TO production,extsrc,odestatic;")
        cur.execute("SELECT tool_classname,tool_name,tool_description,tool_requirements FROM tool WHERE tool_classname=%s;", (subclassname,))
        t = cur.fetchone()
        self.tool_name = t[1]
        self.tool_description = t[2]
        self._requirements = re.split(', *',t[3])
        self.default_parameters = {}

        try:
            cur.execute("SELECT tp_name,tp_default FROM tool_param WHERE tool_classname=%s;", (t[0],))
            for p in cur:
                self.default_parameters[ p[0] ] = p[1]
        except:
            pass
        cur.close()

    def combine_genesets(self, gsids):
        include_homology = self._parameters['Homology']=='Included'

        gsids_str = '{%d' % (gsids[0])
        for gsid in gsids[1:]:
            gsids_str+=',%d' % (gsid)
        gsids_str += '}'
        self.cur.execute(self.TOOLSET_SQL[0], (gsids_str,))
        data1 = self.cur.fetchall()
        self.cur.execute(self.TOOLSET_SQL[1], (gsids_str,gsids_str))
        data2 = self.cur.fetchall()
        self.cur.execute(self.TOOLSET_SQL[2], (gsids_str,))
        data3 = self.cur.fetchall()

        self.update_progress("Combining GeneSets...")
        matrix = {}
        for row in data1:
            self.update_progress('', self.cur.rownumber*100/self.cur.rowcount)
            if row[1] not in matrix:
                matrix[ row[1] ] = {}
            matrix[ row[1] ][ 0 ] = row[2]
            matrix[ row[1] ][ row[0] ] = 1

        #//////////////////////////

        homologs={}
        h2 = {}
        if len(data2)>0 and include_homology:
            self.update_progress("Integrating homologous genes...")
            for row in data2:
                if row[0] not in homologs:
                    homologs[ row[0] ] = {}
                if row[1] not in homologs:
                    homologs[ row[1] ] = {}

                homologs[ row[0] ][ row[1] ] = 1
                homologs[ row[1] ][ row[0] ] = 1

            for (h,arr) in homologs.items():
                cnt=len(arr)+1
                if cnt not in h2:
                    h2[cnt]=[]
                h2[ cnt ].append(h)

            h2counts=h2.keys()
            h2counts.sort(reverse=True)

            for cnt in h2counts:
                for candidate in h2[cnt]:
                    if candidate in homologs and candidate in matrix:
                        r3 = matrix[candidate]
                        added=False
                        for g2 in homologs[candidate].keys():
                            if g2 not in matrix:
                                continue
                            for gsid in gsids:
                                if (gsid in matrix[g2] and matrix[g2][gsid]):
                                    if (gsid not in r3 or not r3[gsid]):
                                        r3[gsid]=1
                                        added=True
                            del matrix[g2]
                            del homologs[g2]
                        if added:
                            matrix[-candidate]=r3
                            del matrix[candidate]

        # ///////////////////////////
        matrix['==HEADER=='] = {'gsids': gsids, 'gslabels': {}, 'gsnames': {}}
        for row in data3:
            matrix['==HEADER==']['gslabels'][row[0]] = re.sub("[\t\n]",' ',row[2])
            matrix['==HEADER==']['gsnames'][row[0]] = re.sub("[\t\n]",' ',row[1])

        return matrix

    def pairwise_deletion_counting(self, matrix):
        header = matrix['==HEADER==']
        gsids = header['gsids']
        num_genesets = len(gsids)
        do_pairwise_deletion=False
        for param in self._parameters:
            if 'PairwiseDeletion' in param and self._parameters[param]=='Enabled':
                do_pairwise_deletion=True

        c = {}
        if do_pairwise_deletion:
            self.update_progress('Performing Pairwise Deletion Counting...')
        else:
            self.update_progress('Performing Pairwise Counting...')

        for i in range(0,num_genesets):
            self.update_progress('', i*25/num_genesets)
            c[i] = [False for x in range(0,num_genesets)]
            for j in range(i,num_genesets):
                ref_count = None
                ref_pop = None
                self.cur.execute(self.TOOLSET_SQL[3], (gsids[i],))
                data1 = self.cur.fetchone()
                self.cur.execute(self.TOOLSET_SQL[3], (gsids[j],))
                data2 = self.cur.fetchone()

                if not do_pairwise_deletion or data1[2]<0 or data2[2]<0 or data1[1]!=data2[1]:
                    self.cur.execute(self.TOOLSET_SQL[4], (gsids[i],gsids[j]))
                    data3 = self.cur.fetchone()

                    ref_count=data3[0]
                elif data1[2]==data2[2]:
                    self.cur.execute(self.TOOLSET_SQL[5], (data1[2],data1[2]))
                    data3 = self.cur.fetchone()

                    ref_count=data3[0]
                else:
                    self.cur.execute(self.TOOLSET_SQL[6], (data1[2],data1[2], data2[2],data2[2]))
                    ref_count=self.cur.rowcount
                    data3 = self.cur.fetchall()
                    ref_pop={}
                    for r in data3:
                        ref_pop[ r[0] ]=1
                c[i][j] = {'00': ref_count, '10': 0, '01': 0, '11': 0, 'ref': ref_pop}

        for i in range(0,num_genesets):
            gsA = gsids[i]

            self.update_progress('', 25+(i+1)*75/num_genesets)
            for (gid,row) in matrix.items():
                if gid=='==HEADER==':
                    continue

                for j in range(i,num_genesets):
                    gsB = gsids[j]
                    if c[i][j]['ref'] and gid not in c[i][j]['ref']:
                        continue

                    # counting
                    if gsA not in row or row[gsA]==0:
                        if gsB in row and row[gsB]!=0:
                            # A is missing, B is set
                            c[i][j]['01']+=1
                            c[i][j]['00']-=1
                    else:
                        if gsB not in row or row[gsB]==0:
                            # A is set, B is missing
                            c[i][j]['10']+=1
                            c[i][j]['00']-=1
                        else:
                            # both are set
                            c[i][j]['11']+=1
                            c[i][j]['00']-=1

            for j in range(i+1,num_genesets):
                c[ j ][ i ] = dict(c[ i ][ j ])
                #c[ j ][ i ]['00'] = c[ i ][ j ]['00']
                c[ j ][ i ]['01'] = c[ i ][ j ]['10']
                c[ j ][ i ]['10'] = c[ i ][ j ]['01']
                #c[ j ][ i ]['11'] = c[ i ][ j ]['11']
        c['==HEADER==']=header
        return c

    ##################

    def write_combined_file(self, filename, matrix):
        F = open(filename, "w")
        header = matrix['==HEADER==']
        gsids = header['gsids']
        newline = ["%d\t%d" % (len(matrix)-1, len(gsids))]
        newline2= ["\t"]

        for gsid in gsids:
            newline.append("GS%d" % (gsid))
            newline2.append(header['gslabels'][gsid])
        print >>F, "\t".join(newline)
        print >>F, "\t".join(newline2)

        for (geneid,row) in matrix.items():
            if geneid=='==HEADER==':
                continue

            newline = ["%d" % (geneid),row[0]]
            e=0
            for gsid in gsids:
                if gsid in row and row[gsid]:
                    newline.append("1")
                    e+=1
                else:
                    newline.append("0")
            print >>F, "\t".join(newline)
        F.close()

    def write_pairwise_deletion_file(self, filename, pwdc):
        F = open(filename, "w")
        header = pwdc['==HEADER==']
        gsids = header['gsids']
        newline = ["%d" % (len(gsids))]
        newline2= [""]

        for gsid in gsids:
            newline.append("GS%d" % (gsid))
            newline2.append(header['gslabels'][gsid])
        print >>F, "\t".join(newline)
        print >>F, "\t".join(newline2)

        for i in range(0,len(gsids)):
            row = pwdc[i]

            newline = ["GS%d" % (gsids[i])]
            for j in range(0,len(gsids)):
                counts = row[j]
                newline.append("%d (%d) %d [%d]" % (counts['10'], counts['11'], counts['01'], counts['00']))
            print >>F, "\t".join(newline)
        F.close()


    def load_matrix_py(self, mat):
        header = mat['==HEADER==']
        gsids = header['gsids']
        self._files['matrix']=None
        self._num_genes = len(mat)
        self._num_genesets = len(gsids)
        self._gsids=[]
        self._gsnames=[]
        for gsid in gsids:
            self._gsids.append("GS%d" %(gsid))
            self._gsnames.append(header['gslabels'][gsid] )
        self._gsdescriptions = self._gsnames # TODO: actual gs_descriptions
        self._matrix = []
        for (geneid,row) in mat.items():
            if geneid=='==HEADER==':
                continue
            newline = [geneid,row[0]]
            self._num_edges=0
            for gsid in gsids:
                if gsid in row and row[gsid]:
                    newline.append(1)
                    self._num_edges+=1
                else:
                    newline.append(0)
            self._matrix.append(newline)

    def load_pairwisedeletion_matrix_py(self, pwdc):
        header = pwdc['==HEADER==']
        gsids = header['gsids']
        self._files['pairwisedeletion_matrix']=None
        self._num_genesets = len(gsids)
        self._gsids=[]
        self._gsnames=[]
        for gsid in gsids:
            self._gsids.append("GS%d" %(gsid))
            self._gsnames.append(header['gslabels'][gsid] )
        self._gsdescriptions = self._gsnames # TODO: actual gs_descriptions
        self._pairwisedeletion_matrix = []
        for i in range(0,len(gsids)):
            self._pairwisedeletion_matrix.append([])
            row = pwdc[i]

            for j in range(0,len(gsids)):
                counts = row[j]
                self._pairwisedeletion_matrix[i].append( counts )

    def load_matrix(self, filename):
        self._files['matrix']=filename
        matrix = open(filename).read().split("\n")
        header = matrix[0].split("\t")
        self._num_genes = int(header[0])
        self._num_genesets = int(header[1])
        self._gsids = header[2:]
        self._gsnames = matrix[1].split("\t")[2:]
        self._gsdescriptions = self._gsnames # TODO: actual gs_descriptions
        self._matrix = []
        for row in matrix[2:]:
            if row=='':
                continue
            self._matrix.append( row.split("\t") )

    def load_pairwisedeletion_matrix(self, filename):
        self._files['pairwisedeletion_matrix']=filename
        pwdc = open(filename).read().split("\n")
        header = pwdc[0].split("\t")
        self._num_genesets = int(header[0])
        self._gsids = header[1:]
        self._gsnames = pwdc[1].split("\t")[1:]
        self._gsdescriptions = self._gsnames # TODO: actual gs_descriptions

        pwdc = pwdc[2:]
        self._pairwisedeletion_matrix = []
        for i in range(0,self._num_genesets):
            cnt = pwdc[i].split("\t")[1:]
            self._pairwisedeletion_matrix.append([])
            for j in range(0,self._num_genesets):
                m = re.search(r'^([0-9]*) \(([0-9]*)\) ([0-9]*) \[([0-9]*)\]$', cnt[j])
                if m:
                    self._pairwisedeletion_matrix[ i ].append({
                        '10': int(m.group(1)), '11': int(m.group(2)),
                        '01': int(m.group(3)), '00': int(m.group(4))
                    })

    def run(self, output_prefix='job1', gsids=[], params={}):
        self._start_time = time.time()
        self._last_status_time = self._start_time

        gsids=[int(x) for x in gsids]
        self.cur = self.db.cursor()
        self.cur.execute("set search_path to production,extsrc,odestatic;")
        self.cur.execute("UPDATE result SET res_started=NOW() WHERE res_runhash=%s;", (output_prefix,));
        self.cur.execute("SELECT usr_id FROM result WHERE res_runhash=%s;", (output_prefix,));
        row=self.cur.fetchone()
        self.usr_id=row[0]

        self._parameters = params
        for (k,v) in self.default_parameters.items():
            if k not in self._parameters:
                self._parameters[k]=v

        mat=None

        if 'Homology' not in self._parameters:
            self._parameters['Homology']='Included'

        self._parameters['output_prefix']=output_prefix

        if 'matrix' in self._requirements:
            mat = self.combine_genesets(gsids)
            self.load_matrix_py(mat)

        if 'matrix_file' in self._requirements:
            self.write_combined_file('%s.odemat' % output_prefix, mat)

        if 'pairwisedeletion_matrix' in self._requirements:
            if not mat:
                mat = self.combine_genesets(gsids)
            pwdc = self.pairwise_deletion_counting(mat);
            self.load_pairwisedeletion_matrix_py(pwdc)

        self._results = {'parameters': self._parameters}

        try:
            self.mainexec()
            self.cur.execute("UPDATE result SET res_completed=NOW(),res_status=COALESCE(res_status,'')||E'\nDONE',res_data=%s WHERE res_runhash=%s;",
                    (json.dumps(self._results),output_prefix,));
        except SoftTimeLimitExceeded:
            self._kill_children()
            self.cur.execute("UPDATE result SET res_completed=NOW(),res_status=COALESCE(res_status,'')||E'\nERROR - Time limit exceeded. Try smaller data sets.',res_data=%s WHERE res_runhash=%s;",
                (json.dumps(self._results),output_prefix,));
        except Exception as ex:
            self._kill_children()
            self.cur.execute("UPDATE result SET res_completed=NOW(),res_status=COALESCE(res_status,'')||E'\nERROR - Unknown problem.\n'||%s,res_data=%s WHERE res_runhash=%s;",
                (str(ex), json.dumps(self._results),output_prefix,));

        #current_task.update_state(state='SUCCESS', meta={'result': self._results})

        """
                 $res->set('res_status', $toolName." on ".count($gs_idList)." GeneSets" );
        """
        self.cur.close()
        self.db.commit()

        return json.dumps(self._results)

    def get_exectime(self):
        cur_time = time.time()
        elapsed = int(cur_time-self._start_time)
        return "%d:%02d" % (elapsed/60, elapsed%60)

    def update_progress(self, text=None, percent=0):
        if '_last_' not in self._progress:
            self._progress = {'_last_': ['',0] }

        if text is None or text.strip()=='':
            text=self._progress['_last_'][0]

        self._progress[text]=percent
        if self._progress['_last_'][0]!=text:
            self._last_status_time=time.time()
            self._progress['_last_'][0]=text
            self._progress['_last_'][1]=percent
        elif (percent-self._progress['_last_'][1])>=10 or (time.time()-self._last_status_time) >= 30:
            self._last_status_time=time.time()
            self._progress['_last_'][1]=percent
        else:
            return

        pstr='      '
        if float(percent)>0.09:
          pstr="%5.1f%%" % (float(percent))
        text = "%s - %s %s" % (self.get_exectime(), pstr, text)

        self.cur.execute("UPDATE result SET res_status=COALESCE(res_status,'')||%s WHERE res_runhash=%s", ("\n%s"%text, self._parameters['output_prefix']))
        self.db.commit()
        current_task.update_state(state='STATUS_INFO', meta={'at': self.get_exectime(), 'message': text, 'percent': percent})

    def _kill_children(self, pid=None, is_child=False):
        import subprocess
        import signal
        if pid is None:
            pid=os.getpid()
        ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" % (pid,), shell=True, stdout=subprocess.PIPE)
        ps_output = ps_command.stdout.read()
        retcode = ps_command.wait()
        if retcode != 0:
            return
        for chpid in ps_output.split("n")[:-1]:
            try:
                self._kill_children(chpid, signal.SIGTERM, True)

                if is_child:
                    os.kill(chpid, signal.SIGTERM)
            except OSError:
                pass

    def mainexec(self):
        raise NotImplementedError("""
        ode.Tool.mainexec() is not implemented. Here's a short reference:
         update status with: update_progress("what i'm doing", percent_complete)
         place result data in: self._results[...] = {}

         useful params/data for your implementation are:

             self._matrix
             self._pairwisedeletion_matrix
             self._parameters
             self._num_genes
             self._num_genesets
             self._gsids
             self._gsnames
             self._gsdescriptions

             self._results
        """)
