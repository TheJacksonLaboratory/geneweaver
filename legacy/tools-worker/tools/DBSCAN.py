#!/usr/bin/python

import os
from subprocess import PIPE
import subprocess
import sys
import json

import tools.toolbase
from tools.celeryapp import celery

class DBSCAN(tools.toolbase.GeneWeaverToolBase):
    name = "tools.DBSCAN.DBSCAN"

    def __init__(self, *args, **kwargs):
        self.init("DBSCAN")
        self.urlroot=''

    # Main execution
    def mainexec(self):

        epsilon = self._parameters['DBSCAN_epsilon']
        minPts = self._parameters['DBSCAN_minPts']
        output_prefix = self._parameters["output_prefix"]
        gs_dict = self._parameters["gs_dict"]

        self.update_progress('Running the DBSCAN algorithm...')

        print("got to mainexec")
        try:
            fout = open(output_prefix + ".txt", "w")
        except IOError:
            sys.stderr.write("Could not open file text.txt")

        num_genes = 0  # The number of genes in the data set
        num_genesets = 0  # The number of gene sets in the data set
        num_links = 0  # The number of connections from gene to gene sets
        genes = {}  # A dictionary of all the genes
        genesets = {}  # A dictionary of all the gene sets
        links = ""  # The input string that will be passed to the DBSCAN executable
        resClusters = []
        all_species = {}  # species for the select species modal
        all_species_full = {}  # needed for a complete list of species

        # database cursor
        cursor = self.db.cursor()

        # get all species from GeneWeaver
        cursor.execute('''SELECT sp_id, sp_name FROM odestatic.species WHERE sp_id != 0''')
        for s in cursor.fetchall():
            all_species[s[0]] = "".join(item[0] for item in s[1].split())
            all_species_full[s[0]] = s[1]

        gene_symbols = gs_dict["gene_symbols"]
        for key in gene_symbols:
            if str(key) not in genesets:
                genesets[str(key)] = num_genesets
                num_genesets += 1
            for element in gene_symbols[key]:
                if str(element) not in genes:
                    genes[str(element)] = num_genes
                    num_genes += 1
                links += str(genes[element]) + "*" + str(genesets[key]) + "*"
                num_links += 1

        if int(num_genes-1) >= int(minPts):
            self._results['ran'] = 1
            data_input = str(num_genes) + "*" + str(num_genesets) + "*" + str(num_links) + "*" + links
            fout.write(data_input + " " + str(epsilon) + " " + str(minPts))
            # Toolpath is the variable that holds the location to the executable, needs to be changed to more generic
            toolpath = os.path.join(self.TOOL_DIR, 'TOOLBOX/DBSCAN/dbscan')

            # Runs the executable, and waits for it to finish
            popen = subprocess.Popen([toolpath + " " + data_input + " " + str(epsilon) + " " + str(minPts)],
                                     shell=True, stdout=PIPE, stderr=PIPE)
            # Waits for the process to finish and get its exit code
            returncode = popen.wait()

            # Reads from the executables stdout and stderr
            data, error = popen.communicate()

            # Popen returns bytes on Python 3; decode before comparing/parsing.
            if isinstance(data, bytes):
                data = data.decode('utf-8', 'replace')
            if isinstance(error, bytes):
                error = error.decode('utf-8', 'replace')

            # Map each gene index back to its symbol. Built unconditionally so the
            # result keys set below are always defined, even when there are no
            # clusters or the executable fails (otherwise the result page 500s).
            decode = {}
            for gene in genes:
                decode[str(genes[gene])] = gene
            clusters = []

            # A non-zero return code means the executable failed; an '@' or empty
            # stdout means no clusters were found. Either way, degrade gracefully
            # with an empty cluster set instead of raising.
            if returncode != 0:
                fout.write(str(error))
            elif data.strip() in ('', '@'):
                fout.write("No Clusters Found")
            else:
                clusters = json.loads(data)

                for clus in clusters:
                    fout.write("Cluster: ")
                    tempCluster = []
                    for g in clus:
                        fout.write(str(decode[str(g)]) + " ")
                        tempCluster.append(str(decode[str(g)]))
                    fout.write("\n")
                    resClusters.append(tempCluster)

            fout.close()

            self._results['resClusters'] = resClusters
            self._results['resClustersStr'] = json.dumps(resClusters)
            self._results['clusters'] = clusters
            self._results['decode'] = decode
            self._results['genes'] = json.dumps(list(genes.keys()))
            self._results['gs_ids'] = self._gsids
            self._results['species_map'] = json.dumps(gs_dict["species_map"])
            self._results['edges'] = json.dumps(gs_dict["edges"])
            self._results['threshold'] = gs_dict["threshold"]
            self._results['parameters'] = self._parameters
            self._results['all_species_full'] = all_species_full
        else:
            self._results['gs_ids'] = self._gsids
            self._results['parameters'] = self._parameters
            self._results['ran'] = 0

        ###############################################################
        ###############################################################
        # dump the dictionary into a json file that will be read
        # by the template
        #

        with open(output_prefix + '.json', 'w') as fp:
            json.dump(self._results, fp)


DBSCAN = celery.register_task(DBSCAN())
