#!/usr/bin/env python3
"""coach_run.py — headless orchestrator for Claude Code Coach.

Unattended daily pass: discover sessions, condense → extract → episode-link,
narrate + score NEW work via Haiku (the only model calls, made through
coach_llm), then aggregate / trend / habits into a persistent growing pool and
emit a profile.json snapshot.

The pipeline, per project dir:

    *.jsonl ──condense──▶ condensed JSONL ──┐
            └──events────▶ sessions.jsonl ──┤
                                            ▼
        cwd is a git repo? ──yes──▶ gitdata.py(repo) ──▶ {commit_groups, episodes}
                          └──no───▶ synth session_only episodes (one per session)
                                            │
                  narrate NEW sessions (Haiku, cached by content hash)
                                            ▼
                    episodes.py ──▶ <episode_id>.txt + manifest
                                            │
                  score NEW episodes (Haiku, cached by sha256(input))
                                            ▼
         merge ALL scored episodes (cached + new, all projects) ──▶ episodes.json

Then over the pooled scored episodes + combined sessions/gitdata:
  coach_aggregate.rollup → trend.py → habits.py → (recommend optional) →
  coach_report.py → profile.build_profile → profile.json (+ history.jsonl).

Caches make the run incremental: an unchanged input triggers ZERO model calls.

Robustness: one bad project dir is logged and skipped; the run continues.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import _shared  # noqa: F401  (puts repo scripts/ on sys.path)
import coach_aggregate
import coach_llm
import profile as profile_mod
from _shared import REPO_ROOT, SHARED_SCRIPTS

COACH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../coach
NARRATIVE_PROMPT = os.path.join(REPO_ROOT, "prompts", "session_narrative.md")
SCORING_PROMPT = os.path.join(COACH_DIR, "prompts", "coach_scoring.md")
RECOMMENDER_PROMPT = os.path.join(COACH_DIR, "prompts", "skill_recommender.md")
SKILLS_INDEX = os.path.join(COACH_DIR, "reference", "skills_index.json")
HABIT_CATALOG = os.path.join(COACH_DIR, "reference", "habit_catalog.json")

CONDENSE = os.path.join(SHARED_SCRIPTS, "condense.py")
EVENTS = os.path.join(SHARED_SCRIPTS, "events.py")
GITDATA = os.path.join(SHARED_SCRIPTS, "gitdata.py")
EPISODES = os.path.join(SHARED_SCRIPTS, "episodes.py")
TREND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trend.py")
HABITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habits.py")
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coach_report.py")


def log(msg):
    sys.stderr.write("[coach_run] %s\n" % msg)


def _read_prompt(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _run(argv, **kw):
    """Run a subprocess, returning CompletedProcess; capture text by default."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(argv, **kw)


def _py(script, *args, **kw):
    return _run([sys.executable, script, *args], **kw)


# --- discovery ---

def discover_project_dirs(projects_dir, codex_dir):
    """Project session dirs: each subdir of projects-dir holding *.jsonl, plus
    codex-dir if present. Sorted for determinism."""
    dirs = []
    if projects_dir and os.path.isdir(projects_dir):
        for name in sorted(os.listdir(projects_dir)):
            sub = os.path.join(projects_dir, name)
            if not os.path.isdir(sub):
                continue
            if any(f.endswith(".jsonl") for f in os.listdir(sub)):
                dirs.append(sub)
    if codex_dir and os.path.isdir(codex_dir):
        dirs.append(codex_dir)
    return dirs


# --- git repo detection ---

def _is_git_repo(path):
    if not path or not os.path.isdir(path):
        return False
    res = _run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"])
    return res.returncode == 0 and res.stdout.strip() == "true"


def _repo_from_sessions(condensed_records):
    """First cwd among condensed sessions that is an existing git repo, else None."""
    for rec in condensed_records:
        cwd = rec.get("cwd")
        if cwd and _is_git_repo(cwd):
            return cwd
    return None


def synth_gitdata(sessions):
    """Minimal gitdata-shaped dict: one session_only episode per session, no
    commit groups. Matches the schema episodes.py / trend.py consume."""
    episodes = []
    for i, s in enumerate(sessions, 1):
        sid = s.get("session_id")
        episodes.append({
            "episode_id": i,
            "episode_type": "session_only",
            "confidence": 0.3,
            "session_ids": [sid],
            "commit_group_ids": [],
            "added_lines": 0,
            "deleted_lines": 0,
            "links": [{"session_id": sid, "link_type": None,
                       "link_confidence": 0.3}],
        })
    return {"commit_groups": [], "episodes": episodes}


# --- caches ---

def _content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def narrative_cache_path(cache_dir, session_id, content_hash):
    safe = str(session_id).replace("/", "_")
    return os.path.join(cache_dir, "%s.%s.md" % (safe, content_hash[:16]))


def score_cache_path(cache_dir, input_text):
    return os.path.join(cache_dir, "%s.json" % _content_hash(input_text))


# --- model-backed steps (the only model calls) ---

def narrate_sessions(condensed_records, narratives_dir, narr_cache_dir,
                     model, runner, stats):
    """Write a <session_id>.md narrative for every (non-empty) session into
    narratives_dir. Cache hits skip the model call."""
    os.makedirs(narratives_dir, exist_ok=True)
    os.makedirs(narr_cache_dir, exist_ok=True)
    system = _read_prompt(NARRATIVE_PROMPT)
    for rec in condensed_records:
        sid = rec.get("session_id")
        text = rec.get("condensed_text") or ""
        if not sid or not text.strip():
            continue
        h = _content_hash(text)
        cache_path = narrative_cache_path(narr_cache_dir, sid, h)
        if os.path.exists(cache_path):
            narrative = open(cache_path, encoding="utf-8").read()
        else:
            narrative = coach_llm.call_text(system, text, model=model, runner=runner)
            stats["narrative_calls"] += 1
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(narrative)
        out_path = os.path.join(narratives_dir, "%s.md" % str(sid).replace("/", "_"))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(narrative)


def score_episodes(manifest, score_cache_dir, model, runner, stats):
    """Score each episode listed in the manifest; return scored records.

    Each record: {episode_id, scores{...}, confidence, session_ids, ...the
    rest of the model's JSON (title/what_happened/...)}. Cached by
    sha256(input_text); cache hits skip the model call.
    """
    os.makedirs(score_cache_dir, exist_ok=True)
    system = _read_prompt(SCORING_PROMPT)
    scored = []
    for entry in manifest:
        input_path = entry.get("input_path")
        if not input_path or not os.path.exists(input_path):
            continue
        input_text = open(input_path, encoding="utf-8").read()
        cache_path = score_cache_path(score_cache_dir, input_text)
        if os.path.exists(cache_path):
            record = json.load(open(cache_path))
        else:
            record = coach_llm.call_json(system, input_text, model=model, runner=runner)
            stats["score_calls"] += 1
            record = dict(record)
            record.setdefault("confidence", 0.8)
            json.dump(record, open(cache_path, "w"), ensure_ascii=False)
        record = dict(record)
        record["episode_id"] = entry["episode_id"]
        record.setdefault("confidence", 0.8)
        record["session_ids"] = entry.get("session_ids") or []
        scored.append(record)
    return scored


# --- per-project processing ---

def process_project(project_dir, work_dir, out_dir, model, runner, stats):
    """Run the per-project pipeline; return (scored_episodes, sessions, gitdata).

    Raises on hard failure (caller catches per-project so one bad dir doesn't
    sink the run).
    """
    tag = hashlib.sha1(project_dir.encode("utf-8")).hexdigest()[:10]
    pdir = os.path.join(work_dir, tag)
    os.makedirs(pdir, exist_ok=True)

    # 1) condense → JSONL records
    res = _py(CONDENSE, project_dir)
    if res.returncode != 0:
        raise RuntimeError("condense failed: %s" % (res.stderr or "").strip())
    condensed_records = [json.loads(l) for l in res.stdout.splitlines() if l.strip()]
    # Drop too-short sessions (under the scorable threshold) so we don't burn
    # model calls narrating noise.
    condensed_records = [r for r in condensed_records if not r.get("too_short")]
    if not condensed_records:
        return [], [], synth_gitdata([])

    # 2) events → sessions.jsonl
    res = _py(EVENTS, project_dir)
    if res.returncode != 0:
        raise RuntimeError("events failed: %s" % (res.stderr or "").strip())
    sessions = [json.loads(l) for l in res.stdout.splitlines() if l.strip()]
    # Keep only sessions we condensed (i.e. long enough to score).
    keep_ids = {r["session_id"] for r in condensed_records}
    sessions = [s for s in sessions if s.get("session_id") in keep_ids]
    if not sessions:
        return [], [], synth_gitdata([])
    sessions_path = os.path.join(pdir, "sessions.jsonl")
    with open(sessions_path, "w", encoding="utf-8") as f:
        for s in sessions:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # 3) gitdata (real repo) or synthesized session_only episodes
    repo = _repo_from_sessions(condensed_records)
    gitdata_path = os.path.join(pdir, "gitdata.json")
    if repo:
        res = _py(GITDATA, "--repo", repo, "--sessions", sessions_path,
                  "--out", gitdata_path)
        if res.returncode != 0 or not os.path.exists(gitdata_path):
            log("gitdata failed for %s (repo=%s); using synth episodes: %s"
                % (project_dir, repo, (res.stderr or "").strip()))
            gitdata = synth_gitdata(sessions)
            json.dump(gitdata, open(gitdata_path, "w"), ensure_ascii=False)
        else:
            gitdata = json.load(open(gitdata_path))
    else:
        gitdata = synth_gitdata(sessions)
        json.dump(gitdata, open(gitdata_path, "w"), ensure_ascii=False)

    # 4) narrate NEW sessions (cached)
    narratives_dir = os.path.join(pdir, "narratives")
    narr_cache = os.path.join(out_dir, "cache", "narratives")
    narrate_sessions(condensed_records, narratives_dir, narr_cache,
                     model, runner, stats)

    # 5) episodes.py → per-episode .txt + manifest
    inputs_dir = os.path.join(pdir, "inputs")
    res = _py(EPISODES, "--sessions", sessions_path, "--episodes", gitdata_path,
              "--narratives", narratives_dir, "--out-dir", inputs_dir)
    if res.returncode != 0:
        raise RuntimeError("episodes failed: %s" % (res.stderr or "").strip())
    manifest = json.load(open(os.path.join(inputs_dir, "episodes_manifest.json")))

    # 6) score NEW episodes (cached)
    score_cache = os.path.join(out_dir, "cache", "scores")
    scored = score_episodes(manifest, score_cache, model, runner, stats)
    return scored, sessions, gitdata


# --- pooling + reindexing across projects ---

def reindex(all_scored, all_sessions, all_gitdata_episodes):
    """Give episodes globally-unique ids so trend.py can join episode↔session
    across projects. Returns (scored_pool, gitdata_episodes)."""
    scored_out = []
    gitdata_out = []
    eid = 0
    # all_scored and all_gitdata_episodes are parallel per-project lists.
    for scored, gd_eps in zip(all_scored, all_gitdata_episodes):
        # Map this project's old episode_id -> session_ids (from gitdata).
        sids_by_old = {e["episode_id"]: e.get("session_ids") or [] for e in gd_eps}
        old_to_new = {}
        for rec in scored:
            eid += 1
            old = rec["episode_id"]
            old_to_new[old] = eid
            new_rec = dict(rec)
            new_rec["episode_id"] = eid
            if not new_rec.get("session_ids"):
                new_rec["session_ids"] = sids_by_old.get(old, [])
            scored_out.append(new_rec)
        for e in gd_eps:
            old = e["episode_id"]
            if old not in old_to_new:
                continue  # episode produced no score (skip in trend dating)
            ne = dict(e)
            ne["episode_id"] = old_to_new[old]
            gitdata_out.append(ne)
    return scored_out, gitdata_out


# --- finalize: aggregate / trend / habits / report / profile ---

def finalize(scored_pool, sessions_path, gitdata_path, out_dir, n_sessions,
             updated_at, model, runner, stats, do_recommend):
    episodes_path = os.path.join(out_dir, "episodes.json")
    json.dump({"episodes": scored_pool}, open(episodes_path, "w"),
              indent=2, ensure_ascii=False)

    # aggregate (imported, not subprocess)
    per_axis, overall = coach_aggregate.rollup(scored_pool)
    aggregate = {
        "episodes_scored": len(scored_pool),
        "axes": per_axis,
        "overall_score": overall,
        "band": coach_aggregate.band_for_score(overall) if overall is not None else None,
    }
    aggregate_path = os.path.join(out_dir, "aggregate.json")
    json.dump(aggregate, open(aggregate_path, "w"), indent=2, ensure_ascii=False)

    # trend (subprocess)
    trend_path = os.path.join(out_dir, "trend.json")
    res = _py(TREND, "--episodes", episodes_path, "--sessions", sessions_path,
              "--gitdata", gitdata_path, "--out", trend_path)
    if res.returncode != 0:
        log("trend failed: %s" % (res.stderr or "").strip())
        json.dump({"weeks": [], "deltas": None, "note": "trend unavailable"},
                  open(trend_path, "w"))
    trend = json.load(open(trend_path))

    # habits (subprocess)
    habits_path = os.path.join(out_dir, "habits.json")
    res = _py(HABITS, "--sessions", sessions_path, "--catalog", HABIT_CATALOG,
              "--out", habits_path)
    if res.returncode != 0:
        log("habits failed: %s" % (res.stderr or "").strip())
        json.dump({"habits": []}, open(habits_path, "w"))
    habits = json.load(open(habits_path))

    # recommendations (OPTIONAL — model-backed; best effort)
    recommendations = None
    rec_path = os.path.join(out_dir, "recommendations.json")
    if do_recommend:
        try:
            recommendations = run_recommend(aggregate_path, habits_path,
                                            sessions_path, rec_path, model,
                                            runner, stats)
        except Exception as ex:
            log("recommend skipped: %s: %s" % (type(ex).__name__, ex))
            recommendations = None

    # report (best effort)
    try:
        report_recs = rec_path if recommendations is not None else None
        if report_recs is None:
            json.dump({"recommend": [], "reconsider": []}, open(rec_path, "w"))
            report_recs = rec_path
        res = _py(REPORT, "--episodes", episodes_path, "--trend", trend_path,
                  "--habits", habits_path, "--recommendations", report_recs,
                  "--index", SKILLS_INDEX,
                  "--out", os.path.join(out_dir, "last_report.txt"))
        if res.returncode != 0:
            log("report failed: %s" % (res.stderr or "").strip())
    except Exception as ex:
        log("report skipped: %s: %s" % (type(ex).__name__, ex))

    # profile
    prof = profile_mod.build_profile(aggregate, trend, habits, recommendations,
                                     n_sessions, updated_at)
    profile_path = os.path.join(out_dir, "profile.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=2, ensure_ascii=False, sort_keys=True)

    # history append
    with open(os.path.join(out_dir, "history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"run_at": updated_at, "n_sessions": n_sessions,
                            "overall": prof["overall"], "band": prof["band"]},
                           ensure_ascii=False) + "\n")
    return prof, profile_path


def run_recommend(aggregate_path, habits_path, sessions_path, rec_path,
                  model, runner, stats):
    """prep → Haiku(skill_recommender.md) → finalize. Returns the dict written
    to rec_path."""
    recommend_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recommend.py")
    prep_path = rec_path + ".prep.json"
    res = _py(recommend_py, "prep", "--aggregate", aggregate_path,
              "--habits", habits_path, "--sessions", sessions_path,
              "--index", SKILLS_INDEX, "--out", prep_path)
    if res.returncode != 0:
        raise RuntimeError("recommend prep failed: %s" % (res.stderr or "").strip())
    rec_input = open(prep_path, encoding="utf-8").read()
    system = _read_prompt(RECOMMENDER_PROMPT)
    raw = coach_llm.call_json(system, rec_input, model=model, runner=runner)
    stats["recommend_calls"] += 1
    raw_path = rec_path + ".raw.json"
    json.dump(raw, open(raw_path, "w"), ensure_ascii=False)
    res = _py(recommend_py, "finalize", "--raw", raw_path, "--out", rec_path)
    if res.returncode != 0:
        raise RuntimeError("recommend finalize failed: %s" % (res.stderr or "").strip())
    return json.load(open(rec_path))


# --- main pass ---

def run_once(projects_dir, codex_dir, out_dir, model, work_dir, runner=None,
             updated_at=None, do_recommend=False):
    os.makedirs(out_dir, exist_ok=True)
    updated_at = updated_at or datetime.datetime.now().isoformat()
    stats = {"narrative_calls": 0, "score_calls": 0, "recommend_calls": 0}

    project_dirs = discover_project_dirs(projects_dir, codex_dir)
    log("discovered %d project dir(s)" % len(project_dirs))

    all_scored, all_sessions, all_gd_eps = [], [], []
    for pdir in project_dirs:
        try:
            scored, sessions, gitdata = process_project(
                pdir, work_dir, out_dir, model, runner, stats)
        except Exception as ex:
            log("project failed (skipped): %s: %s: %s"
                % (pdir, type(ex).__name__, ex))
            continue
        if not scored:
            continue
        all_scored.append(scored)
        all_sessions.extend(sessions)
        all_gd_eps.append(gitdata.get("episodes") or [])

    scored_pool, gitdata_episodes = reindex(all_scored, all_sessions, all_gd_eps)

    # combined sessions.jsonl + gitdata.json for trend/habits
    sessions_path = os.path.join(work_dir, "combined_sessions.jsonl")
    with open(sessions_path, "w", encoding="utf-8") as f:
        for s in all_sessions:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    gitdata_path = os.path.join(work_dir, "combined_gitdata.json")
    json.dump({"commit_groups": [], "episodes": gitdata_episodes},
              open(gitdata_path, "w"), ensure_ascii=False)

    n_sessions = len({s.get("session_id") for s in all_sessions})
    prof, profile_path = finalize(
        scored_pool, sessions_path, gitdata_path, out_dir, n_sessions,
        updated_at, model, runner, stats, do_recommend)

    print("Coach run complete: %d session(s), %d episode(s), overall=%s, band=%s"
          % (n_sessions, len(scored_pool), prof["overall"], prof["band"]))
    print("Profile written to %s" % profile_path)
    print("Model calls: %d narrative, %d score, %d recommend"
          % (stats["narrative_calls"], stats["score_calls"],
             stats["recommend_calls"]))
    return prof, profile_path, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--projects-dir",
                    default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--codex-dir",
                    default=os.path.expanduser("~/.codex/sessions"))
    ap.add_argument("--out-dir", default=os.path.expanduser("~/.claude/coach"))
    ap.add_argument("--model", default=coach_llm.DEFAULT_MODEL)
    ap.add_argument("--once", action="store_true",
                    help="run a single pass (the only supported mode today)")
    ap.add_argument("--work-dir", default=None,
                    help="scratch dir for intermediate artifacts (default: a tmp dir)")
    ap.add_argument("--recommend", action="store_true",
                    help="also run the (model-backed) skill recommender")
    a = ap.parse_args()

    cleanup = False
    work_dir = a.work_dir
    if not work_dir:
        work_dir = tempfile.mkdtemp(prefix="coach_run_")
        cleanup = True
    else:
        os.makedirs(work_dir, exist_ok=True)

    codex_dir = a.codex_dir if a.codex_dir and os.path.isdir(a.codex_dir) else None
    try:
        run_once(a.projects_dir, codex_dir, a.out_dir, a.model, work_dir,
                 do_recommend=a.recommend)
    finally:
        if cleanup:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
