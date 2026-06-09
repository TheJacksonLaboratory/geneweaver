#!/usr/bin/python
# USAGE: Combine.py input.odemat input.odepwd < parameters_json.txt > output_json.txt 2>status.txt

import tools.toolbase

from tools.celeryapp import celery

class Combine(tools.toolbase.GeneWeaverToolBase):
    name = "tools.Combine.Combine"

    def __init__(self, *args, **kwargs):
        self.init("Combine")
        self.urlroot=''

    def mainexec(self):
        pass

Combine = celery.register_task(Combine())
