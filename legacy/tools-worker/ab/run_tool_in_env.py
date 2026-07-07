#!/usr/bin/env python
"""A/B harness — single-environment tool runner.

Runs INSIDE a geneweaver-legacy-tools pod. Dispatches one tool Celery task the
same way the web blueprints do (insert a production.result row, then
celery.send_task with gsids/output_prefix/params), waits for completion, and
prints the result as JSON between sentinels so the orchestrator can capture it.

Usage (inside the pod):
    python run_tool_in_env.py <ToolClassname> <gsid,gsid,...> [params_json] [timeout_s]

Example:
    python run_tool_in_env.py BooleanAlgebra 396123,390337,392374 '{}' 240
"""
import os, sys, json, uuid, time

# The tools package lives in different dirs across images: /app/tools-worker
# (monorepo dev image) vs /app/src (prod/sqa image). Auto-detect and use it.
for _cand in ("/app/tools-worker", "/app/src", os.getcwd()):
    if os.path.exists(os.path.join(_cand, "tools", "celeryapp.py")):
        sys.path.insert(0, _cand)
        os.chdir(_cand)
        break
import psycopg2
from tools.celeryapp import celery


def db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USERNAME"], password=os.environ["DB_PASSWORD"],
        port=os.environ.get("DB_PORT", "5432"),
    )


def main():
    tool = sys.argv[1]
    gsids = [int(x) for x in sys.argv[2].split(",") if x.strip()]
    extra = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else {}
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 240

    conn = db(); conn.autocommit = True
    cur = conn.cursor()

    # Default params for this tool (same source the web UI uses), then overrides.
    cur.execute("select tp_name, tp_default from odestatic.tool_param where tool_classname=%s", (tool,))
    params = {n: v for n, v in cur.fetchall()}
    params.update(extra)

    cur.execute("select tool_name from odestatic.tool where tool_classname=%s", (tool,))
    tool_name = cur.fetchone()[0]
    # A valid (non-guest) user to own the result row.
    cur.execute("select usr_id from production.usr where is_guest is not true order by usr_id limit 1")
    usr_id = cur.fetchone()[0]

    task_id = str(uuid.uuid4())
    desc = "AB-test: %s on %d genesets" % (tool_name, len(gsids))
    cur.execute(
        """insert into production.result
           (usr_id,res_runhash,gs_ids,res_data,res_tool,res_description,res_status,res_started)
           values (%s,%s,%s,%s,%s,%s,'running', now())""",
        (usr_id, task_id, ",".join(map(str, gsids)), json.dumps(params), tool_name, desc),
    )

    celery.send_task(
        "tools.%s.%s" % (tool, tool),
        kwargs={"gsids": gsids, "output_prefix": task_id, "params": params},
        task_id=task_id,
    )

    # Wait for completion via the Celery result backend, then read the stored output.
    async_ret, async_state = None, None
    try:
        r = celery.AsyncResult(task_id)
        async_ret = r.get(timeout=timeout, propagate=False)
        async_state = r.state
    except Exception as e:  # noqa: BLE001
        async_state = "GET_ERROR:%s" % str(e).splitlines()[0][:120]

    # res_data in the result row is overwritten by the tool with its output.
    res_data, res_status, completed = None, None, None
    try:
        cur.execute("select res_data,res_status,res_completed from production.result where res_runhash=%s", (task_id,))
        row = cur.fetchone()
        if row:
            res_data, res_status, completed = row[0], row[1], (row[2].isoformat() if row[2] else None)
    except Exception:
        conn.rollback()

    out = {
        "tool": tool, "env": os.environ.get("DB_NAME"), "task_id": task_id,
        "gsids": gsids, "params": params,
        "async_state": async_state, "async_return": async_ret,
        "res_status": res_status, "res_completed": completed, "res_data": res_data,
    }
    print("===AB_JSON_START===")
    print(json.dumps(out, default=str))
    print("===AB_JSON_END===")


if __name__ == "__main__":
    main()
