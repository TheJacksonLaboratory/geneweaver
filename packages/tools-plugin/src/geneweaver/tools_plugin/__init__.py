"""The AsyncTask plugin for the GeneWeaver tools: the workflow, and where it sends each tool.

AsyncTask installs this package, and only this package: the tools and the worker that runs
them are `geneweaver-tools[temporal]`, deployed as GeneWeaver's own images. See the README.

Nothing is imported here, so `geneweaver.tools_plugin.payload` -- standard library only --
can be used by the GeneWeaver API without loading the Temporal SDK.
"""
