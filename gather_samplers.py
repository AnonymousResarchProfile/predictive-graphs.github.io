#!/usr/bin/env python3
"""
Scan a project tree for videos at:
  ./<scene>/<task>/<model>/<run id>/<iter>/sim.mp4

Group by (task, model) and emit HTML (stdout or file) that inserts into index.html.
Usage:
  python scripts/generate_video_grid.py [base_dir] [--out FILE]
Example:
  python scripts/generate_video_grid.py . --out video_grid.html
"""
from pathlib import Path
import re
import sys
import argparse
import json
from collections import defaultdict

VIDEO_NAME = "sim.mp4"
ITER_RE = re.compile(r"(\d+)")

def find_videos(base: Path):
    videos_dir = base / 'static' / 'videos' / 'highlight-videos'
    if not videos_dir.exists():
        print(f"Videos directory not found at {videos_dir}")
        return []
    print(f"Searching for videos in {videos_dir}")
    res = []
    for p in videos_dir.rglob(VIDEO_NAME):
        try:
            rel = p.relative_to(videos_dir)
        except Exception:
            rel = p
        # Construct relative path for web
        web_path = "static/videos/highlight-videos/" + str(rel)
        parts = rel.parts
        # Structure: blocks_gre_yel_bla/Make-a-task/gpt-5-2025-08-07/run_id/sim.mp4
        if len(parts) < 6:
            continue
        
        # Find the model folder (the one containing gpt-5)
        model_idx = next((i for i, part in enumerate(parts) if 'gpt-5' in part), None)
        if model_idx is None:
            continue
            
        scene = parts[1]  # e.g., blocks_gre_yel_bla
        task = parts[model_idx - 1]  # The task is right before the model
        model = parts[model_idx]  # e.g., gpt-5-2025-08-07
        run_id = parts[model_idx + 1]  # The run ID follows the model
        
        m = ITER_RE.search(run_id)  # Look for iteration number in the run_id
        iter_num = int(m.group(1)) if m else None
        
        res.append({
            "path": web_path,
            "abs_path": str(p),
            "scene": scene,
            "task": task,
            "model": model,
            "run_id": run_id,
            "iter_name": run_id,  # Using run_id as iter_name since that's what contains our iteration
            "iter_num": iter_num if iter_num is not None else 0
        })
    return res

def group_by_task_model(videos):
    grouped = defaultdict(list)
    for v in videos:
        key = (v["task"], v["model"])
        grouped[key].append(v)
    # sort each list by iter_num ascending, then by path
    for k in grouped:
        videos_for_key = grouped[k]
        videos_for_key.sort(key=lambda x: (x["iter_num"], x["path"]))
        # If there are exactly 6 videos, only keep the first 5
        if len(videos_for_key) == 6:
            grouped[k] = videos_for_key[:5]
    return grouped

def render_html(grouped):
    tasks = sorted(set(task for task, _ in grouped.keys()))
    models_by_task = {t: sorted(set(m for tt, m in grouped.keys() if tt == t)) for t in tasks}

    out = []
    # Add HTML head with required CSS
    out.extend([
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        '  <link rel="stylesheet" href="static/css/bulma.min.css">',
        '</head>',
        '<body>',
    ])

    # --- Controls ---
    out.append('<div class="section">')
    out.append('  <div class="container is-max-desktop">')

    # Task selector
    out.append('    <div class="field">')
    out.append('      <label class="label">Task</label>')
    out.append('      <div class="control">')
    out.append('        <div class="select">')
    out.append('          <select id="task-select" onchange="updateTask()">')
    for t in tasks:
        out.append(f'            <option value="{t}">{t}</option>')
    out.append('          </select>')
    out.append('        </div>')
    out.append('      </div>')
    out.append('    </div>')

    # Model selector
    out.append('    <div class="field">')
    out.append('      <label class="label">Model</label>')
    out.append('      <div class="control">')
    out.append('        <div class="select">')
    out.append('          <select id="model-select" onchange="updateModel()">')
    # initially populate with first task's models
    for m in models_by_task[tasks[0]]:
        out.append(f'            <option value="{m}">{m}</option>')
    out.append('          </select>')
    out.append('        </div>')
    out.append('      </div>')
    out.append('    </div>')

    out.append('  </div>')
    out.append('</div>')

    # --- Video sections ---
    for (task, model), vids in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        section_id = f"{task}-{model}"
        out.append(f'<section class="section video-grid" id="{section_id}" style="display:none;">')
        out.append('  <div class="container is-max-desktop">')
        out.append(f'    <h2 class="title is-3">{task} — {model}</h2>')
        out.append('    <div class="columns is-multiline">')
        for idx, v in enumerate(vids):
            caption = "Feedback iteration "+str(idx)  # Use the enumerated index (0-4) instead of iter_num
            out.append('      <div class="column is-one-third-desktop is-half-mobile">')
            out.append('        <div class="card">')
            out.append('          <div class="card-image">')
            out.append(
                f'            <video autoplay loop muted playsinline preload="metadata" style="width:100%; height:auto;">'
            )
            out.append(f'              <source src="{v["path"]}" type="video/mp4">')
            out.append('            </video>')
            out.append('          </div>')
            out.append('          <div class="card-content">')
            out.append(f'            <p class="subtitle is-6">{caption}</p>')
            out.append('          </div>')
            out.append('        </div>')
            out.append('      </div>')

        out.append('    </div>')
        out.append('  </div>')
        out.append('</section>')
        out.append('')

    # --- JavaScript for toggling ---
    out.append('<script>')
    out.append('const modelsByTask = ' + json.dumps(models_by_task) + ';')
    out.append('function updateTask() {')
    out.append('  const task = document.getElementById("task-select").value;')
    out.append('  const modelSel = document.getElementById("model-select");')
    out.append('  modelSel.innerHTML = "";')
    out.append('  for (const m of modelsByTask[task]) {')
    out.append('    const opt = document.createElement("option");')
    out.append('    opt.value = m; opt.textContent = m;')
    out.append('    modelSel.appendChild(opt);')
    out.append('  }')
    out.append('  updateModel();')
    out.append('}')
    out.append('function updateModel() {')
    out.append('  const task = document.getElementById("task-select").value;')
    out.append('  const model = document.getElementById("model-select").value;')
    out.append('  // hide all sections')
    out.append('  document.querySelectorAll(".video-grid").forEach(s => s.style.display = "none");')
    out.append('  // show the selected one')
    out.append('  const section = document.getElementById(task + "-" + model);')
    out.append('  if (section) section.style.display = "block";')
    out.append('}')
    out.append('// initialize')
    out.append('updateTask();')
    out.append('</script>')
    
    # Add closing tags
    out.extend([
        '</body>',
        '</html>'
    ])

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_dir", nargs="?", default=".", help="project root to scan (default: .)")
    ap.add_argument("--out", "-o", help="write HTML to this file (default: stdout)")
    args = ap.parse_args()
    base = Path(args.base_dir).resolve()
    videos = find_videos(base)
    if not videos:
        print("<!-- No videos found -->")
        return
    grouped = group_by_task_model(videos)
    html = render_html(grouped)
    if args.out:
        outp = Path(args.out)
        with open(outp, 'w', encoding='utf-8') as f:
            f.write(html)
            f.flush()
        print(f"Wrote HTML to {outp}")
    else:
        print(html)

if __name__ == "__main__":
    main()