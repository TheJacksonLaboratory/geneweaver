#!/usr/bin/python
# USAGE: JaccardClustering.py input.odemat < parameters_json.txt > output_json.txt 2>status.txt

from subprocess import PIPE
import subprocess
import sys
import tempfile
import os

import numpy as np

import tools.toolbase
from tools.celeryapp import logger
from tools.celeryapp import celery


def write_gs_to_tempfile(geneset):
    """
    Save a geneset to a temporary file, and return the file object
    :param geneset: tab separated list
    :return: tempfile object
    """
    tmp = tempfile.NamedTemporaryFile(mode='w', delete=False)
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(tmp.name, 0o777 & ~umask)
    for gene in geneset:
        tmp.write(str(gene) + '\n')
    tmp.close()
    return tmp

def tsv_file_to_dict(path):
    with open(path, 'r') as tsv_file:
        d = {row[0]: row[1:][0].strip() for row in (line.split('\t') for line in tsv_file)}
    return d

class MSET(tools.toolbase.GeneWeaverToolBase):
    name = "tools.MSET.MSET"

    def __init__(self, *args, **kwargs):
        self.init("MSET")
        self.urlroot=''
        self.mset_dir = os.path.join('TOOLBOX', 'CS_Mset')
        # Background files are DB-derived and go stale whenever the gene data is
        # reloaded (a stale background fails MSETcpp's "list must be a subset of
        # its background" check). Prefer a per-environment regenerated copy on the
        # results volume when present (GW_MSET_BG_DIR, else
        # $APPLICATION_RESULTS/mset_backgrounds); fall back to the in-image copy.
        _image_bg = os.path.join(self.TOOL_DIR, self.mset_dir, 'backgroundFiles')
        _pvc_bg = os.environ.get('GW_MSET_BG_DIR') or (
            os.path.join(os.environ['APPLICATION_RESULTS'], 'mset_backgrounds')
            if os.environ.get('APPLICATION_RESULTS') else None)
        self.bg_dir = _pvc_bg if _pvc_bg and os.path.isdir(_pvc_bg) else _image_bg
        self.cpp_path = os.path.join(self.TOOL_DIR, self.mset_dir, 'MSETcpp')

    def mainexec(self):
        output_prefix = self._parameters["output_prefix"]
        gs_dict = self._parameters["gs_dict"]
        num_trials = self._parameters["MSET_NumberofSamples"]

        # Update tool progress
        self.update_progress("Computing MSET...")

        # Attempt to open the output file
        try:
            fout = open(output_prefix + ".txt", "w")
            fout.close()
        except IOError:
            logger.error("Could not open output file.")
            sys.stderr.write("Could not open file text.txt")
            raise

        list_1 = gs_dict.get("group_1_genes")
        list_1_bg = gs_dict.get("group_1_background")
        bg_1_file_base = os.path.join(self.bg_dir, str(list_1_bg))

        list_2 = gs_dict.get("group_2_genes")
        list_2_bg = gs_dict.get("group_2_background")
        bg_2_file_base = os.path.join(self.bg_dir, str(list_2_bg))

        if list_1 and list_2:
            list_1_file = write_gs_to_tempfile(list_1)
            list_2_file = write_gs_to_tempfile(list_2)
        else:
            logger.error("MSET can't compare two lists of genes without being passed two lists of genes:")
            logger.error("Attempted GS IDs: {} {}".format(gs_dict.get('group_1_gsid'), gs_dict.get('group_2_gsid')))
            raise ValueError("Interest Genes and Top Genes are required")

        # Build the CLI command to run MSET, first the location of the MSET program
        func_call = self.cpp_path + " "
        # First argument is the number of trials to perform
        func_call += str(num_trials) + " "
        # Next is the location of the group 1 file, and its background file
        func_call += str(list_1_file.name) + " " + str(bg_1_file_base) + " "
        # Then the location of the group 2 file, and its background file
        func_call += str(list_2_file.name) + " " + str(bg_2_file_base) + " "
        # Finally, we currently only support Over-representation, using "-U" instead would test for under-representation
        func_call += "-O"

        self._results["intersect_genes"] = np.intersect1d(list_1, list_2).tolist()

        try:
            popen = subprocess.Popen([func_call], shell=True, stderr=PIPE)
            returncode = popen.wait()
        except Exception as e:
            logger.error('There was a problem calling the MSET c++ code: {}'.format(e))
            raise e

        if returncode != 0:
            logger.error('MSET failed and returned a non-zero code')
            try:
                error = popen.communicate()
                logger.error('Process reports: {}'.format(error))
                self._results['error'] = str(error)
            except IOError as e:
                logger.error('There was a problem writing MSET errors to file: {}'.format(e))
                raise e
        else:
            logger.info('MSET completed successfully')
            try:
                mset_data = tsv_file_to_dict(self.OUTPUT_DIR + '/mset_output.tsv')
                mset_hist = tsv_file_to_dict(self.OUTPUT_DIR + '/mset_hist.tsv')
                self._results['mset_data'] = mset_data
                self._results['mset_hist'] = mset_hist

            except Exception as e:
                logger.error('There was a problem writing MSET results to a file: {}'.format(e))
                raise e

        # These temp files were created with delete=False; remove them by name.
        # (NamedTemporaryFile.delete is a bool attribute, not a method -- calling it
        # raises "'bool' object is not callable" and masks the real result/error.)
        for _tmp in (list_1_file, list_2_file):
            try:
                os.unlink(_tmp.name)
            except OSError:
                pass

        self._results['gs_dict'] = gs_dict
        self._results['gs_ids'] = self._gsids
        self._results['gs_names'] = self._gsnames
        self._results['parameters'] = self._parameters


MSET = celery.register_task(MSET())
