"""Plan or publish a new, byte-verified F1 evidence archive. No network access.

Default is planning only. --execute requires passing final Windows/CI evidence.
An existing destination is never written; --verify-existing audits it in place.
Build binaries, ZIP containers, non-visible media, credentials and CI selfchecks
are excluded. Explicit visible PNG/JPEG files are byte-preserved. Official ZIP digests remain in the copied CI metadata; original
ZIP bytes are checked before publication and stay in the source evidence root.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
import zipfile
import importlib.util
import posixpath
import stat
import tempfile
import math
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
_identity_spec = importlib.util.spec_from_file_location(
    "f4_archive_identity", Path(__file__).with_name("f4_archive_identity.py"))
identity = importlib.util.module_from_spec(_identity_spec)
_identity_spec.loader.exec_module(identity)
EXPLICIT_SOURCE_SUFFIXES = {".patch", ".cc", ".hh"}
TEXT_SUFFIXES = {".json", ".md", ".log", ".txt", ".csv", ".ini", ".mac", ".py", ".yml", ".yaml"}
FORBIDDEN_COMPONENTS = {".git", ".ssh", ".codex", "credentials", "secrets", "__pycache__"}
SECRET_PATTERNS = {
    "bearer authorization": re.compile(r"Authorization\s*[:=]\s*[\"']?Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    "API credential": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "assigned credential": re.compile(r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|DEEPSEEK_API_KEY|GITHUB_TOKEN|GH_TOKEN)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{16,}", re.I),
    "signed download URL": re.compile(r"(?:X-Amz-Signature|X-Goog-Signature|[?&]sig)=[A-Za-z0-9%+/=_-]{12,}", re.I),
    "private key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError("Duplicate JSON key in archive source")
            result[key]=value
        return result
    return json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=unique,parse_constant=lambda token:(_ for _ in ()).throw(ValueError("Nonfinite JSON in archive source")))


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe_relative(root, value):
    if "\\" in value or PureWindowsPath(value).drive:raise ValueError("Unsafe Windows archive member path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(part in {"..", "."} for part in relative.parts):
        raise ValueError("Unsafe archive member path")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive member escapes destination")
    return path


def check_text(raw, path):
    if b"\x00" in raw:
        raise ValueError(f"Binary or NUL content refused: {path}")
    text = raw.decode("utf-8")
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            # Never include matched secret content in diagnostics.
            raise ValueError(f"Potential {label} refused in {path}")


def file_digest(path):
    value=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            value.update(chunk)
    return value.hexdigest()


def performance_check(source, expected_count):
    report=source/"report.json"
    result={"source":str(source.absolute()),"expected_samples":expected_count,"checks":[],"blockers":[],"scope":"Recorded executable/artifact identities are retained, not recomputed from paths that may now hold a later build; original input/macro/log bytes are rechecked."}
    if not report.is_file():
        result["blockers"].append("Performance report missing: "+str(report));return result
    data=read_json(report);samples=data.get("samples")
    if data.get("schema")!="g4usim_output_measurement_v1" or not isinstance(samples,list) or len(samples)!=expected_count:
        result["blockers"].append("Performance schema/sample count mismatch: "+str(report));return result
    result["samples"]=len(samples)
    executables=data.get("executables",[])
    labels=[row.get("label") for row in executables]
    if not labels or len(set(labels))!=len(labels) or any(not re.fullmatch(r"[A-Za-z0-9_-]+",label or "") or not re.fullmatch(r"[0-9a-f]{64}",row.get("sha256", "")) for label,row in zip(labels,executables)):
        result["blockers"].append("Invalid recorded performance executable identity")
    identities=set()
    for row in samples:
        identity=(row.get("label"),row.get("workload"),row.get("format"),row.get("repeat"))
        if identity in identities:result["blockers"].append("Duplicate performance sample identity")
        identities.add(identity)
        if (identity[0] not in labels or identity[1] not in {"hits","events","mesh"} or identity[2] not in {"csv","root","both","auto"} or type(identity[3]) is not int or identity[3]<0 or type(row.get("exit_code")) is not int or row["exit_code"]!=0 or type(row.get("events")) is not int or row["events"]<=0):
            result["blockers"].append("Invalid/failed performance sample");continue
        if any(type(row.get(key)) not in {int,float} or not math.isfinite(row[key]) or row[key]<0 for key in ("wall_seconds","python_verify_seconds","registered_bytes")):result["blockers"].append("Invalid performance measurement value")
        name="-".join(map(str,identity));sample=source/name
        for filename,key in (("main.ini","config_sha256"),("run.mac","macro_sha256"),("backend.log","log_sha256")):
            path=sample/filename;actual=file_digest(path) if path.is_file() else None
            match=actual==row.get(key) and isinstance(actual,str)
            result["checks"].append({"sample":name,"file":filename,"expected_sha256":row.get(key),"actual_sha256":actual,"matches":match})
            if not match:result["blockers"].append("Performance original bytes mismatch: "+str(path))
        hashes=row.get("artifact_sha256")
        if not isinstance(hashes,dict) or not hashes or any(not re.fullmatch(r"[0-9a-f]{64}",value) for value in hashes.values()):result["blockers"].append("Invalid recorded performance output hashes: "+name)
    rounds=data.get("rounds")
    workloads={row.get("workload") for row in samples};formats={row.get("format") for row in samples}
    if type(rounds) is not int or rounds<=0:
        result["blockers"].append("Invalid performance repeat count")
    else:
        expected={(label,workload,fmt,repeat) for label in labels for workload in workloads for fmt in formats for repeat in range(rounds)}
        if identities!=expected:result["blockers"].append("Performance experiment matrix is incomplete")
    return result


def link_check(plan,folder=None):
    spec=importlib.util.spec_from_file_location("f1_archive_doc_links",ROOT/"scripts/check_doc_links.py")
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    destination=Path(plan["destination"]).relative_to(ROOT).as_posix()
    tracked=set(subprocess.check_output(["git","ls-files","-z"],cwd=ROOT).decode("utf-8").split("\0"));tracked.discard("")
    available=tracked|{destination+"/"+row["archive_path"] for row in plan["files"]}
    directories=set()
    for name in available:
        while "/" in name:
            name=name.rsplit("/",1)[0];directories.add(name)
    records=[]
    for row in plan["files"]:
        if not row["archive_path"].endswith(".md"):continue
        future=destination+"/"+row["archive_path"]
        path=safe_relative(folder,row["archive_path"]) if folder is not None else Path(row["source"])
        content=checker.strip_fenced_blocks(path.read_text(encoding="utf-8"));links=[]
        for lineno,line in enumerate(content.splitlines(),1):
            for match in checker.LINK_RE.finditer(line):
                target=match.group(1)
                if target.startswith(checker.SKIP_PREFIXES):continue
                target=unquote(target.split("#",1)[0])
                if not target:continue
                relative=checker.repo_relative(target,str(ROOT));candidate=relative if relative is not None else target
                base="" if relative is not None else posixpath.dirname(future)
                resolved=posixpath.normpath(posixpath.join(base,candidate))
                exists=resolved in available or resolved in directories
                if not exists:
                    resolved=posixpath.normpath(posixpath.join(base,checker.LINE_SUFFIX_RE.sub("",candidate)));exists=resolved in available or resolved in directories
                links.append({"line":lineno,"target":target,"future_resolved":resolved,"portable":exists})
        records.append({"archive_path":row["archive_path"],"links":links,"broken_count":sum(not x["portable"] for x in links)})
    return {"scope":"Exact existing doc-links parser; Git tracked plus planned archive paths only, case-sensitive future layout; no source-out existence fallback; external URLs and anchors not asserted", "markdown_files":len(records),"local_links":sum(len(x["links"]) for x in records),"broken_links":sum(x["broken_count"] for x in records),"records":records}


def check_source_zips(plan):
    for row in plan["artifact_zip_digest_checks"]+plan.get("historical_zip_digest_checks",[]):
        path=Path(row["zip_source"])
        if not path.is_file() or "sha256:"+file_digest(path)!=row["official_digest"] or not row["matches"]:
            raise ValueError("Official source ZIP changed after planning: "+row["name"])


def review_plan(plan):
    blockers=list(plan["preflight_blockers"])+["Missing source: "+name for name in plan["missing_sources"]]
    checked=0
    for row in plan["files"]:
        path=Path(row["source"])
        if not path.is_file() or path.is_symlink() or path.stat().st_size!=row["size"] or file_digest(path)!=row["sha256"]:
            blockers.append("Planned source changed: "+str(path))
        else:checked+=1
    links=link_check(plan)
    if links["broken_links"]:blockers.append("Nonportable local links")
    if blockers:return {"status":"blocked_plan_review","archive_published":False,"source_files_verified":checked,"blockers":blockers,"link_check":links}
    check_source_zips(plan)
    # A private disposable review workspace, never the publication destination.
    with tempfile.TemporaryDirectory(prefix="f1-archive-review-",dir=ROOT/"out/collab") as temporary:
        stage=Path(temporary)
        for row in plan["files"]:
            raw=Path(row["source"]).read_bytes()
            if len(raw)!=row["size"] or digest(raw)!=row["sha256"]:raise ValueError("Source changed during review copy")
            write_new(safe_relative(stage,row["archive_path"]),raw)
        gates=report_gates(stage,plan)
    return {"status":"review_passed_not_published","archive_published":False,"source_files_verified":checked,"link_check":links,"report_gates":gates}


# Current F1 release workflows: identities, not merely four ZIPs/twelve files.
CI_TOPOLOGY = {
    "m0-report-windows-latest": {"workflow":".github/workflows/m0-static-gui.yml","job":"windows-latest / Python 3.11","profiles":["static","gui"]},
    "m0-report-ubuntu-latest": {"workflow":".github/workflows/m0-static-gui.yml","job":"ubuntu-latest / Python 3.11","profiles":["static","gui"]},
    "linux-evidence-11.3.2": {"workflow":".github/workflows/linux-geant4.yml","job":"ubuntu-24.04 / Geant4 11.3.2","profiles":["static","gui","backend","integration"]},
    "linux-evidence-11.4.3": {"workflow":".github/workflows/linux-geant4.yml","job":"ubuntu-24.04 / Geant4 11.4.3","profiles":["static","gui","backend","integration"]},
}


def validate_ci_topology(folder,expected_head,actual_report_paths=None):
    folder=Path(folder);ci=read_json(folder/"ci-evidence.json")
    def need(condition,message):
        if not condition:raise ValueError("CI topology: "+message)
    def positive(value):return type(value) is int and value>0
    need(isinstance(expected_head,str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})",expected_head),"invalid frozen head identity")
    need(ci.get("head_sha")==expected_head and ci.get("status")=="passed" and ci.get("complete") is True,"summary identity/terminal status mismatch")
    runs=ci.get("runs");need(isinstance(runs,list) and len(runs)==2,"exactly two workflow runs required")
    workflow_runs={};job_ids=set();official={};links={}
    for declared in runs:
        need(isinstance(declared,dict) and positive(declared.get("id")),"invalid declared run identity")
        run_id=declared["id"]
        raw=read_json(folder/f"{run_id}-run.json")
        workflow=raw.get("path")
        need(workflow in {x["workflow"] for x in CI_TOPOLOGY.values()} and workflow not in workflow_runs,"duplicate/unknown workflow identity")
        need(raw.get("id")==run_id and raw.get("head_sha")==expected_head and raw.get("status")=="completed" and raw.get("conclusion")=="success" and raw.get("event")=="push","original run must be completed/success at the frozen push head")
        need(positive(raw.get("run_attempt")),"missing original run attempt")
        for key in ("head_sha","conclusion","path","event","run_attempt"):
            need(declared.get(key)==raw.get(key),"summary run differs from original "+key)
        workflow_runs[workflow]=run_id
        jobs_doc=read_json(folder/f"{run_id}-jobs.json");jobs=jobs_doc.get("jobs")
        expected_jobs={x["job"] for x in CI_TOPOLOGY.values() if x["workflow"]==workflow}
        need(isinstance(jobs,list) and len(jobs)==len(expected_jobs),"original job set size mismatch")
        by_name={}
        for job in jobs:
            need(isinstance(job,dict) and positive(job.get("id")) and job["id"] not in job_ids,"duplicate/invalid original job ID")
            job_ids.add(job["id"])
            need(job.get("name") in expected_jobs and job["name"] not in by_name,"duplicate/missing/unknown matrix job")
            need(job.get("run_id")==run_id and job.get("status")=="completed" and job.get("conclusion")=="success","original job is not terminal-success in the declared run")
            if "head_sha" in job and job["head_sha"] is not None:need(job["head_sha"]==expected_head,"original job head mismatch")
            if "run_attempt" in job and job["run_attempt"] is not None:need(job["run_attempt"]==raw["run_attempt"],"original job attempt mismatch")
            need((folder/f"job-{job['id']}.log").is_file(),"original successful job log missing")
            by_name[job["name"]]=job
        need(set(by_name)==expected_jobs,"original matrix jobs incomplete")
        declared_jobs=declared.get("jobs")
        need(isinstance(declared_jobs,list) and len(declared_jobs)==len(jobs),"summary job set mismatch")
        seen=set()
        for job in declared_jobs:
            need(job.get("name") in by_name and job["name"] not in seen,"duplicate/unknown summary job")
            seen.add(job["name"]);original=by_name[job["name"]]
            need(job.get("id")==original["id"] and job.get("conclusion")==original["conclusion"] and job.get("log_present") is True,"summary job differs from original terminal evidence")
        need(seen==expected_jobs,"summary matrix jobs incomplete")
        artifact_doc=read_json(folder/f"{run_id}-artifacts.json");artifacts=artifact_doc.get("artifacts")
        names={name for name,x in CI_TOPOLOGY.items() if x["workflow"]==workflow}
        need(isinstance(artifacts,list) and len(artifacts)==len(names),"original artifact identity set size mismatch")
        for artifact in artifacts:
            name=artifact.get("name")
            need(name in names and name not in official and positive(artifact.get("id")),"duplicate/unknown original artifact")
            reference=artifact.get("workflow_run",{})
            need(reference.get("id")==run_id and reference.get("head_sha")==expected_head,"official artifact run/head association mismatch")
            need(artifact.get("expired") is False and re.fullmatch(r"sha256:[0-9a-f]{64}",artifact.get("digest", "")),"official artifact digest/expiry metadata invalid")
            official[name]=artifact
            links[name]={"run_id":run_id,"job_id":by_name[CI_TOPOLOGY[name]["job"]]["id"],"workflow":workflow,"profiles":CI_TOPOLOGY[name]["profiles"]}
    need(set(official)==set(CI_TOPOLOGY) and len({x["id"] for x in official.values()})==len(CI_TOPOLOGY),"official artifacts duplicate/incomplete")
    summary_artifacts=ci.get("artifacts")
    need(isinstance(summary_artifacts,list) and len(summary_artifacts)==len(CI_TOPOLOGY),"summary artifact identities incomplete")
    seen=set()
    for row in summary_artifacts:
        name=row.get("name")
        need(name in official and name not in seen,"duplicate/unknown summary artifact")
        seen.add(name);raw=official[name]
        need(row.get("id")==raw["id"] and row.get("official_digest")==raw["digest"] and row.get("sha256")==raw["digest"],"summary artifact identity differs from original official metadata")
    reports=ci.get("reports");need(isinstance(reports,list),"summary report list missing")
    pairs=set();paths=set();records=[]
    for row in reports:
        name,profile=row.get("artifact"),row.get("profile")
        need(name in CI_TOPOLOGY and profile in CI_TOPOLOGY[name]["profiles"],"unexpected artifact/profile pair")
        pair=(name,profile);need(pair not in pairs,"duplicate artifact/profile report")
        pairs.add(pair)
        value=row.get("path");need(isinstance(value,str) and value,"invalid report path")
        relative=PurePosixPath(value.replace("\\","/"))
        path=relative.as_posix();need(relative.parts[0]==name and relative.name=="report.json" and path not in paths,"duplicate/misattributed report path")
        local=safe_relative(folder,path);need(local.is_file() and not local.is_symlink(),"summary report bytes absent")
        data=read_json(local)
        need(data.get("profile")==profile and data.get("git_head")==expected_head,"actual report profile/head differs from summary association")
        need(type(row.get("strict_gate_exit_code")) is int and row["strict_gate_exit_code"]==0 and row.get("problems")==[],"summary did not record a clean strict report gate")
        paths.add(path);records.append({"path":path,"artifact":name,"profile":profile,**links[name]})
    expected={(name,profile) for name,x in CI_TOPOLOGY.items() for profile in x["profiles"]}
    need(pairs==expected,"required artifact/profile coverage incomplete")
    if actual_report_paths is None:
        actual_report_paths=[p.relative_to(folder).as_posix() for p in folder.rglob("report.json")]
    actual=[PurePosixPath(str(path).replace("\\","/")).as_posix() for path in actual_report_paths]
    need(len(actual)==len(set(actual)) and set(actual)==paths,"actual archived report paths do not exactly equal the CI summary")
    return {"status":"passed","head_sha":expected_head,"workflow_runs":workflow_runs,"artifacts":links,"reports":sorted(records,key=lambda x:x["path"]),"report_count":len(paths)}


def read_historical_ci(folder):
    """Recognize the two saved failed-round receipts, never as release success.

    Summary schema errors raise. Missing historical job logs are explicit
    collection blockers so a plan can still inventory all existing evidence.
    Official ZIPs remain at source, but are checked before archive publication.
    """
    folder=Path(folder)
    def need(condition,message):
        if not condition:raise ValueError("Historical CI: "+message)
    def integer(value):return type(value) is int and value>=0
    def read(name):
        path=safe_relative(folder,name)
        need(path.is_file() and not path.is_symlink(),"missing original evidence "+name)
        return read_json(path)
    summary_path=folder/"failed-round-summary.json"
    if not summary_path.is_file():
        ci=read("ci-evidence.json")
        topology=validate_ci_topology(folder,ci.get("head_sha"))
        return {"summary_file":"ci-evidence.json","summary_format":"ci_evidence_passed_v1",
                "recorded_head":ci["head_sha"],"recorded_status":"passed", "recorded_complete":True,
                "reports":topology["report_count"],"collection_blockers":[],"zip_digest_checks":[],
                "meaning":"retained original history, not release acceptance"}
    summary=read("failed-round-summary.json")
    need(isinstance(summary,dict),"failed summary is not an object")
    short={"head","status","reports","boundary"}
    rich={"head_sha","status","stage_acceptance","evidence_collection_complete","linux_run","m0_run",
          "reports_total","strict_pass_reports","strict_rejected_reports","case_executions",
          "passed_case_executions","failed_case_executions","artifacts","job_logs","reports","failures","boundary"}
    if set(summary)==short:
        schema="failed_round_compact_v1";head=summary["head"]
    elif set(summary)==rich:
        schema="failed_round_audited_v1";head=summary["head_sha"]
        need(summary["stage_acceptance"]=="not_passed" and summary["evidence_collection_complete"] is True,
             "audited summary must explicitly separate complete collection from failed acceptance")
    else:raise ValueError("Historical CI: unknown or incomplete failed summary schema")
    need(isinstance(head,str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})",head),"invalid failed head")
    need(summary["status"]=="failed" and isinstance(summary["boundary"],str) and summary["boundary"].strip(),
         "failed receipt status/boundary missing")
    frozen=read("frozen-case-manifest.json")
    need(frozen.get("head_sha")==head and isinstance(frozen.get("profiles"),dict),"frozen identity mismatch")
    rows=summary["reports"]
    need(isinstance(rows,list) and rows,"report list is empty/missing")
    reports={};pairs={};failures=[];cases_total=passed_total=0
    compact_row={"path","cases","failures"}
    audited_row={"artifact","profile","path","report_sha256","cases","assertions","failures",
                 "strict_gate_exit_code","triage_integrity_only","release_accepted","git_dirty"}
    for row in rows:
        need(isinstance(row,dict) and set(row)==(compact_row if schema=="failed_round_compact_v1" else audited_row),
             "unknown or incomplete report row")
        value=row["path"];need(isinstance(value,str) and value,"report path missing")
        relative=PurePosixPath(value.replace("\\","/"));path=relative.as_posix()
        need(relative.name=="report.json" and path not in reports and relative.parts[0] in CI_TOPOLOGY,"duplicate/unknown report path")
        local=safe_relative(folder,path);data=read(path)
        artifact=relative.parts[0];profile=data.get("profile");pair=(artifact,profile)
        need(profile in CI_TOPOLOGY[artifact]["profiles"] and pair not in pairs,"duplicate/unknown report profile")
        need(data.get("git_head")==head,"report head mismatch")
        for key in ("source_fingerprint","tests_content_fingerprint"):
            need(isinstance(frozen.get(key),str) and data.get(key)==frozen[key],"report/freeze "+key+" mismatch")
        results=data.get("results");expected=frozen["profiles"].get(profile)
        need(isinstance(results,list) and results and isinstance(expected,list),"report/freeze cases missing")
        names=[case.get("name") for case in results]
        need(len(names)==len(set(names)) and set(names)==set(expected),"report case set mismatch")
        need(integer(row["cases"]) and row["cases"]==len(results),"report case count mismatch")
        bad=[]
        for case in results:
            need(case.get("status") in {"pass","fail"} and type(case.get("exit_code")) is int,"incomplete case status")
            need((case["exit_code"]==0)==(case["status"]=="pass"),"case exit/status mismatch")
            if case["status"]!="pass":bad.append(case)
        cases_total+=len(results);passed_total+=len(results)-len(bad)
        failures.extend({"artifact":artifact,"profile":profile,"case":case["name"],"status":case["status"],
                         "exit_code":case["exit_code"],"assertions":case.get("assertions_executed"),
                         "path":str(relative.parent/PurePosixPath(case["log"].replace("\\","/")).name),
                         "log_sha256":case.get("log_sha256")} for case in bad)
        expected_bad=[{"name":case["name"],"status":case["status"],"exit_code":case["exit_code"]} for case in bad]
        if schema=="failed_round_compact_v1":
            need(row["failures"]==expected_bad,"compact failure list mismatch")
        else:
            need(row["artifact"]==artifact and row["profile"]==profile and row["report_sha256"]==file_digest(local),"audited report association/hash mismatch")
            need(row["failures"]==[case["name"] for case in bad],"audited failure list mismatch")
            need(type(row["strict_gate_exit_code"]) is int and row["strict_gate_exit_code"]==(1 if bad else 0),"audited gate outcome mismatch")
            need(row["triage_integrity_only"] is bool(bad) and row["release_accepted"] is (not bad),"audited report acceptance mismatch")
            need(integer(row["assertions"]) and row["assertions"]==data.get("assertions_executed_total") and row["git_dirty"] is data.get("git_dirty"),"audited assertions/source state mismatch")
        reports[path]={"artifact":artifact,"profile":profile,"failures":len(bad)};pairs[pair]=path
    actual={p.relative_to(folder).as_posix() for p in folder.rglob("report.json")}
    need(set(reports)==actual,"declared report set differs from all preserved reports")
    need(failures,"failed summary contains no failing case")
    runs={};jobs={};official={};zip_checks=[];blockers=[];expected_pairs=set()
    run_files=sorted(folder.glob("*-run.json"))
    need(len(run_files)==2,"exactly two original workflow run receipts required")
    for path in run_files:
        raw=read(path.name);run_id=raw.get("id");workflow=raw.get("path")
        need(type(run_id) is int and run_id>0 and path.name==f"{run_id}-run.json","original run ID mismatch")
        need(workflow in {x["workflow"] for x in CI_TOPOLOGY.values()} and workflow not in runs,"duplicate/unknown workflow")
        need(raw.get("head_sha")==head and raw.get("status")=="completed" and raw.get("conclusion") in {"success","failure"} and raw.get("event")=="push","nonterminal or mismatched original run")
        need(type(raw.get("run_attempt")) is int and raw["run_attempt"]>0,"original run attempt missing")
        runs[workflow]=raw
        original_jobs=read(f"{run_id}-jobs.json").get("jobs")
        expected_jobs={x["job"] for x in CI_TOPOLOGY.values() if x["workflow"]==workflow}
        need(isinstance(original_jobs,list) and len(original_jobs)==len(expected_jobs) and {x.get("name") for x in original_jobs}==expected_jobs,"original matrix jobs incomplete")
        if raw["conclusion"]=="success":
            need(all(job.get("conclusion")=="success" for job in original_jobs),"successful original run contains an unsuccessful job")
        for job in original_jobs:
            jid=job.get("id")
            need(type(jid) is int and jid>0 and jid not in jobs and job.get("run_id")==run_id,"invalid/duplicate job identity")
            need(job.get("status")=="completed" and job.get("conclusion") in {"success","failure"},"nonterminal original job")
            if job["conclusion"]=="success":
                need(not any(step.get("conclusion") in {"failure","cancelled","timed_out","action_required","startup_failure"}
                             for step in job.get("steps",[])),"successful original job contains an unsuccessful step")
            log=folder/f"job-{jid}.log"
            if not log.is_file() or not log.stat().st_size:blockers.append("Historical job log missing/empty: "+str(log))
            jobs[jid]=job
            artifact=next(name for name,x in CI_TOPOLOGY.items() if x["workflow"]==workflow and x["job"]==job["name"])
            step_names=({"static":"Run static tests on Linux","gui":"Run offscreen GUI tests on Linux","backend":"Run backend tests on Linux","integration":"Run integration tests on Linux"}
                        if workflow.endswith("linux-geant4.yml") else {"static":"Verify tracked source inventory and static tests","gui":"Run offscreen GUI tests"})
            for profile,step_name in step_names.items():
                matching=[s for s in job.get("steps",[]) if s.get("name")==step_name]
                need(len(matching)==1 and matching[0].get("status")=="completed" and matching[0].get("conclusion") in {"success","failure","skipped"},"original profile step missing/nonterminal")
                result=matching[0]["conclusion"]
                if result!="skipped":
                    pair=(artifact,profile);expected_pairs.add(pair)
                    need(pair in pairs and (reports[pairs[pair]]["failures"]>0)==(result=="failure"),"original step/report failure mismatch")
        artifacts=read(f"{run_id}-artifacts.json").get("artifacts")
        expected_artifacts={name for name,x in CI_TOPOLOGY.items() if x["workflow"]==workflow}
        need(isinstance(artifacts,list) and len(artifacts)==len(expected_artifacts) and {x.get("name") for x in artifacts}==expected_artifacts,"official artifacts incomplete")
        for artifact in artifacts:
            name=artifact["name"];ref=artifact.get("workflow_run",{});sha=artifact.get("digest","")
            need(name not in official and type(artifact.get("id")) is int and artifact["id"]>0,"duplicate/invalid artifact")
            need(ref.get("id")==run_id and ref.get("head_sha")==head and re.fullmatch(r"sha256:[0-9a-f]{64}",sha),"official artifact association/hash missing")
            archive=folder/(name+".zip")
            need(archive.is_file() and "sha256:"+file_digest(archive)==sha,"original historical ZIP missing/changed: "+name)
            official_members=set()
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    need(not stat.S_ISLNK(member.external_attr>>16),"linked historical ZIP member")
                    if member.is_dir():continue
                    extracted=safe_relative(folder/name,member.filename)
                    relative=extracted.relative_to(folder/name).as_posix()
                    need(relative not in official_members,"duplicate historical ZIP file member")
                    official_members.add(relative)
                    need(extracted.is_file() and file_digest(extracted)==digest(bundle.read(member)),"historical ZIP/extracted bytes mismatch")
            extracted_members={path.relative_to(folder/name).as_posix() for path in (folder/name).rglob("*") if path.is_file()}
            need(extracted_members==official_members,"historical artifact file set differs from official ZIP members: "+name)
            official[name]={**artifact,"run_id":run_id}
            zip_checks.append({"zip_source":str(archive.absolute()),"name":name,"official_digest":sha,"matches":True,"category":"historical_ci"})
    need(set(pairs)==expected_pairs,"preserved reports do not match executed profile steps")
    need(set(official)==set(CI_TOPOLOGY) and len({x["id"] for x in official.values()})==4,"official artifact identity set mismatch")
    need(any(x["conclusion"]=="failure" for x in runs.values()),"failed summary has no failed original run")
    backfill=None
    if schema=="failed_round_compact_v1":
        # This is the explicitly saved first-round sidecar, not a generic
        # invented attestation. The Ubuntu M0 log predates this three-log
        # backfill and has presence/manifest evidence only, not this receipt.
        sidecar_name="job-log-backfill-20261030.json"
        sidecar=read(sidecar_name)
        need(isinstance(sidecar,dict) and set(sidecar)=={"recorded_utc","source","correction","logs"},"unknown or incomplete compact backfill receipt")
        need(sidecar["source"]=="GitHub connector fetch_workflow_job_logs decoded content" and
             isinstance(sidecar["recorded_utc"],str) and sidecar["recorded_utc"].strip() and
             isinstance(sidecar["correction"],str) and sidecar["correction"].strip(),"compact backfill source/time/correction missing")
        expected_ids={jid for jid,job in jobs.items() if job["name"]!="ubuntu-latest / Python 3.11"}
        legacy_ids=set(jobs)-expected_ids
        rows=sidecar["logs"]
        need(len(expected_ids)==3 and len(legacy_ids)==1 and isinstance(rows,list) and len(rows)==len(expected_ids),"compact backfill log roster incomplete")
        seen=set()
        for row in rows:
            need(isinstance(row,dict) and set(row)=={"job_id","path","bytes","sha256"},"unknown or incomplete compact backfill log row")
            jid=row["job_id"]
            need(type(jid) is int and jid in expected_ids and jid not in seen,"duplicate/unknown compact backfill job ID")
            seen.add(jid)
            need(row["path"]==f"job-{jid}.log" and type(row["bytes"]) is int and row["bytes"]>0 and
                 isinstance(row["sha256"],str) and re.fullmatch(r"[0-9a-f]{64}",row["sha256"]),"compact backfill path/size/digest invalid")
            log=safe_relative(folder,row["path"])
            need(log.is_file() and log.stat().st_size==row["bytes"] and file_digest(log)==row["sha256"],"compact backfill job log differs from receipt")
        need(seen==expected_ids,"compact backfill job roster mismatch")
        backfill={"path":sidecar_name,"sha256":file_digest(folder/sidecar_name),"verified_job_ids":sorted(seen),
                  "legacy_presence_only_job_ids":sorted(legacy_ids),
                  "meaning":"Three decoded connector logs match their saved receipt; the older Ubuntu M0 log has no backfill hash attestation. SHA is not a signature."}
    if schema=="failed_round_audited_v1":
        need(summary["linux_run"]==runs[".github/workflows/linux-geant4.yml"]["id"] and summary["m0_run"]==runs[".github/workflows/m0-static-gui.yml"]["id"],"summary workflow association mismatch")
        counts={"reports_total":len(reports),"strict_pass_reports":sum(not x["failures"] for x in reports.values()),"strict_rejected_reports":sum(bool(x["failures"]) for x in reports.values()),
                "case_executions":cases_total,"passed_case_executions":passed_total,"failed_case_executions":len(failures)}
        need(all(integer(summary[key]) and summary[key]==value for key,value in counts.items()),"audited aggregate counts mismatch")
        declared=summary["artifacts"]
        need(isinstance(declared,list) and len(declared)==4 and {x.get("name") for x in declared}==set(official),"audited artifact list incomplete")
        for row in declared:
            raw=official[row["name"]]
            need(row.get("id")==raw["id"] and row.get("run_id")==raw["run_id"] and row.get("official_digest")==raw["digest"]==row.get("actual_sha256") and row.get("zip_bytes")== (folder/(row["name"]+".zip")).stat().st_size,"audited artifact receipt mismatch")
        declared=summary["job_logs"]
        need(isinstance(declared,list) and len(declared)==len(jobs) and {x.get("id") for x in declared}==set(jobs),"audited job-log list incomplete")
        for row in declared:
            raw=jobs[row["id"]];log=folder/f"job-{row['id']}.log"
            need(all(row.get(key)==raw[key] for key in ("id","run_id","name","status","conclusion")) and row.get("log")==log.name,"audited job-log association mismatch")
            need(log.is_file() and row.get("log_bytes")==log.stat().st_size and row.get("log_sha256")==file_digest(log),"audited job log missing/changed")
        declared=summary["failures"]
        need(isinstance(declared,list) and len(declared)==len(failures),"audited failure detail list incomplete")
        for row,actual_failure in zip(declared,failures):
            need(all(row.get(key)==value for key,value in actual_failure.items()),"audited failed case differs from original report")
            log=safe_relative(folder,actual_failure["path"])
            need(log.is_file() and row.get("log_bytes")==log.stat().st_size and row.get("log_sha256")==file_digest(log),"audited failed case log missing/changed")
        if (folder/"ci-evidence.json").is_file():
            ci=read("ci-evidence.json")
            need(ci.get("head_sha")==head and ci.get("status")=="not_passed" and ci.get("complete") is True,"companion CI summary contradicts failed collection")
            need({r.get("path","").replace("\\","/") for r in ci.get("reports",[])}==set(reports),"companion CI report set differs")
    return {"summary_file":"failed-round-summary.json","summary_format":schema,"recorded_head":head,
            "recorded_status":"failed","recorded_complete":not blockers,"reports":len(reports),
            "failed_case_executions":len(failures),"case_executions":cases_total,
            "collection_blockers":blockers,"zip_digest_checks":zip_checks,
            "job_log_backfill":backfill,
            "meaning":"retained original failure, not release acceptance"}


def build_plan(options):
    target = options.destination.absolute()
    if not target.resolve().is_relative_to(ROOT.resolve()):raise ValueError("Archive destination must stay within the current workspace")
    selected, excluded, missing, blockers = {}, [], [], []
    roots = []
    required_reports = []
    plain_markdown = {path.absolute() for path in options.plain_markdown_source}
    plain_markdown_seen = set()

    def add_file(source, relative, category, *, explicit=False):
        source = Path(source).absolute()
        if not source.is_file():
            missing.append(str(source)); return
        if not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Selected archive source escapes the current workspace")
        for ancestor in [source,*source.parents]:
            if ancestor==ROOT:break
            if ancestor.is_symlink() or (getattr(ancestor.lstat(),"st_file_attributes",0)&getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",1024)):
                raise ValueError("Linked/reparse source refused")
        # The authorized workspace itself lives below .codex; evaluate only
        # selected archive members, never trusted ancestor folder names.
        member_parts = PurePosixPath(str(relative).replace("\\", "/")).parts
        if source.is_symlink() or any(part.lower() in FORBIDDEN_COMPONENTS or "selfcheck" in part.lower() for part in member_parts):
            excluded.append({"path": str(source), "reason": "link, private, or historical selfcheck path"}); return
        is_text=source.suffix.lower() in TEXT_SUFFIXES or (explicit and source.suffix.lower() in EXPLICIT_SOURCE_SUFFIXES)
        if category=="visible" and source.suffix.lower() in {".png",".jpg",".jpeg"}:
            raw=source.read_bytes()
            valid=(raw.startswith(b"\x89PNG\r\n\x1a\n") if source.suffix.lower()==".png" else raw.startswith(b"\xff\xd8\xff"))
            if not valid:raise ValueError("Visible image signature mismatch")
        elif not is_text:
            excluded.append({"path": str(source), "reason": "binary/media/container or unapproved extension"}); return
        raw = source.read_bytes()
        if is_text:check_text(raw, source)
        key = PurePosixPath(relative).as_posix()
        original_key = None
        if source in plain_markdown:
            if source.suffix.lower() != ".md" or not key.endswith(".md"):
                raise ValueError("Plain Markdown mapping requires a selected .md source/member")
            original_key = key
            key += ".txt"
            plain_markdown_seen.add(source)
        safe_relative(target, key)
        item = {"source": str(source), "archive_path": key, "size": len(raw), "sha256": digest(raw), "category": category}
        if original_key is not None:
            item.update(original_archive_path=original_key, rendering="literal_text",
                        archive_path_reason="Preserve original evidence bytes; embedded links assume its original publication location")
        if key in selected and selected[key] != item:
            raise ValueError(f"Conflicting archive destination: {key}")
        selected[key] = item

    def add_tree(source, relative, category, *, required=False):
        source = Path(source).absolute()
        if not source.is_dir():
            if required: missing.append(str(source))
            return
        if target.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(target.resolve()):
            raise ValueError("Archive destination and selected source tree must not contain one another")
        roots.append({"source": str(source), "archive_prefix": relative, "category": category})
        for path in sorted(source.rglob("*")):
            if path.is_file():
                add_file(path, str(PurePosixPath(relative) / path.relative_to(source).as_posix()), category)

    for index, report in enumerate(options.windows_report, 1):
        report = report.absolute()
        if report.name != "report.json":
            raise ValueError("Windows report argument must name the original report.json")
        prefix = f"windows/final-{index}"
        required_reports.append(f"{prefix}/{report.name}")
        if not report.is_file():
            missing.append(str(report))
        add_tree(report.parent, prefix, "accepted_windows", required=True)
    add_tree(options.ci_root, "ci", "accepted_ci", required=True)
    historical_rounds = []
    for index, source in enumerate(options.historical_ci_root, 1):
        if source.resolve() == options.ci_root.resolve():
            raise ValueError("A final CI root cannot simultaneously be a historical CI round")
        prefix = f"history/ci-round-{index}-{source.name}"
        add_tree(source, prefix, "historical_ci", required=True)
        try:
            record=read_historical_ci(source)
        except (ValueError,OSError,KeyError,TypeError,zipfile.BadZipFile) as error:
            record={"recorded_status":"invalid_or_incomplete","recorded_complete":False,
                    "collection_blockers":[str(error)],"zip_digest_checks":[]}
        historical_rounds.append({"source":str(source.absolute()),"category":"historical_ci","archive_prefix":prefix,**record})
        blockers.extend(record["collection_blockers"])
    for index, source in enumerate(options.historical_windows_root, 1):
        if any(report.absolute().is_relative_to(source.absolute()) for report in options.windows_report):
            raise ValueError("Final Windows report cannot also belong to a historical Windows round")
        prefix = f"history/windows-round-{index}-{source.name}"
        add_tree(source, prefix, "historical_windows", required=True)
        records = []
        for report in sorted(source.rglob("report.json")) if source.is_dir() else []:
            value = read_json(report)
            records.append({"report": str(report), "head": value.get("git_head"), "profile": value.get("profile"),
                            "statuses": [case.get("status") for case in value.get("results", [])]})
        historical_rounds.append({"source": str(source.absolute()), "category": "historical_windows", "archive_prefix": prefix,
                                  "reports": records})
        if not records:
            blockers.append("Historical Windows round is still awaiting its terminal report: " + str(source))
    for index, report in enumerate(options.historical_report, 1):
        add_tree(report.absolute().parent, f"history/explicit-report-{index}", "historical", required=True)
    for index, source in enumerate(options.include_root, 1):
        add_tree(source, f"additional/{index}-{source.name}", "additional", required=True)
    for index, source in enumerate(options.include_file, 1):
        add_file(source, f"additional-files/{index}-{source.name}", "additional", explicit=True)
    if options.root_readme is not None:
        add_file(options.root_readme, "README.md", "active_index")
    for category, sources in (("review",options.review_root),("visible",options.visible_root)):
        for index, source in enumerate(sources,1):
            add_tree(source,f"{category}/{index}-{source.name}",category,required=True)
    for category,sources in (("review",options.review_file),("design_response",options.deepseek_response),("design_receipt",options.deepseek_receipt)):
        for index,source in enumerate(sources,1):
            add_file(source,f"{category}/{index}-{source.name}",category,explicit=True)
    performance_checks=[]
    for category,sources,expected_count in (("performance",options.performance_root,options.expected_performance_samples),("buffer_performance",options.buffer_performance_root,options.expected_buffer_samples)):
        if not sources:blockers.append("Missing explicit "+category+" source root")
        for index,source in enumerate(sources,1):
            prefix=f"{category}/{index}-{source.name}"
            roots.append({"source":str(source.absolute()),"archive_prefix":prefix,"category":category})
            report=source/"report.json"
            add_file(report,f"{prefix}/report.json",category)
            record=performance_check(source,expected_count)
            performance_checks.append(record)
            blockers.extend(record["blockers"])
            if source.is_dir():
                # Preserve reports/capabilities, original sample inputs/logs and
                # small provenance receipts. Large CSV/ROOT outputs and executables
                # remain at source with their original recorded SHA identities.
                for path in sorted(source.rglob("*")):
                    if not path.is_file() or path==report:continue
                    rel=path.relative_to(source)
                    if len(rel.parts)==1 or (len(rel.parts)==2 and path.name in {"main.ini","run.mac","backend.log"}) or (len(rel.parts)==3 and rel.parts[1]=="output" and (path.name in {"run_summary.txt","run_metadata.json"} or path.name.startswith("effective_config"))):
                        add_file(path,f"{prefix}/{rel.as_posix()}",category)
                    else:excluded.append({"path":str(path),"reason":"performance raw output retained at source; report records artifact SHA"})
    add_file(ROOT/"scripts/check_report_evidence.py","tools/check_report_evidence.py","verification_tool")
    add_file(ROOT/"scripts/check_doc_links.py","tools/check_doc_links.py","verification_tool")
    add_file(Path(__file__),"tools/archive-f1.py","verification_tool")
    for index, report in enumerate(options.baseline_report, 1):
        add_tree(report.absolute().parent, f"baseline/{index}", "baseline", required=True)

    if not options.windows_report:blockers.append("No final Windows all report selected")
    if not options.baseline_report:blockers.append("No explicit same-probe baseline selected")
    if options.root_readme is None:blockers.append("No final active archive README selected")
    if not options.review_root and not options.review_file:blockers.append("No explicit independent review evidence selected")
    if not options.visible_root:blockers.append("No explicit visible observation evidence selected")
    if not options.deepseek_response or not options.deepseek_receipt:blockers.append("DeepSeek response and receipt must both be explicitly selected")
    ci_file = options.ci_root / "ci-evidence.json"
    frozen_file = options.ci_root / "frozen-case-manifest.json"
    ci = read_json(ci_file) if ci_file.is_file() else {}
    frozen = read_json(frozen_file) if frozen_file.is_file() else {}
    if not ci_file.is_file(): blockers.append("Final CI evidence summary does not exist")
    if ci.get("status") != "passed" or not ci.get("complete"):
        blockers.append("Final CI evidence is not complete/passed")
    if len(ci.get("artifacts", [])) != options.expected_ci_artifacts or len(ci.get("reports", [])) != options.expected_ci_reports:
        blockers.append("Final CI artifact/report count differs from requested topology")
    if not frozen: blockers.append("Final frozen case manifest is absent")
    expected_head = options.expected_head or frozen.get("head_sha")
    if not expected_head or frozen.get("head_sha") != expected_head:
        blockers.append("Final frozen head does not match the requested final identity")
    elif not ci:
        blockers.append("Final CI identity is unavailable until its summary is collected")
    elif ci.get("head_sha") != expected_head:
        blockers.append("Final CI head does not match the requested final identity")
    topology_check={"status":"not_checked"}
    if options.expected_ci_artifacts!=len(CI_TOPOLOGY) or options.expected_ci_reports!=sum(len(x["profiles"]) for x in CI_TOPOLOGY.values()):
        blockers.append("Requested CI counts differ from the required F1 artifact/profile topology")
    if ci_file.is_file():
        try:
            actual_paths=[item["archive_path"][3:] for item in selected.values() if item["category"]=="accepted_ci" and item["archive_path"].endswith("/report.json")]
            topology_check=validate_ci_topology(options.ci_root,expected_head,actual_paths)
        except (ValueError,OSError,KeyError,TypeError) as error:
            topology_check={"status":"failed","error":str(error)};blockers.append("Final CI topology gate failed: "+str(error))
    for report in options.windows_report:
        if not report.is_file():
            continue
        windows = read_json(report)
        if windows.get("profile") != "all" or windows.get("git_dirty") is not False:
            blockers.append("Final Windows report must be clean profile=all")
        if any(item.get("status") != "pass" for item in windows.get("results", [])):
            blockers.append("Final Windows report contains failed/skipped cases")
        if windows.get("git_head") != expected_head:
            blockers.append("Final Windows report head mismatch")
        for key in ("source_fingerprint", "tests_content_fingerprint"):
            if windows.get(key) != frozen.get(key):
                blockers.append("Final Windows " + key + " mismatch")
    artifact_checks = []
    for item in ci.get("artifacts", []):
        if item.get("name") not in CI_TOPOLOGY:
            blockers.append("Unknown CI artifact identity; ZIP path not read")
            continue
        archive = options.ci_root / (item["name"] + ".zip")
        actual = "sha256:" + digest(archive.read_bytes()) if archive.is_file() else None
        match = actual == item.get("official_digest") == item.get("sha256")
        artifact_checks.append({"zip_source":str(archive.absolute()),"name": item["name"], "official_digest": item.get("official_digest"), "source_zip_digest": actual, "matches": match})
        if not match: blockers.append(f"Source ZIP official digest mismatch: {item['name']}")
        if match:
            checked_members = 0
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    if stat.S_ISLNK(member.external_attr >> 16):raise ValueError("Symlink CI ZIP member refused")
                    if member.is_dir(): continue
                    extracted = safe_relative(options.ci_root / item["name"], member.filename)
                    if not extracted.is_file() or digest(extracted.read_bytes()) != digest(bundle.read(member)):
                        blockers.append("CI extracted bytes differ from original ZIP: " + item["name"] + "/" + member.filename)
                    checked_members += 1
            artifact_checks[-1]["extracted_members_checked"] = checked_members
    if plain_markdown_seen != plain_markdown:
        raise ValueError("Plain Markdown mapping names a source not selected in the archive")
    plan = {"format": "f1_evidence_archive_plan_v1", "created_utc": utc(), "destination": str(target),
            "repository_head_at_plan": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "expected_head": expected_head, "frozen": frozen, "source_roots": roots,
            "required_windows_reports": required_reports,
            "baseline_reports": [f"baseline/{index}/{path.name}" for index, path in enumerate(options.baseline_report, 1)],
            "files": sorted(selected.values(), key=lambda item: item["archive_path"]),
            "historical_rounds": historical_rounds,
            "excluded": excluded, "missing_sources": sorted(set(missing)), "preflight_blockers": blockers,
            "artifact_zip_digest_checks": artifact_checks,
            "historical_zip_digest_checks":[row for record in historical_rounds for row in record.get("zip_digest_checks",[])],
            "performance_checks": performance_checks,
            "expected_ci_reports": options.expected_ci_reports, "expected_ci_artifacts": options.expected_ci_artifacts, "ci_topology_check": topology_check,
            "policy": "Byte copies, exclusive new destination, no source edits; ZIP bytes stay at source, official identities are retained; archival does not establish physics or visible UI completion"}
    plan["link_check"] = link_check(plan)
    if plan["link_check"]["broken_links"]:plan["preflight_blockers"].append("Archive Markdown contains nonportable local links")
    return plan



def report_gates(folder, plan, *, publish_logs=False):
    identity_check=identity.verify_plan_identity(folder,plan)
    topology=validate_ci_topology(folder/"ci",plan.get("ci_expected_head",plan["expected_head"]))
    planned_ci={item["archive_path"][3:] for item in plan["files"] if item["category"]=="accepted_ci" and item["archive_path"].endswith("/report.json")}
    if planned_ci!={row["path"] for row in topology["reports"]}:raise ValueError("Archived CI reports differ from planned CI report paths")
    gate_tool = folder / "tools/check_report_evidence.py"
    required = set(plan["required_windows_reports"])
    reports = [item for item in plan["files"] if PurePosixPath(item["archive_path"]).name == "report.json" and item["category"] not in {"performance", "buffer_performance"}]
    results = []
    found = set()
    for index, item in enumerate(reports):
        relative = item["archive_path"]
        report = safe_relative(folder, relative)
        data = read_json(report)
        release = item["category"] in {"accepted_windows", "accepted_ci"}
        if release: found.add(relative)
        for case in data.get("results", []):
            log = case.get("log")
            if not log:
                if case.get("status") == "pass": raise ValueError(f"Passing archived case has no log: {relative}/{case['name']}")
                continue
            # Require an archive-local copy: never let the checker silently
            # succeed using the original absolute log reference.
            name = str(log).replace("\\", "/").rsplit("/", 1)[-1]
            choices = [report.parent / name, report.parent / "logs" / name]
            local = next((path for path in choices if path.is_file()), None)
            if local is None or digest(local.read_bytes()) != case.get("log_sha256"):
                raise ValueError(f"Missing or modified archive-local log: {relative}/{case['name']}")
        command = [sys.executable, "-B", str(gate_tool), "--report", str(report)]
        gate = subprocess.run(command, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        logname = f"verification/gate-{index:03d}.log"
        if publish_logs: write_new(folder / logname, (gate.stdout + gate.stderr).encode("utf-8"))
        if release:
            if gate.returncode: raise ValueError(f"Release report strict gate failed: {relative}")
            for key in ("source_fingerprint", "tests_content_fingerprint"):
                if data.get(key) != plan["frozen"].get(key): raise ValueError(f"Release {key} mismatch: {relative}")
            if data.get("git_head") != identity.expected_report_head(plan,item["category"]) or data.get("tracked_source_gate") != "pass":
                raise ValueError(f"Release head/tracked-source identity mismatch: {relative}")
            if item["category"] == "accepted_windows":
                if data.get("profile") != "all" or data.get("git_dirty") is not False:
                    raise ValueError(f"Final Windows report must be clean profile=all: {relative}")
                expected_cases = {case for cases in plan["frozen"].get("profiles", {}).values() for case in cases}
            else:
                expected_cases = set(plan["frozen"].get("profiles", {}).get(data.get("profile"), []))
            if {case["name"] for case in data["results"]} != expected_cases:
                raise ValueError(f"Release case set differs from freeze: {relative}")
        results.append({"report": relative, "category": item["category"], "strict_gate_exit_code": gate.returncode,
                        "all_pass": all(case["status"] == "pass" for case in data.get("results", [])),
                        "gate_log": logname if publish_logs else None,
                        "meaning": "release evidence" if release else "retained original history, not release acceptance"})
    if not required <= found: raise ValueError("Requested final Windows report is absent from archive")
    if len([item for item in results if item["category"] == "accepted_ci"]) != plan["expected_ci_reports"]:
        raise ValueError("Archive final CI report count differs from requested topology")
    baseline_results = []
    for index, windows in enumerate(plan["required_windows_reports"]):
        for baseline in plan["baseline_reports"]:
            command = [sys.executable, "-B", str(gate_tool), "--report", str(folder / windows), "--baseline", str(folder / baseline)]
            gate = subprocess.run(command, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            if gate.returncode: raise ValueError("Final Windows same-probe baseline gate failed")
            name = f"verification/baseline-{index:03d}-{len(baseline_results):03d}.log"
            if publish_logs: write_new(folder / name, (gate.stdout + gate.stderr).encode("utf-8"))
            baseline_results.append({"report": windows, "baseline": baseline, "exit_code": gate.returncode})
    return {"reports": results, "baseline_comparisons": baseline_results, "ci_topology_check":topology,
            "identity_mapping_check":identity_check}


def verify_existing(folder):
    if not (folder / "archive-complete.json").is_file():
        raise ValueError("Existing archive has no completion marker; it may be partial and will not be overwritten")
    plan = read_json(folder / "archive-manifest.json")
    completion = read_json(folder / "archive-complete.json")
    if digest((folder / "archive-manifest.json").read_bytes()) != completion["manifest_sha256"]:
        raise ValueError("Archive manifest digest mismatch")
    if digest((folder / "archive-verification.json").read_bytes()) != completion["verification_sha256"]:
        raise ValueError("Archive verification record digest mismatch")
    for item in plan["files"]:
        path = safe_relative(folder, item["archive_path"])
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["size"] or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError(f"Archive byte mismatch: {item['archive_path']}")
    verification=read_json(folder/"archive-verification.json")
    for record in verification.get("generated_verification_files",[]):
        path=safe_relative(folder,record["path"])
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=record["size"] or digest(path.read_bytes())!=record["sha256"]:raise ValueError("Generated verification evidence mismatch")
    if link_check(plan,folder)["broken_links"]:raise ValueError("Archived local links failed recheck")
    verified = report_gates(folder, plan)
    return {"status": "verified", "files": len(plan["files"]), "report_gates": verified}


def execute(plan):
    target = Path(plan["destination"])
    if target.exists() or os.path.lexists(target): raise FileExistsError("Archive destination already exists; use --verify-existing; no overwrite")
    if plan["missing_sources"] or plan["preflight_blockers"]:
        raise ValueError("Archive preflight incomplete; review the plan's missing_sources/preflight_blockers")
    # Exclusive directory creation is the reservation point. A failure leaves
    # an explicitly incomplete new directory, never overwrites or deletes data.
    check_source_zips(plan)
    target.mkdir(parents=False, exist_ok=False)
    write_new(target / "archive-started.json", json_bytes({"started_utc": utc(), "expected_head": plan["expected_head"]}))
    write_new(target / "archive-manifest.json", json_bytes(plan))
    for item in plan["files"]:
        source = Path(item["source"])
        raw = source.read_bytes()
        if len(raw) != item["size"] or digest(raw) != item["sha256"]:
            raise ValueError(f"Evidence source changed after plan: {source}")
        destination = safe_relative(target, item["archive_path"])
        write_new(destination, raw)
        if digest(destination.read_bytes()) != item["sha256"] or digest(source.read_bytes()) != item["sha256"]:
            raise ValueError(f"Byte-copy/source stability check failed: {item['archive_path']}")
    gates = report_gates(target, plan, publish_logs=True)
    links=link_check(plan,target)
    if links["broken_links"]:raise ValueError("Archived local links are not portable")
    write_new(target/"verification/link-check.json",json_bytes(links))
    generated=[{"path":path.relative_to(target).as_posix(),"size":path.stat().st_size,"sha256":digest(path.read_bytes())} for path in sorted((target/"verification").rglob("*")) if path.is_file()]
    verification = {"verified_utc": utc(), "files_sha256_matched": len(plan["files"]), "generated_verification_files":generated, **gates}
    write_new(target / "archive-verification.json", json_bytes(verification))
    write_new(target / "archive-complete.json", json_bytes({"completed_utc": utc(),
              "manifest_sha256": digest((target / "archive-manifest.json").read_bytes()),
              "verification_sha256": digest((target / "archive-verification.json").read_bytes())}))
    return verify_existing(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows-report", type=Path, action="append", default=[])
    parser.add_argument("--ci-root", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--expected-head")
    parser.add_argument("--baseline-report", type=Path, action="append", default=[])
    parser.add_argument("--historical-report", type=Path, action="append", default=[])
    parser.add_argument("--historical-ci-root", type=Path, action="append", default=[])
    parser.add_argument("--historical-windows-root", type=Path, action="append", default=[])
    parser.add_argument("--include-root", type=Path, action="append", default=[])
    parser.add_argument("--include-file", type=Path, action="append", default=[])
    parser.add_argument("--plain-markdown-source", type=Path, action="append", default=[])
    for name in ("performance-root","buffer-performance-root","review-root","review-file","deepseek-response","deepseek-receipt","visible-root"):
        parser.add_argument("--"+name,type=Path,action="append",default=[])
    parser.add_argument("--expected-performance-samples",type=int,default=54)
    parser.add_argument("--expected-buffer-samples",type=int,default=18)
    parser.add_argument("--expected-ci-reports",type=int,default=12)
    parser.add_argument("--expected-ci-artifacts",type=int,default=4)
    parser.add_argument("--review-plan",type=Path)
    parser.add_argument("--review-output",type=Path)
    parser.add_argument("--root-readme", type=Path)
    parser.add_argument("--plan-output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    options = parser.parse_args()
    if options.review_plan:
        result=review_plan(read_json(options.review_plan))
        if options.review_output:write_new(options.review_output,json_bytes(result))
        print(json.dumps(result,ensure_ascii=False))
        return

    if options.destination is None:parser.error("--destination is required except for --review-plan")
    if options.verify_existing:
        print(json.dumps(verify_existing(options.destination.absolute()), ensure_ascii=False, indent=2)); return
    if not options.windows_report or options.ci_root is None:
        parser.error("--windows-report and --ci-root are required to plan or publish")
    plan = build_plan(options)
    if options.plan_output:
        write_new(options.plan_output, json_bytes(plan))
    if options.execute:
        result = execute(plan)
    else:
        result = {"mode": "plan_only", "destination": plan["destination"], "file_count": len(plan["files"]),
                  "source_roots": plan["source_roots"], "excluded_files": len(plan["excluded"]),
                  "missing_sources": plan["missing_sources"], "preflight_blockers": plan["preflight_blockers"],
                  "plan_output": str(options.plan_output) if options.plan_output else None,
                  "notice": "No evidence archive created. --execute never overwrites an existing destination."}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
