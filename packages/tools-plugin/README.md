# GeneWeaver Tools Plugin

The AsyncTask plugin for the GeneWeaver analysis tools. AsyncTask depends on this package,
not on the tools.

It holds the workflow AsyncTask starts, the rule for which task queue each tool goes to,
and the checks on a request. It depends only on the Temporal SDK and imports no tool.

| Part | Package | Runs in |
| --- | --- | --- |
| Workflow, routing, request checks | `geneweaver-tools-plugin` | AsyncTask |
| The activity that runs a tool, its database look-ups, the worker | `geneweaver-tools[temporal]` | GeneWeaver's two tool workers |
| The tools | `geneweaver-tools` | The workers, and the API in-process |

## The agreement with the workers

The workflow and the workers are deployed separately, so what they share lives here, in
`geneweaver.tools_plugin.contract`, and the workers import it:

- the two task queues, `geneweaver-tools` (python) and `geneweaver-tools-native` (MSET and
  PhenomeMap, which need compiled binaries), and which tools go to which;
- the activity name, `geneweaver_run_tool`;
- the run timeout;
- the shape of a request, `{"tool": ..., "input": {...}}`, checked by
  `geneweaver.tools_plugin.payload`.

`geneweaver-tools`' contract tests fail if the workers disagree with any of these.

## Releases

| Change | Release |
| --- | --- |
| A new tool, or a fix inside one | `geneweaver-tools` and the worker images. AsyncTask is untouched. |
| Routing, the checks, or the workflow | This package, then AsyncTask. The workers too if the agreement changed. |
