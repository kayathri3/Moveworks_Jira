"""
Generates a single continuous-flow HTML page from the dynamic solver results.
All sections flow vertically with connecting arrows — no page breaks.
"""
import os, sys, time

# Reuse the solver engine
from dynamic_interactive_solver import (
    build_config_from_dict, generate_all_goals, solve_bfs,
    analyze_solution, format_action, PRESET_UNCERTAIN,
)


def generate_continuous_html(analyses, config, output_path):
    engine = config["engine"]
    tracks = config["tracks"]
    eng_len = config["stock_length"][engine]

    # ── Helpers ──
    def cap_str(c):
        return "∞" if c == float("inf") else f"{c}m"

    def junction_rows():
        seen = set()
        rows = ""
        for (f, t), c in sorted(config["junctions"].items()):
            key = tuple(sorted([f, t]))
            if key in seen:
                continue
            seen.add(key)
            cs = cap_str(c)
            e_ok  = "✓" if eng_len <= c else "✗"
            e_1w  = "✓" if eng_len + 8 <= c else "✗"
            e_2w  = "✓" if eng_len + 16 <= c else "✗"
            w_ok  = "✓" if 8 <= c else "✗"
            rows += f"<tr><td>{f} ↔ {t}</td><td>{cs}</td><td>{e_ok}</td><td>{e_1w}</td><td>{e_2w}</td><td>{w_ok}</td></tr>\n"
        return rows

    def stock_rows():
        rows = ""
        for name, length in config["stock_length"].items():
            role = "Engine" if name == engine else "Wagon"
            init_t = next((t for t, items in config["initial"].items() if name in items), "—")
            rows += f"<tr><td>{name}</td><td>{role}</td><td>{length}m</td><td>Track {init_t}</td></tr>\n"
        return rows

    def deadlock_rows():
        rows = ""
        for t in tracks:
            exits = []
            can_escape = False
            for (f2, t2), c in config["junctions"].items():
                if f2 != t:
                    continue
                cs = cap_str(c)
                fit = eng_len <= c
                if fit:
                    can_escape = True
                exits.append(f"{t2}({cs} {'✓' if fit else '✗'})")
            status_cls = "safe" if can_escape else "risk"
            status_txt = "SAFE" if can_escape else "⚠ RISK"
            rows += f'<tr><td>Track {t}</td><td>{", ".join(exits)}</td><td class="{status_cls}">{status_txt}</td></tr>\n'
        return rows

    # ── Build per-solution sections ──
    solution_sections = ""
    for idx, analysis in enumerate(analyses):
        if analysis is None:
            continue
        goal = analysis["goal"]
        goal_str = " | ".join(f"{t}={goal.get(t, [])}" for t in tracks)
        n_actions = analysis["total_actions"]
        n_rev = analysis["reversal_count"]

        if n_actions == 0:
            solution_sections += f"""
            <div class="section" id="sol{idx+1}">
              <div class="section-hdr green">SOLUTION {idx+1}: {goal_str}</div>
              <div class="info-box green">Already at goal — 0 actions needed.</div>
            </div>
            <div class="connector"><div class="arrow-down"></div></div>"""
            continue

        # Flowchart steps
        flow_html = ""
        for s in analysis["steps"]:
            if s["step"] == 0:
                continue
            act = s["action_type"]
            colors = {"COUPLE": ("#e3f2fd", "#1565c0"), "DECOUPLE": ("#e3f2fd", "#1565c0"),
                      "MOVE": ("#c8e6c9", "#2e7d32"), "FLY_SHUNT": ("#fff3e0", "#e65100")}
            bg, bdr = colors.get(act, ("#f5f5f5", "#999"))
            track_state = " | ".join(f"{t}={','.join(s['state'].get(t,[])) or '—'}" for t in tracks)
            coupled = ",".join(s["coupled"]) or "—"
            flow_html += f"""
            <div class="step-box" style="background:{bg};border-color:{bdr};">
              <div class="step-num">{s['step']}</div>
              <div class="step-body">
                <div class="step-action"><b>{act}</b>: {s['detail']}</div>
                <div class="step-state">State: {track_state} | Coupled: {coupled} | Engine: {s['engine_on']}</div>
              </div>
            </div>
            <div class="step-arrow"></div>"""

        # Capacity checks
        cap_html = ""
        for c in analysis["capacity_checks"]:
            cs = cap_str(c["capacity"])
            ok = c["pass"]
            cap_html += f'<tr><td>{c["route"]}</td><td>{cs}</td><td>{c["length"]}m</td><td class="{"safe" if ok else "risk"}">{"✓" if ok else "✗"}</td></tr>\n'

        # Reversal detail
        rev_html = ""
        rn = 0
        for r in analysis["reversals_detail"]:
            if r["reversal"]:
                rn += 1
            rev_html += f'<tr><td>{r["move"]}</td><td>{r["prev"] or "—"}</td><td class="{"risk" if r["reversal"] else ""}">{"YES (#" + str(rn) + ")" if r["reversal"] else "no"}</td></tr>\n'

        # Validation
        val_html = ""
        final_state = analysis["steps"][-1]["state"]
        all_pass = True
        for t, exp in goal.items():
            actual = final_state.get(t, [])
            ok = sorted(actual) == sorted(exp)
            if not ok:
                all_pass = False
            val_html += f'<tr><td>Track {t}</td><td>{exp}</td><td>{actual}</td><td class="{"safe" if ok else "risk"}">{"✓ PASS" if ok else "✗ FAIL"}</td></tr>\n'

        solution_sections += f"""
        <div class="section" id="sol{idx+1}">
          <div class="section-hdr green">SOLUTION {idx+1}: {goal_str} — {n_actions} actions, {n_rev} reversals</div>

          <div class="flow-col">
            <div class="flow-title">EXECUTION FLOWCHART</div>
            <div class="start-end">START — Initial: {" | ".join(f"{t}={config['initial'].get(t,[])}" for t in tracks)}</div>
            <div class="step-arrow"></div>
            {flow_html}
            <div class="start-end" style="background:#a5d6a7;">END ✓ — Goal Reached</div>
          </div>

          <div class="detail-grid">
            <div>
              <div class="sub-title">⑤ Capacity Checks</div>
              <table><tr><th>Route</th><th>Capacity</th><th>Length</th><th>OK?</th></tr>{cap_html}</table>
            </div>
            <div>
              <div class="sub-title">⑨ Reversal Analysis</div>
              <table><tr><th>Direction</th><th>Previous</th><th>Reversed?</th></tr>{rev_html}</table>
            </div>
          </div>

          <div class="sub-title">⑩ Final Validation</div>
          <table><tr><th>Track</th><th>Expected</th><th>Actual</th><th>Status</th></tr>{val_html}</table>
          <div class="info-box {"green" if all_pass else "red"}">{"ALL CHECKS PASSED ✓" if all_pass else "VALIDATION FAILED ✗"}</div>
        </div>
        <div class="connector"><div class="arrow-down"></div></div>"""

    # ── Pre-build summary table (avoid nested f-strings) ──
    summary_rows = ""
    for i, a in enumerate(analyses):
        if a:
            goal_cols = " | ".join(str(t) + "=" + str(a["goal"].get(t, [])) for t in tracks)
            summary_rows += (
                f'<tr><td>{i+1}</td><td>{goal_cols}</td>'
                f'<td>{a["total_actions"]}</td><td>{a["reversal_count"]}</td>'
                f'<td class="safe">✓ SOLVED</td></tr>\n'
            )
        else:
            summary_rows += (
                f'<tr><td>{i+1}</td><td>—</td><td>—</td><td>—</td>'
                f'<td class="risk">✗ UNSOLVABLE</td></tr>\n'
            )

    siding_limit_rows = ""
    for t, l in config.get("siding_limits", {}).items():
        siding_limit_rows += f"<tr><td>Track {t}</td><td>Max {l} wagon(s)</td></tr>"
    if not siding_limit_rows:
        siding_limit_rows = '<tr><td colspan="2">None</td></tr>'

    solved_count = len([a for a in analyses if a])
    best_actions = min((a["total_actions"] for a in analyses if a and a["total_actions"] > 0), default=0)
    worst_actions = max((a["total_actions"] for a in analyses if a), default=0)

    # ── Assemble full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Continuous Flow — Dynamic Shunting Puzzle</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#e8eaf6 0%,#f5f5f5 100%);
  padding:20px;color:#222}}

.container{{max-width:1100px;margin:0 auto;}}

/* Title */
.main-title{{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;text-align:center;
  padding:20px;border-radius:8px;font-size:22px;font-weight:bold;margin-bottom:0;}}

/* Connectors */
.connector{{display:flex;justify-content:center;padding:5px 0;}}
.arrow-down{{width:3px;height:35px;background:#1a237e;position:relative;}}
.arrow-down::after{{content:'▼';position:absolute;bottom:-12px;left:-6px;font-size:14px;color:#1a237e;}}

/* Sections */
.section{{background:#fff;border:2px solid #ccc;border-radius:8px;padding:20px;margin:0 auto;
  box-shadow:0 2px 8px rgba(0,0,0,0.08);}}
.section-hdr{{font-weight:bold;font-size:16px;padding:10px 15px;border-radius:5px;margin:-20px -20px 15px;
  border-bottom:2px solid #ccc;}}
.section-hdr.blue{{background:#e3f2fd;color:#0d47a1;border-color:#90caf9;}}
.section-hdr.red{{background:#ffebee;color:#b71c1c;border-color:#ef9a9a;}}
.section-hdr.green{{background:#e8f5e9;color:#1b5e20;border-color:#a5d6a7;}}
.section-hdr.orange{{background:#fff3e0;color:#e65100;border-color:#ffcc80;}}

/* Tables */
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}}
th{{background:#e8eaf6;padding:6px 8px;border:1px solid #bbb;text-align:left}}
td{{padding:6px 8px;border:1px solid #ddd}}
.safe{{color:#2e7d32;font-weight:bold}}
.risk{{color:#c62828;font-weight:bold}}

/* Flow */
.flow-text{{font-family:Consolas,monospace;font-size:12px;background:#fafafa;border:1px solid #ddd;
  padding:12px;border-radius:4px;white-space:pre;line-height:1.4;overflow-x:auto}}

/* Step boxes */
.flow-col{{margin:10px 0;padding:10px;background:#fafafa;border:1px solid #e0e0e0;border-radius:6px}}
.flow-title{{font-weight:bold;color:#1a237e;margin-bottom:8px;font-size:14px}}
.start-end{{background:#ef9a9a;border:2px solid #c62828;border-radius:25px;padding:8px 20px;
  text-align:center;font-weight:bold;font-size:13px;max-width:600px;margin:0 auto}}
.step-box{{display:flex;align-items:stretch;border:2px solid #999;border-radius:6px;overflow:hidden;
  margin:0 auto;max-width:700px}}
.step-num{{background:#1a237e;color:#fff;font-weight:bold;font-size:15px;
  width:36px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.step-body{{padding:6px 12px;flex:1}}
.step-action{{font-size:13px}}
.step-state{{font-size:11px;color:#555;margin-top:2px}}
.step-arrow{{width:3px;height:14px;background:#666;margin:0 auto}}

/* Info boxes */
.info-box{{padding:8px 15px;border-radius:4px;text-align:center;font-weight:bold;margin:8px 0;font-size:13px}}
.info-box.green{{background:#c8e6c9;color:#1b5e20;border:1px solid #a5d6a7}}
.info-box.red{{background:#ffcdd2;color:#b71c1c;border:1px solid #ef9a9a}}

/* Grids */
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin:10px 0}}
.sub-title{{font-weight:bold;color:#1a237e;font-size:14px;margin:10px 0 5px}}

/* Module boxes */
.mod-box{{border:2px solid #f9a825;background:#fffde7;border-radius:6px;padding:12px;margin:8px 0}}
.mod-hdr{{font-weight:bold;font-size:14px;color:#e65100;margin-bottom:6px}}

ul{{padding-left:18px;margin:4px 0}} li{{font-size:13px;margin:2px 0}}
</style>
</head>
<body>
<div class="container">

<!-- ═══ TITLE ═══ -->
<div class="main-title">
  DYNAMIC SHUNTING PUZZLE SOLVER — CONTINUOUS FLOW<br>
  <span style="font-size:14px;font-weight:normal">
    Tracks: {', '.join(tracks)} | Engine: {engine} ({eng_len}m) |
    Wagons: {', '.join(f'{n}({l}m)' for n,l in config['stock_length'].items() if n != engine)} |
    Solutions: {len([a for a in analyses if a])}
  </span>
</div>
<div class="connector"><div class="arrow-down"></div></div>

<!-- ═══ SECTION 1: INITIALIZATION ═══ -->
<div class="section">
  <div class="section-hdr blue">① INITIALIZATION — System Configuration</div>
  <div class="two-col">
    <div>
      <div class="sub-title">Rolling Stock</div>
      <table><tr><th>Name</th><th>Role</th><th>Length</th><th>Start</th></tr>{stock_rows()}</table>
      <div class="sub-title">Junction Capacity Matrix</div>
      <table><tr><th>Route</th><th>Capacity</th><th>{engine} alone</th><th>+1 wagon</th><th>+2 wagons</th><th>Wagon alone</th></tr>
        {junction_rows()}</table>
    </div>
    <div>
      <div class="sub-title">④ Deadlock Analysis Per Track</div>
      <table><tr><th>Track</th><th>Available Exits</th><th>Status</th></tr>{deadlock_rows()}</table>
      <div class="sub-title">Siding Limits</div>
      <table><tr><th>Track</th><th>Limit</th></tr>
        {siding_limit_rows}
      </table>
    </div>
  </div>
</div>
<div class="connector"><div class="arrow-down"></div></div>

<!-- ═══ SECTION 2: MASTER FLOWCHART ═══ -->
<div class="section">
  <div class="section-hdr blue">MASTER FLOWCHART — Module Execution Loop</div>
  <div class="two-col" style="grid-template-columns:55% 45%">
    <div class="flow-text">
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                ┌────────▼────────┐
           ①   │ INITIALIZATION  │
                └────────┬────────┘
                         │
            ┌────────────▼────────────┐
       ②   │   TERMINATION CHECK     │
            └────────────┬────────────┘
                         │
                ◇ Goal satisfied? ◇
               ╱                   ╲
         YES  ╱                     ╲  NO
             ╱                       ╲
  ┌──────────▼─────────┐    ┌────────▼──────────────┐
⑩│ FINAL VALIDATION   │  ③│ SELECT NEXT LEGAL     │
  └──────────┬─────────┘    │ ACTION                │
             │              └────────┬──────────────┘
    ◇ All OK? ◇                     │
   ╱           ╲           ┌────────▼────────┐
 YES           NO        ④│ DEADLOCK CHECK  │
  │             │          └────────┬────────┘
  ▼             ▼                   │
┌─────┐   Back to ③      ◇ Deadlocked? ◇
│ END │                  ╱               ╲
└─────┘                YES               NO
                         │                │
              ┌──────────▼───┐   ┌────────▼────────┐
              │REJECT → ③   │ ⑤│VALIDATE CAPACITY│
              └──────────────┘   └────────┬────────┘
                                          │
                                 ◇ Valid? ◇
                                ╱          ╲
                              YES          NO
                               │      ┌────▼────────┐
                      ┌────────▼──┐   │REJECT → ③  │
                 ⑥   │COUPLE /   │   └─────────────┘
                      │DECOUPLE   │
                      └────────┬──┘
                      ┌────────▼──────┐
                 ⑦   │ MOVE ENGINE / │
                      │ FLY_SHUNT    │
                      └────────┬──────┘
                      ┌────────▼──────┐
                 ⑧   │ STATE UPDATE  │
                      └────────┬──────┘
                      ┌────────▼──────────┐
                 ⑨   │REVERSAL COUNT UPD │
                      └────────┬──────────┘
                               │
                               └──→ back to ②
    </div>
    <div>
      <div class="mod-box">
        <div class="mod-hdr">③ SELECT NEXT LEGAL ACTION</div>
        <div class="flow-text" style="font-size:11px">
 ◇ Wagon on engine's track? ◇
╱                              ╲
YES                            NO
 │                              │
 ▼                              ▼
COUPLE it              ◇ Coupled wagon
                       │ needs to move? ◇
                      ╱                  ╲
                    YES                  NO
                     │                    │
                     ▼                    ▼
              MOVE or FLY_SHUNT    MOVE engine
              (depends on junction  alone to reach
               capacity)           next wagon
        </div>
      </div>
      <div class="mod-box">
        <div class="mod-hdr">⑤ VALIDATE CAPACITY — Decision Chain</div>
        <div class="flow-text" style="font-size:11px">
 ◇ consist ≤ junction cap? ◇
╱                            ╲
YES                          NO → REJECT
 │
 ◇ coupled ≤ max ({config['max_coupled']})? ◇
╱                              ╲
YES                            NO → REJECT
 │
 ◇ siding limits OK? ◇
╱                      ╲
YES                    NO → REJECT
 │
 ▼
PASS → ⑥ COUPLE/DECOUPLE
        </div>
      </div>
      <div class="mod-box">
        <div class="mod-hdr">⑩ FINAL VALIDATION — Decision Chain</div>
        <div class="flow-text" style="font-size:11px">
 ◇ Every item at goal? ◇
╱                        ╲
YES                      NO → FAIL
 │
 ◇ Nothing coupled? ◇
╱                     ╲
YES                   NO → FAIL
 │
 ◇ No constraint violated? ◇
╱                             ╲
YES                           NO → FAIL
 │
 ▼
 END ✓
        </div>
      </div>
    </div>
  </div>
</div>
<div class="connector"><div class="arrow-down"></div></div>

<!-- ═══ SECTION 3: ALL SOLUTIONS ═══ -->
<div class="section">
  <div class="section-hdr orange">ALL POSSIBLE GOAL PERMUTATIONS — {len(analyses)} Configurations</div>
  <table>
    <tr><th>#</th><th>Goal Configuration</th><th>Actions</th><th>Reversals</th><th>Status</th></tr>
    {summary_rows}
  </table>
</div>
<div class="connector"><div class="arrow-down"></div></div>

<!-- ═══ INDIVIDUAL SOLUTIONS ═══ -->
{solution_sections}

<!-- ═══ END ═══ -->
<div class="section" style="text-align:center;background:#e8f5e9;border-color:#a5d6a7;">
  <div style="font-size:20px;font-weight:bold;color:#1b5e20;">
    ✓ ALL {solved_count} SOLUTIONS COMPLETE
  </div>
  <div style="font-size:13px;color:#555;margin-top:5px;">
    Best: {best_actions} actions |
    Worst: {worst_actions} actions |
    Engine always returns to Track {config['engine_origin']}
  </div>
</div>

</div>
</body></html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def convert_to_jpg(html_path, out_dir):
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from PIL import Image

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1200,800")
        driver = webdriver.Edge(options=opts)
        driver.get("file:///" + html_path.replace("\\", "/"))
        time.sleep(2)

        # Get full page height
        height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1200, height + 100)
        time.sleep(1)

        png = os.path.join(out_dir, "continuous_flow_full.png")
        driver.save_screenshot(png)
        img = Image.open(png).convert("RGB")
        jpg = os.path.join(out_dir, "continuous_flow_full.jpg")
        img.save(jpg, "JPEG", quality=95)
        os.remove(png)
        print(f"  Full-page JPG: {jpg}")

        # Also save individual sections
        sections = driver.find_elements("css selector", ".section")
        paths = [jpg]
        for i, sec in enumerate(sections, 1):
            driver.execute_script("arguments[0].scrollIntoView(true);", sec)
            time.sleep(0.3)
            sp = os.path.join(out_dir, f"continuous_section_{i}.png")
            sec.screenshot(sp)
            si = Image.open(sp).convert("RGB")
            sj = os.path.join(out_dir, f"continuous_section_{i}.jpg")
            si.save(sj, "JPEG", quality=95)
            os.remove(sp)
            paths.append(sj)
            print(f"  Section {i} JPG: {sj}")

        driver.quit()
        return paths
    except Exception as e:
        print(f"  JPG error: {e}")
        return []


if __name__ == "__main__":
    config = build_config_from_dict(PRESET_UNCERTAIN)
    print("Solving all permutations...")
    all_goals = generate_all_goals(config)
    analyses = []
    for i, goal in enumerate(all_goals):
        result = solve_bfs(config, goal_override=goal, max_depth=22)
        if result:
            analyses.append(analyze_solution(result, config, goal))
            print(f"  [{i+1}/{len(all_goals)}] ✓ {result.reversals} rev, {len(result.actions)} actions")
        else:
            analyses.append(None)
            print(f"  [{i+1}/{len(all_goals)}] ✗ No solution")

    out_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(out_dir, "continuous_flow.html")
    generate_continuous_html(analyses, config, html_path)
    print(f"\nHTML: {html_path}")

    print("\nConverting to JPG...")
    convert_to_jpg(html_path, out_dir)
    print("\nDone!")
