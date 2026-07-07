import re
import math
import os
import subprocess

import tools.toolbase
from tools.celeryapp import celery


class TricliqueViewer(tools.toolbase.GeneWeaverToolBase):
    name = "tools.TricliqueViewer.TricliqueViewer"

    def __init__(self, *args, **kwargs):
        self.init("TricliqueViewer")
        self.urlroot=''

    def mainexec(self):
        #os.chdir('/var/www/html/dev-geneweaver/results/')
        os.chdir(self.OUTPUT_DIR)
        TOOL_DIRECTORY = self.TOOL_DIR
        RESULTS_DIRECTORY = self.OUTPUT_DIR
        print("Got to TricliqueViewer")
        output_prefix = self._parameters["output_prefix"]
        # Also need to figure out what Dr. Baker's output file is named
        # Enable this when we implement Jaccard option
        enabled_ExactGeneOverlap = self._parameters["Methods"]=='ExactGeneOverlap'
        print("value")
        print(enabled_ExactGeneOverlap)
        print("results")
        print(self._results)
        print("parameters")
        print(self._parameters)

        # Call bk-partite and store results in some data structure
        self.update_progress("Running bk-partite algorithm...")
        print("Running bk-partite algorithm")
        args = ("%s/TOOLBOX/bk-partite/bk-partite" % (TOOL_DIRECTORY), RESULTS_DIRECTORY + output_prefix + ".kel", "-p")
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        if enabled_ExactGeneOverlap:
            print("writing exact gene overlap file")
            f = open(output_prefix + ".mkc", 'w')
        else:
            print("writing jaccard file")
            f = open(output_prefix + ".mkcj", 'w')
        for line in proc.stdout:
            f.write(line)
        #f.write(edge_kclique)
        print("edge_kclique")
        # print edge_kclique
        f.close()

    # Generate .json and .csv files and write to results directory

    # Return to tricliqueblueprint.py

TricliqueViewer = celery.register_task(TricliqueViewer())
