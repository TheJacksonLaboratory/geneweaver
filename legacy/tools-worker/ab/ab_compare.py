#!/usr/bin/env python3
"""A/B harness — orchestrator + diff.

Runs the same tool with the same geneset inputs in the dev and sqa
geneweaver-legacy-tools pods (via `kubectl exec`), then canonicalizes and diffs
the two outputs so legitimate-but-cosmetic differences (the run uuid, URLs, and
the remapped internal ode_gene_id values) don't show up as false diffs — only
the meaningful numbers (jaccard values, p-values, overlap counts, set sizes) do.

Usage:
    ab_compare.py <ToolClassname> <gsid,gsid,...> [params_json] [timeout_s]

Examples:
    ab_compare.py JaccardSimilarity 396123,390337,392374
    ab_compare.py BooleanAlgebra   396123,390337,392374 '{"BooleanAlgebra_Relation":"Union","at_least":"2"}'
    ab_compare.py GeneSetViewer    396123,390337,392374

Requires: kubectl context on jax-cluster-dev-10 (namespaces dev + sqa), and the
runner copied into each pod (this script copies it automatically).
"""
import json, subprocess, sys, re, os

RUNNER_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_tool_in_env.py")
RUNNER_REMOTE = "/tmp/run_tool_in_env.py"
CONTAINER = "geneweaver-legacy-tools"
OUTDIR = "/tmp/ab_out"

# Keys whose values are environment-specific noise — dropped before diffing.
DROP_KEYS = {"output_prefix", "task_id", "runhash", "url", "gs_dict",
             "filename", "file", "img", "image"}
# Keys whose value is a gene/id list — compared by length only (ode_gene_id was
# remapped in dev, so raw IDs legitimately differ; the COUNT is the signal).
LEN_ONLY_KEYS = {"genes", "gene_ids", "ode_gene_ids", "geneids", "nodes",
                 "edges", "members", "emphasisgenes", "emphasis_genes"}


def pod(ns):
    out = subprocess.run(
        ["kubectl", "get", "pods", "-n", ns, "-l", "app=geneweaver-legacy-tools",
         "-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True, text=True)
    return out.stdout.strip()


def run_env(ns, tool, gsids, params_json, timeout):
    p = pod(ns)
    subprocess.run(["kubectl", "cp", RUNNER_LOCAL, f"{ns}/{p}:{RUNNER_REMOTE}", "-c", CONTAINER],
                   capture_output=True, text=True)
    cmd = ["kubectl", "exec", "-n", ns, p, "-c", CONTAINER, "--",
           "sh", "-c", f"python {RUNNER_REMOTE} {tool} {gsids} '{params_json}' {timeout}"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 120)
    blob = res.stdout
    m = re.search(r"===AB_JSON_START===\s*(.*?)\s*===AB_JSON_END===", blob, re.S)
    if not m:
        raise RuntimeError(f"[{ns}] no result captured. stderr/stdout tail:\n{(res.stderr or blob)[-1500:]}")
    return json.loads(m.group(1))


def canon(x, key=None):
    """Recursively canonicalize for diffing."""
    if isinstance(x, dict):
        return {k: canon(v, k) for k, v in sorted(x.items())
                if k.lower() not in DROP_KEYS}
    if isinstance(x, list):
        if key and key.lower() in LEN_ONLY_KEYS:
            return {"__len__": len(x)}
        cv = [canon(v) for v in x]
        try:  # sort scalar lists so order differences don't matter
            return sorted(cv, key=lambda v: json.dumps(v, sort_keys=True))
        except Exception:
            return cv
    if isinstance(x, float):
        return round(x, 5)
    if isinstance(x, str):
        # res_data is often a JSON string — parse so we compare structurally
        s = x.strip()
        if s[:1] in "{[" and s[-1:] in "}]":
            try:
                return canon(json.loads(s), key)
            except Exception:
                pass
        # strip the run uuid if it appears embedded in text
        return re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>", x)
    return x


def diff(a, b, path=""):
    out = []
    if type(a) is not type(b):
        out.append(f"{path or '/'}: type {type(a).__name__} != {type(b).__name__}")
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: out.append(f"{path}/{k}: only in sqa")
            elif k not in b: out.append(f"{path}/{k}: only in dev")
            else: out += diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: list len dev={len(a)} sqa={len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)): out += diff(x, y, f"{path}[{i}]")
    elif a != b:
        out.append(f"{path}: dev={a!r} sqa={b!r}")
    return out


def main():
    tool, gsids = sys.argv[1], sys.argv[2]
    params_json = sys.argv[3] if len(sys.argv) > 3 else "{}"
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 240
    os.makedirs(OUTDIR, exist_ok=True)

    print(f"== A/B: {tool} on genesets {gsids} ==")
    dev = run_env("dev", tool, gsids, params_json, timeout)
    sqa = run_env("sqa", tool, gsids, params_json, timeout)
    for env, d in (("dev", dev), ("sqa", sqa)):
        json.dump(d, open(f"{OUTDIR}/{tool}_{env}.json", "w"), indent=2)
        print(f"  {env}: state={d.get('async_state')} runhash={d.get('task_id')[:8]}")

    # sanity: both should have succeeded
    for env, d in (("dev", dev), ("sqa", sqa)):
        if d.get("async_state") != "SUCCESS":
            print(f"  !! {env} did not SUCCEED — res_status tail: "
                  f"{str(d.get('res_status'))[-200:]}")

    ca = canon(dev.get("res_data"))
    cb = canon(sqa.get("res_data"))
    d = diff(ca, cb)
    print(f"\n-- numeric/structural diff (dev vs sqa), gene-IDs & uuids ignored --")
    if not d:
        print("  ✅ MATCH — dev and sqa produced equivalent results.")
    else:
        print(f"  ⚠️  {len(d)} difference(s):")
        for line in d[:40]:
            print("   ", line)
        if len(d) > 40:
            print(f"    ... (+{len(d)-40} more)")
    print(f"\n  raw outputs: {OUTDIR}/{tool}_dev.json , {OUTDIR}/{tool}_sqa.json")


if __name__ == "__main__":
    main()
