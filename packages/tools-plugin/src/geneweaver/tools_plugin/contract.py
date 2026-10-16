"""What the workflow and the workers must agree on, in one place.

The workflow runs inside AsyncTask; the activity runs on GeneWeaver's own workers. They are
released separately, so the names that join them are defined here and the workers import
them rather than restating them. `geneweaver-tools`' contract tests fail if the two disagree.
Change any of these only as a planned release of this package *and* the workers together.

Standard library only: it is imported from workflow code, which must be deterministic.

**Two workers, split by dependency profile, not one per tool:**

* **python** -- the seven tools that need only wheels (`scipy`/`scikit-learn` for DBSCAN's
  in-process default and JaccardClustering), and ABBA's database search.
* **native** -- MSET and PhenomeMap, which shell out to compiled TOOLBOX binaries (`MSETcpp`
  needs OpenMP, `bstrap` needs Boost) and so need a build toolchain in their image.

One image per tool would give seven near-identical images with nothing to isolate;
`asynctask-mpd-plugin` makes the same trade. Grouping by profile also keeps MSET's Monte
Carlo sampling and PhenomeMap's biclique enumeration -- the two slow tools -- off the worker
serving fast interactive runs.

**The queue names are constants, deliberately not configuration**, an exception to this
repository's rule that infrastructure comes from the environment. That rule assumes one
process reads the value; here two do, in different deployments. `task_queue_for` runs in
AsyncTask's worker, while the queue is consumed by ours. An environment override would reach
only one side, and every run would sit unclaimed until it timed out -- a split no test in
either repository could see. Being constants also makes them replay-safe: a replayed
workflow must schedule its activity on the queue it used the first time.
"""

#: The task queue of the python worker, and of any tool not listed in `NATIVE_TOOLS`.
PYTHON_TASK_QUEUE = "geneweaver-tools"

#: The task queue of the native worker.
NATIVE_TASK_QUEUE = "geneweaver-tools-native"

#: Tools whose runtime needs a compiled TOOLBOX binary. DBSCAN is **not** here: its
#: in-process implementation is the default and its binary only the legacy-parity fallback.
NATIVE_TOOLS: frozenset[str] = frozenset({"mset", "phenome_map"})

#: The activity the workflow schedules, by name: the workflow never imports it, so
#: AsyncTask never loads the code that runs a tool. Prefixed because activity names share
#: one flat namespace across every AsyncTask plugin, and a duplicate stops its worker.
ACTIVITY_NAME = "geneweaver_run_tool"

#: The activity's start-to-close deadline. Legacy's Celery worker used a 900 s soft limit;
#: tool runs are minutes at worst, and a generous ceiling still beats a run that hangs
#: forever (G3-739). `geneweaver.tools.framework.binary` keeps its own copy, because the
#: tools library must not depend on this package; a contract test pins the two together.
TOOL_RUN_TIMEOUT_SECONDS = 30 * 60


def task_queue_for(tool: str) -> str:
    """The queue whose worker can run `tool`. Called from workflow code, so it stays pure."""
    return NATIVE_TASK_QUEUE if tool in NATIVE_TOOLS else PYTHON_TASK_QUEUE
