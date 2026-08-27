"""
Dynamic Interactive Shunting Puzzle Solver
==========================================
Accepts ANY user-defined configuration:
  - Custom tracks, junctions, rolling stock
  - Custom initial and goal positions
  - "ANY" goal for uncertain wagon placement (explores all permutations)
  - Engine always returns to original position

Solves via BFS, generates HTML flowchart + JPG output.
"""

from collections import deque
from dataclasses import dataclass, field
from itertools import permutations
from typing import Optional
import json, os, time


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1: INITIALIZATION — Build config from user input
# ═══════════════════════════════════════════════════════════════════════════════

def build_config_interactive() -> dict:
    """Gather puzzle configuration from user interactively."""
    print("=" * 65)
    print("  DYNAMIC SHUNTING PUZZLE SOLVER — CONFIGURATION")
    print("=" * 65)

    # Tracks
    tracks_input = input("\nEnter track names (comma-separated, e.g. A,B,C,D): ").strip()
    tracks = [t.strip().upper() for t in tracks_input.split(",")]
    print(f"  Tracks registered: {tracks}")

    # Junctions
    print("\nDefine junctions (connections between tracks).")
    print("  Format: FROM,TO,CAPACITY  (use 'inf' for unlimited)")
    print("  Type 'done' when finished.")
    junctions = {}
    while True:
        j = input("  Junction: ").strip()
        if j.lower() == "done":
            break
        parts = [p.strip() for p in j.split(",")]
        if len(parts) != 3:
            print("    ✗ Invalid format. Use: FROM,TO,CAPACITY")
            continue
        f, t = parts[0].upper(), parts[1].upper()
        cap = float("inf") if parts[2].lower() == "inf" else int(parts[2])
        junctions[(f, t)] = cap
        junctions[(t, f)] = cap
        print(f"    ✓ {f} ↔ {t} : {cap}m")

    # Rolling stock
    print("\nDefine rolling stock.")
    print("  Format: NAME,LENGTH  (e.g. EE,16)")
    print("  Type 'done' when finished.")
    stock_length = {}
    while True:
        s = input("  Stock: ").strip()
        if s.lower() == "done":
            break
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 2:
            print("    ✗ Invalid format. Use: NAME,LENGTH")
            continue
        name, length = parts[0].upper(), int(parts[1])
        stock_length[name] = length
        print(f"    ✓ {name} = {length}m")

    # Engine
    engine = input("\nWhich stock item is the ENGINE? ").strip().upper()
    print(f"  Engine: {engine} ({stock_length.get(engine, '?')}m)")

    # Max coupled wagons
    max_coupled = int(input("Max wagons coupled behind engine (e.g. 2): ").strip() or "2")

    # Track D limit (or general siding limits)
    siding_limits = {}
    print("\nAny track with wagon storage limits? (e.g. D,1 means Track D max 1 wagon)")
    print("  Type 'done' if none.")
    while True:
        sl = input("  Limit: ").strip()
        if sl.lower() == "done":
            break
        parts = [p.strip() for p in sl.split(",")]
        if len(parts) == 2:
            siding_limits[parts[0].upper()] = int(parts[1])
            print(f"    ✓ Track {parts[0].upper()} max {parts[1]} wagon(s)")

    # Initial positions
    print("\nSet INITIAL positions.")
    print("  Format: TRACK,ITEM1,ITEM2,...  (e.g. A,EE)")
    print("  Type 'done' when finished.")
    initial = {t: [] for t in tracks}
    while True:
        p = input("  Position: ").strip()
        if p.lower() == "done":
            break
        parts = [x.strip().upper() for x in p.split(",")]
        track = parts[0]
        items = parts[1:]
        initial[track] = items
        print(f"    ✓ Track {track}: {items}")

    # Goal positions
    print("\nSet GOAL positions.")
    print("  Format: TRACK,ITEM1,ITEM2,...")
    print("  Use 'ANY' for a track to try ALL possible wagon placements.")
    print("  Engine will always return to its original track.")
    print("  Type 'done' when finished.")
    goal = {t: [] for t in tracks}
    uncertain_tracks = []
    while True:
        p = input("  Goal: ").strip()
        if p.lower() == "done":
            break
        parts = [x.strip().upper() for x in p.split(",")]
        track = parts[0]
        items = parts[1:]
        if "ANY" in items:
            uncertain_tracks.append(track)
            goal[track] = ["ANY"]
            print(f"    ✓ Track {track}: ANY (will try all permutations)")
        else:
            goal[track] = items
            print(f"    ✓ Track {track}: {items}")

    # Engine always returns to origin
    engine_origin = None
    for t, items in initial.items():
        if engine in items:
            engine_origin = t
            break
    if engine not in goal.get(engine_origin, []):
        goal[engine_origin] = goal.get(engine_origin, [])
        if engine not in goal[engine_origin]:
            goal[engine_origin].append(engine)
    print(f"\n  Engine {engine} will return to Track {engine_origin}")

    config = {
        "junctions": junctions,
        "stock_length": stock_length,
        "engine": engine,
        "max_coupled": max_coupled,
        "engine_min_space": stock_length.get(engine, 16),
        "siding_limits": siding_limits,
        "initial": initial,
        "goal": goal,
        "tracks": tracks,
        "uncertain_tracks": uncertain_tracks,
        "engine_origin": engine_origin,
    }
    return config


def build_config_from_dict(params: dict) -> dict:
    """Build config programmatically (for non-interactive use)."""
    junctions = {}
    for (f, t), cap in params["junctions"].items():
        junctions[(f, t)] = cap
        junctions[(t, f)] = cap

    engine = params["engine"]
    engine_origin = None
    for t, items in params["initial"].items():
        if engine in items:
            engine_origin = t
            break

    return {
        "junctions": junctions,
        "stock_length": params["stock_length"],
        "engine": engine,
        "max_coupled": params.get("max_coupled", 2),
        "engine_min_space": params["stock_length"].get(engine, 16),
        "siding_limits": params.get("siding_limits", {}),
        "initial": params["initial"],
        "goal": params["goal"],
        "tracks": params["tracks"],
        "uncertain_tracks": params.get("uncertain_tracks", []),
        "engine_origin": engine_origin,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2: STATE REPRESENTATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PuzzleState:
    track_contents: tuple
    engine_track: str
    coupled: tuple

    @staticmethod
    def from_dict(tracks: dict, engine_track: str, coupled: list):
        tc = tuple(sorted((k, tuple(sorted(v))) for k, v in tracks.items()))
        return PuzzleState(tc, engine_track, tuple(sorted(coupled)))

    def get_tracks(self) -> dict:
        return {k: list(v) for k, v in self.track_contents}


@dataclass
class SearchNode:
    state: PuzzleState
    actions: list = field(default_factory=list)
    reversals: int = 0
    last_direction: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3: VALIDATE_CAPACITY
# ═══════════════════════════════════════════════════════════════════════════════

def validate_capacity(consist, from_track, to_track, config):
    key = (from_track, to_track)
    if key not in config["junctions"]:
        return False
    cap = config["junctions"][key]
    total = sum(config["stock_length"][i] for i in consist)
    return total <= cap


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4: DEADLOCK_CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def deadlock_check(state, config):
    engine = config["engine"]
    loc = state.engine_track
    for (f, t) in config["junctions"]:
        if f != loc:
            continue
        if validate_capacity([engine], f, t, config):
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5: ACTION GENERATION (SELECT NEXT LEGAL ACTION)
# ═══════════════════════════════════════════════════════════════════════════════

def get_neighbors(node, config):
    neighbors = []
    state = node.state
    tracks = state.get_tracks()
    engine_track = state.engine_track
    coupled = list(state.coupled)
    engine = config["engine"]
    wagons_on_track = [i for i in tracks.get(engine_track, []) if i != engine]

    # COUPLE
    if len(coupled) < config["max_coupled"]:
        for wagon in wagons_on_track:
            new_tracks = {k: list(v) for k, v in tracks.items()}
            new_tracks[engine_track].remove(wagon)
            new_coupled = sorted(coupled + [wagon])
            new_state = PuzzleState.from_dict(new_tracks, engine_track, new_coupled)
            neighbors.append(SearchNode(
                state=new_state,
                actions=node.actions + [("COUPLE", wagon, engine_track, engine_track)],
                reversals=node.reversals,
                last_direction=node.last_direction,
            ))

    # DECOUPLE
    for wagon in coupled:
        new_tracks = {k: list(v) for k, v in tracks.items()}
        new_tracks[engine_track].append(wagon)
        new_coupled = [w for w in coupled if w != wagon]
        non_engine = [i for i in new_tracks.get(engine_track, []) if i != engine]
        limit = config["siding_limits"].get(engine_track)
        if limit is not None and len(non_engine) > limit:
            continue
        new_state = PuzzleState.from_dict(new_tracks, engine_track, new_coupled)
        neighbors.append(SearchNode(
            state=new_state,
            actions=node.actions + [("DECOUPLE", wagon, engine_track, engine_track)],
            reversals=node.reversals,
            last_direction=node.last_direction,
        ))

    # MOVE
    consist = [engine] + coupled
    for (f, t) in config["junctions"]:
        if f != engine_track:
            continue
        if not validate_capacity(consist, f, t, config):
            continue
        new_tracks = {k: list(v) for k, v in tracks.items()}
        if engine in new_tracks[f]:
            new_tracks[f].remove(engine)
        new_tracks[t].append(engine)
        non_engine_on_t = [i for i in new_tracks[t] if i != engine] + coupled
        limit_t = config["siding_limits"].get(t)
        if limit_t is not None and len([w for w in non_engine_on_t if w != engine]) > limit_t:
            continue
        new_state = PuzzleState.from_dict(new_tracks, t, coupled)
        direction = f"{f}->{t}"
        rev = node.reversals
        if node.last_direction:
            prev = node.last_direction.split("->")
            if prev[0] == t and prev[1] == f:
                rev += 1
        neighbors.append(SearchNode(
            state=new_state,
            actions=node.actions + [("MOVE", "+".join(consist), f, t)],
            reversals=rev,
            last_direction=direction,
        ))

    # FLY_SHUNT
    for wagon in coupled:
        for (f, t) in config["junctions"]:
            if f != engine_track:
                continue
            if not validate_capacity([wagon], f, t, config):
                continue
            new_tracks = {k: list(v) for k, v in tracks.items()}
            new_tracks[t].append(wagon)
            non_engine_on_t = [i for i in new_tracks[t] if i != engine]
            limit_t = config["siding_limits"].get(t)
            if limit_t is not None and len(non_engine_on_t) > limit_t:
                continue
            new_coupled = [w for w in coupled if w != wagon]
            new_state = PuzzleState.from_dict(new_tracks, engine_track, new_coupled)
            direction = f"{f}->{t}"
            rev = node.reversals
            if node.last_direction:
                prev = node.last_direction.split("->")
                if prev[0] == t and prev[1] == f:
                    rev += 1
            neighbors.append(SearchNode(
                state=new_state,
                actions=node.actions + [("FLY_SHUNT", wagon, f, t)],
                reversals=rev,
                last_direction=direction,
            ))

    return neighbors


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 6: TERMINATION CHECK / GOAL MATCHING
# ═══════════════════════════════════════════════════════════════════════════════

def is_goal(state, goal_config):
    tracks = state.get_tracks()
    if state.coupled:
        return False
    for track, expected in goal_config.items():
        actual = sorted(tracks.get(track, []))
        if actual != sorted(expected):
            return False
    return True


def generate_all_goals(config):
    """
    If some tracks have 'ANY', generate all valid permutations of
    wagon placements for those tracks.
    """
    uncertain = config.get("uncertain_tracks", [])
    if not uncertain:
        return [config["goal"]]

    engine = config["engine"]
    all_wagons = [s for s in config["stock_length"] if s != engine]

    # Wagons already assigned to fixed tracks
    fixed_assignments = {}
    assigned_wagons = set()
    for t, items in config["goal"].items():
        if "ANY" not in items:
            fixed_assignments[t] = items
            assigned_wagons.update(i for i in items if i != engine)

    unassigned = [w for w in all_wagons if w not in assigned_wagons]
    uncertain_tracks = [t for t in uncertain if "ANY" in config["goal"].get(t, [])]

    if len(unassigned) < len(uncertain_tracks):
        # Pad with empty
        pass

    goals = []
    for perm in permutations(unassigned):
        goal = dict(fixed_assignments)
        for t in config["tracks"]:
            if t not in goal:
                goal[t] = []
        for i, t in enumerate(uncertain_tracks):
            if i < len(perm):
                goal[t] = [perm[i]]
            else:
                goal[t] = []
        # Distribute remaining wagons
        remaining = list(perm[len(uncertain_tracks):])
        for w in remaining:
            for t in uncertain_tracks:
                if not goal[t]:
                    goal[t] = [w]
                    break
        # Ensure engine returns home
        origin = config["engine_origin"]
        if engine not in goal.get(origin, []):
            goal[origin] = goal.get(origin, []) + [engine]
        goals.append(goal)

    # Remove duplicates
    unique = []
    seen = set()
    for g in goals:
        key = tuple(sorted((k, tuple(sorted(v))) for k, v in g.items()))
        if key not in seen:
            seen.add(key)
            unique.append(g)
    return unique


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 7: BFS SOLVER
# ═══════════════════════════════════════════════════════════════════════════════

def solve_bfs(config, goal_override=None, max_depth=22):
    goal = goal_override or config["goal"]
    initial_tracks = {t: list(config["initial"].get(t, [])) for t in config["tracks"]}

    engine_track = None
    for t, items in initial_tracks.items():
        if config["engine"] in items:
            engine_track = t
            break

    initial_state = PuzzleState.from_dict(initial_tracks, engine_track, [])
    start = SearchNode(state=initial_state, actions=[], reversals=0)

    if is_goal(initial_state, goal):
        return start

    visited = {initial_state}
    queue = deque([start])
    nodes = 0
    t0 = time.time()

    while queue:
        node = queue.popleft()
        if len(node.actions) >= max_depth:
            continue
        nodes += 1
        for nb in get_neighbors(node, config):
            if nb.state in visited:
                continue
            visited.add(nb.state)
            if is_goal(nb.state, goal):
                elapsed = time.time() - t0
                return nb
            queue.append(nb)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 8: SOLUTION ANALYZER — Builds structured data from solution
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_solution(result, config, goal):
    """Extract structured analysis from a solution."""
    if result is None:
        return None

    # Replay actions to build state snapshots
    initial_tracks = {t: list(config["initial"].get(t, [])) for t in config["tracks"]}
    engine = config["engine"]
    engine_track = config["engine_origin"]
    coupled = []

    steps = []
    steps.append({
        "step": 0, "action_type": "INIT", "detail": "Initial State",
        "from": "-", "to": "-",
        "state": {t: list(v) for t, v in initial_tracks.items()},
        "coupled": [], "engine_on": engine_track,
    })

    current_tracks = {t: list(v) for t, v in initial_tracks.items()}

    for i, action in enumerate(result.actions):
        act_type, item, frm, to = action
        if act_type == "COUPLE":
            coupled.append(item)
            current_tracks[engine_track].remove(item)
        elif act_type == "DECOUPLE":
            coupled.remove(item)
            current_tracks[engine_track].append(item)
        elif act_type == "MOVE":
            if engine in current_tracks[frm]:
                current_tracks[frm].remove(engine)
            current_tracks[to].append(engine)
            engine_track = to
        elif act_type == "FLY_SHUNT":
            coupled.remove(item)
            current_tracks[to].append(item)

        steps.append({
            "step": i + 1,
            "action_type": act_type,
            "detail": format_action(action),
            "from": frm, "to": to,
            "state": {t: list(v) for t, v in current_tracks.items()},
            "coupled": list(coupled),
            "engine_on": engine_track,
        })

    # Capacity checks used
    capacity_checks = []
    for action in result.actions:
        act_type, item, frm, to = action
        if act_type in ("MOVE", "FLY_SHUNT"):
            cap = config["junctions"].get((frm, to), "?")
            if act_type == "MOVE":
                parts = item.split("+")
                length = sum(config["stock_length"].get(p, 0) for p in parts)
            else:
                length = config["stock_length"].get(item, 0)
            capacity_checks.append({
                "route": f"{frm}→{to}",
                "capacity": cap,
                "length": length,
                "pass": length <= cap if cap != "?" else False,
            })

    # Reversal analysis
    reversals = []
    prev_dir = ""
    for action in result.actions:
        act_type, item, frm, to = action
        if act_type in ("MOVE", "FLY_SHUNT"):
            direction = f"{frm}→{to}"
            is_rev = False
            if prev_dir:
                p = prev_dir.replace("→", ",").split(",")
                if p[0] == to and p[1] == frm:
                    is_rev = True
            reversals.append({"move": direction, "reversal": is_rev, "prev": prev_dir})
            prev_dir = direction

    return {
        "steps": steps,
        "total_actions": len(result.actions),
        "reversals_detail": reversals,
        "reversal_count": result.reversals,
        "capacity_checks": capacity_checks,
        "goal": goal,
        "config": config,
    }


def format_action(action):
    act_type, item, frm, to = action
    if act_type == "COUPLE":
        return f"COUPLE {item} on Track {frm}"
    elif act_type == "DECOUPLE":
        return f"DECOUPLE {item} on Track {frm}"
    elif act_type == "MOVE":
        return f"MOVE [{item}] {frm}→{to}"
    elif act_type == "FLY_SHUNT":
        return f"FLY_SHUNT {item} {frm}→{to} (engine stays {frm})"
    return str(action)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 9: HTML FLOWCHART GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_html_report(analyses, config, output_path):
    """Generate a complete HTML report with flowcharts for all solutions."""
    engine = config["engine"]
    tracks = config["tracks"]

    # Derive movement rules
    rules = []
    for (f, t), cap in sorted(set((k, v) for k, v in config["junctions"].items())):
        if f >= t:
            continue
        cap_str = "∞" if cap == float("inf") else f"{cap}m"
        eng_len = config["stock_length"].get(engine, 0)
        eng_ok = "✓" if eng_len <= cap else "✗"
        eng_1w = "✓" if eng_len + 8 <= cap else "✗"
        eng_2w = "✓" if eng_len + 16 <= cap else "✗"
        rules.append((f, t, cap_str, eng_ok, eng_1w, eng_2w))

    # Generate junction rules HTML
    junction_rows = ""
    for f, t, cap_str, e, e1, e2 in rules:
        junction_rows += f"<tr><td>{f} ↔ {t}</td><td>{cap_str}</td><td>{e}</td><td>{e1}</td><td>{e2}</td></tr>\n"

    # Generate stock rows
    stock_rows = ""
    for name, length in config["stock_length"].items():
        role = "Engine" if name == engine else "Wagon"
        init_track = "-"
        for t, items in config["initial"].items():
            if name in items:
                init_track = t
        stock_rows += f"<tr><td>{name}</td><td>{role}</td><td>{length}m</td><td>Track {init_track}</td></tr>\n"

    # Siding limits
    siding_rows = ""
    for t, limit in config.get("siding_limits", {}).items():
        siding_rows += f"<tr><td>Track {t}</td><td>Max {limit} wagon(s)</td></tr>\n"
    if not siding_rows:
        siding_rows = "<tr><td colspan='2'>No special limits</td></tr>"

    # Deadlock analysis
    deadlock_items = ""
    for t in tracks:
        exits = [(f2, t2, config["junctions"][(f2, t2)])
                 for (f2, t2) in config["junctions"] if f2 == t]
        exit_strs = []
        for f2, t2, cap in exits:
            cap_s = "∞" if cap == float("inf") else f"{cap}m"
            eng_fit = "✓" if config["stock_length"][engine] <= cap else "✗"
            exit_strs.append(f"{t2}({cap_s}, engine:{eng_fit})")
        can_escape = any(config["stock_length"][engine] <= config["junctions"][(t, t2)]
                         for (f2, t2) in config["junctions"] if f2 == t)
        status = "SAFE" if can_escape else "⚠ RISK"
        deadlock_items += f"<tr><td>Track {t}</td><td>{', '.join(exit_strs)}</td><td><b>{status}</b></td></tr>\n"

    # Build per-solution pages
    solution_pages = ""
    for sol_idx, analysis in enumerate(analyses):
        if analysis is None:
            solution_pages += f"""
            <div class="page">
              <div class="header-bar red">SOLUTION {sol_idx+1} — NO SOLUTION FOUND</div>
              <p>Goal: {analyses[sol_idx]}</p>
              <p>No valid sequence of moves exists within search depth.</p>
            </div>"""
            continue

        goal = analysis["goal"]
        goal_str = ", ".join(f"{t}={goal.get(t, [])}" for t in tracks)

        # Step rows for state transition table
        step_rows = ""
        for s in analysis["steps"]:
            track_cols = "".join(
                f"<td>{', '.join(s['state'].get(t, [])) or '—'}</td>" for t in tracks
            )
            coupled_str = ", ".join(s["coupled"]) or "—"
            step_rows += f"""<tr>
              <td>{s['step']}</td><td>{s['detail']}</td>
              {track_cols}
              <td>{coupled_str}</td><td>{s['engine_on']}</td>
            </tr>\n"""

        track_headers = "".join(f"<th>Track {t}</th>" for t in tracks)

        # Capacity check rows
        cap_rows = ""
        for c in analysis["capacity_checks"]:
            cap_s = "∞" if c["capacity"] == float("inf") else f"{c['capacity']}m"
            status = "✓ PASS" if c["pass"] else "✗ FAIL"
            cap_rows += f"<tr><td>{c['route']}</td><td>{cap_s}</td><td>{c['length']}m</td><td>{status}</td></tr>\n"

        # Reversal rows
        rev_rows = ""
        rev_num = 0
        for r in analysis["reversals_detail"]:
            if r["reversal"]:
                rev_num += 1
            rev_str = f"<b style='color:#c62828'>YES (#{rev_num})</b>" if r["reversal"] else "no"
            prev_str = r["prev"] or "—"
            rev_rows += f"<tr><td>{r['move']}</td><td>{prev_str}</td><td>{rev_str}</td></tr>\n"

        # Flowchart steps
        flow_steps = ""
        for s in analysis["steps"]:
            if s["step"] == 0:
                continue
            act = s["action_type"]
            color = {"COUPLE": "#e3f2fd", "DECOUPLE": "#e3f2fd",
                     "MOVE": "#c8e6c9", "FLY_SHUNT": "#fff3e0"}.get(act, "#f5f5f5")
            border = {"COUPLE": "#1565c0", "DECOUPLE": "#1565c0",
                      "MOVE": "#2e7d32", "FLY_SHUNT": "#e65100"}.get(act, "#999")
            flow_steps += f"""
            <div style="display:flex;align-items:center;gap:10px;margin:4px 0;">
              <span style="background:#1a237e;color:#fff;border-radius:50%;width:28px;height:28px;
                display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:13px;
                flex-shrink:0;">{s['step']}</span>
              <div style="background:{color};border:2px solid {border};padding:6px 12px;border-radius:4px;
                flex:1;font-size:13px;">
                <b>{act}</b>: {s['detail']}
              </div>
            </div>
            <div style="width:2px;height:12px;background:#333;margin:0 0 0 13px;"></div>
            """

        # Validation rows
        val_rows = ""
        for t, expected in goal.items():
            actual = analysis["steps"][-1]["state"].get(t, [])
            match = sorted(actual) == sorted(expected)
            val_rows += f"""<tr>
              <td>Track {t}</td><td>{expected}</td><td>{actual}</td>
              <td style="color:{'#2e7d32' if match else '#c62828'};font-weight:bold">
                {'✓ PASS' if match else '✗ FAIL'}</td>
            </tr>\n"""

        solution_pages += f"""
        <div class="page">
          <div class="header-bar green">SOLUTION {sol_idx+1} — Goal: {goal_str}</div>
          <p style="margin-bottom:10px;"><b>Actions: {analysis['total_actions']}</b> |
             <b>Reversals: {analysis['reversal_count']}</b></p>

          <div class="two-col">
            <div>
              <h3 style="margin:10px 0 5px;">Solution Flowchart</h3>
              <div style="border:2px solid #1a237e;border-radius:6px;padding:15px;background:#fafafa;">
                <div style="background:#ef9a9a;border:2px solid #c62828;border-radius:20px;padding:6px;
                  text-align:center;font-weight:bold;margin-bottom:5px;">START</div>
                <div style="width:2px;height:12px;background:#333;margin:0 0 0 13px;"></div>
                {flow_steps}
                <div style="background:#ef9a9a;border:2px solid #c62828;border-radius:20px;padding:6px;
                  text-align:center;font-weight:bold;margin-top:5px;">END ✓</div>
              </div>
            </div>
            <div>
              <h3 style="margin:10px 0 5px;">Final State Validation (Module ⑩)</h3>
              <table><tr><th>Track</th><th>Expected</th><th>Actual</th><th>Status</th></tr>
                {val_rows}</table>

              <h3 style="margin:15px 0 5px;">Capacity Checks (Module ⑤)</h3>
              <table><tr><th>Route</th><th>Capacity</th><th>Length</th><th>Status</th></tr>
                {cap_rows}</table>

              <h3 style="margin:15px 0 5px;">Reversal Analysis (Module ⑨)</h3>
              <table><tr><th>Direction</th><th>Previous</th><th>Reversal?</th></tr>
                {rev_rows}</table>
            </div>
          </div>

          <h3 style="margin:15px 0 5px;">State Transition Table (Module ⑧)</h3>
          <div style="overflow-x:auto;">
          <table style="font-size:12px;">
            <tr><th>Step</th><th>Action</th>{track_headers}<th>Coupled</th><th>Engine On</th></tr>
            {step_rows}
          </table>
          </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dynamic Shunting Puzzle — Solutions</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; color: #222; }}
  .page {{ background: #fff; max-width: 1200px; margin: 0 auto 30px; padding: 25px; border: 1px solid #ccc;
           box-shadow: 0 2px 8px rgba(0,0,0,0.1); page-break-after: always; }}
  .header-bar {{ background: #1a237e; color: #fff; font-weight: bold; font-size: 17px; text-align: center;
                 padding: 10px; margin-bottom: 15px; border-radius: 4px; }}
  .header-bar.red {{ background: #b71c1c; }}
  .header-bar.green {{ background: #2e7d32; }}
  .header-bar.orange {{ background: #e65100; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .module-box {{ border: 2px solid #333; border-radius: 6px; margin: 10px 0; padding: 12px; }}
  .module-box.blue {{ background: #e3f2fd; border-color: #1565c0; }}
  .module-box.yellow {{ background: #fffde7; border-color: #f9a825; }}
  .module-box.green {{ background: #e8f5e9; border-color: #2e7d32; }}
  .module-box.red {{ background: #fce4ec; border-color: #c62828; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }}
  th {{ background: #e0e0e0; padding: 5px 8px; border: 1px solid #999; text-align: left; }}
  td {{ padding: 5px 8px; border: 1px solid #ccc; }}
  ul {{ padding-left: 18px; margin: 5px 0; }}
  li {{ margin: 2px 0; font-size: 13px; }}
  .flow-text {{ font-family: Consolas, monospace; font-size: 13px; background: #fafafa; border: 1px solid #ddd;
                padding: 12px; border-radius: 4px; white-space: pre; line-height: 1.5; overflow-x: auto; }}
  h3 {{ color: #1a237e; }}
</style>
</head>
<body>

<!-- PAGE 1: MASTER FLOWCHART + CONFIGURATION -->
<div class="page">
  <div class="header-bar">DYNAMIC SHUNTING PUZZLE — MASTER FLOWCHART &amp; MODULE DEFINITIONS</div>
  <div class="two-col" style="grid-template-columns: 55% 45%;">
    <div>
      <div class="flow-text">
                        ┌─────────┐
                        │  START  │
                        └────┬────┘
                             │
                    ┌────────▼────────┐
               ①   │ INITIALIZATION  │  Load tracks, junctions,
                    └────────┬────────┘  stock, positions
                             │
                ┌────────────▼────────────┐
           ②   │   TERMINATION CHECK     │  All goals met?
                └────────────┬────────────┘
                             │
                    ◇ Goal satisfied? ◇
                   ╱                   ╲
             YES  ╱                     ╲  NO
                 ╱                       ╲
      ┌─────────▼──────────┐    ┌────────▼─────────────┐
  ⑩  │ FINAL VALIDATION   │  ③│ SELECT NEXT LEGAL    │
      └─────────┬──────────┘    │ ACTION               │
                │               └────────┬─────────────┘
       ◇ All OK? ◇                      │
      ╱           ╲             ┌────────▼────────┐
    YES           NO          ④│ DEADLOCK CHECK  │
     │             │            └────────┬────────┘
     ▼             ▼                     │
  ┌─────┐    Return to ③       ◇ Deadlocked? ◇
  │ END │                     ╱               ╲
  └─────┘                   YES               NO
                              │                │
                   ┌──────────▼──┐    ┌────────▼────────┐
                   │REJECT ACTION│  ⑤│VALIDATE CAPACITY│
                   │→ back to ③  │    └────────┬────────┘
                   └─────────────┘             │
                                      ◇ Valid? ◇
                                     ╱          ╲
                                   YES          NO
                                    │      ┌─────▼───────┐
                           ┌────────▼──┐   │REJECT → ③   │
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
    </div>
    <div>
      <div class="module-box blue">
        <b>① INITIALIZATION — Input Configuration</b>
        <table>
          <tr><th>Tracks</th><td>{', '.join(tracks)}</td></tr>
          <tr><th>Engine</th><td>{engine} ({config['stock_length'][engine]}m)</td></tr>
          <tr><th>Max Coupled</th><td>{config['max_coupled']}</td></tr>
        </table>
        <b>Rolling Stock:</b>
        <table><tr><th>Name</th><th>Role</th><th>Length</th><th>Start</th></tr>{stock_rows}</table>
        <b>Junctions &amp; Capacity:</b>
        <table>
          <tr><th>Route</th><th>Capacity</th><th>{engine}</th><th>+1w</th><th>+2w</th></tr>
          {junction_rows}
        </table>
        <b>Siding Limits:</b>
        <table><tr><th>Track</th><th>Limit</th></tr>{siding_rows}</table>
      </div>

      <div class="module-box yellow">
        <b>④ DEADLOCK CHECK — Per Track Analysis</b>
        <table><tr><th>Track</th><th>Available Exits</th><th>Status</th></tr>{deadlock_items}</table>
      </div>
    </div>
  </div>
</div>

<!-- PAGE 2: MODULE DEFINITIONS -->
<div class="page">
  <div class="header-bar red">MODULE DEFINITIONS — DECISION LOGIC (YES/NO PATHS)</div>
  <div class="two-col">

    <div class="module-box yellow">
      <b>② TERMINATION CHECK</b>
      <p style="font-size:13px;margin:5px 0;">Is every wagon and engine at its goal position with nothing coupled?</p>
      <div class="flow-text" style="font-size:12px;">
  ◇ All items at goal position? ◇
 ╱                                ╲
YES                               NO
 │                                 │
 ▼                                 ▼
┌──────────────────┐    ┌──────────────────────┐
│ Go to ⑩ FINAL   │    │ Go to ③ SELECT NEXT  │
│ VALIDATION       │    │ LEGAL ACTION         │
│                  │    │                      │
│ • Check all      │    │ • Evaluate current   │
│   constraints    │    │   state              │
│ • Confirm order  │    │ • Choose best action │
│ • Verify capacity│    │ • Prioritize moves   │
│   was never      │    │   closer to goal     │
│   exceeded       │    │                      │
└──────────────────┘    └──────────────────────┘
      </div>
    </div>

    <div class="module-box yellow">
      <b>③ SELECT NEXT LEGAL ACTION</b>
      <p style="font-size:13px;margin:5px 0;">Choose from 4 possible action types:</p>
      <div class="flow-text" style="font-size:12px;">
  Current State Analysis
         │
    ┌────▼────┐
    │ Wagon on│──YES──► COUPLE it
    │ track?  │
    └────┬────┘
         │ NO
    ┌────▼──────────┐
    │ Coupled wagon │──YES──► MOVE or FLY_SHUNT
    │ needs to move?│
    └────┬──────────┘
         │ NO
    ┌────▼──────────┐
    │ Need to reach │──YES──► MOVE engine alone
    │ another wagon?│
    └────┬──────────┘
         │ NO
    ┌────▼──────────┐
    │ Coupled wagon │──YES──► DECOUPLE it
    │ at dest?      │
    └───────────────┘
      </div>
    </div>

    <div class="module-box yellow">
      <b>④ DEADLOCK CHECK</b>
      <p style="font-size:13px;margin:5px 0;">Can engine escape current track with current coupling?</p>
      <div class="flow-text" style="font-size:12px;">
  For each adjacent track from engine position:
         │
    ┌────▼──────────────────┐
    │ Can consist fit       │
    │ through junction?     │
    └────┬──────────────────┘
         │
    ◇ Any valid exit? ◇
   ╱                    ╲
  YES                   NO
   │                     │
   ▼                     ▼
┌─────────────┐   ┌─────────────────┐
│ SAFE        │   │ Can engine move │
│ → Continue  │   │ ALONE to any    │
│   to ⑤     │   │ adjacent?       │
└─────────────┘   └────┬────────────┘
                       │
                  ◇ Alone OK? ◇
                 ╱              ╲
               YES              NO
                │                │
                ▼                ▼
          ┌──────────┐    ┌──────────────┐
          │ DECOUPLE │    │ DEADLOCKED!  │
          │ first,   │    │ REJECT action│
          │ then move│    │ → back to ③ │
          └──────────┘    └──────────────┘
      </div>
    </div>

    <div class="module-box yellow">
      <b>⑤ VALIDATE CAPACITY</b>
      <p style="font-size:13px;margin:5px 0;">Pre-move validation of ALL constraints:</p>
      <div class="flow-text" style="font-size:12px;">
  ◇ consist_length ≤ junction_capacity? ◇
 ╱                                        ╲
YES                                       NO
 │                                         │
 ▼                                         ▼
◇ coupled ≤ max_coupled? ◇          ┌──────────┐
╱                         ╲          │ REJECT   │
YES                       NO         │ → ③     │
│                          │         └──────────┘
▼                          ▼
◇ siding limits OK? ◇   REJECT → ③
╱                     ╲
YES                   NO
│                      │
▼                      ▼
◇ engine 16m clear? ◇ REJECT → ③
╱                    ╲
YES                  NO
│                     │
▼                     ▼
PASS → ⑥         REJECT → ③
      </div>
    </div>
  </div>

  <div class="two-col" style="margin-top:15px;">
    <div class="module-box yellow">
      <b>⑥ COUPLE / DECOUPLE — Decision Flow</b>
      <div class="flow-text" style="font-size:12px;">
  ◇ Action type? ◇
 ╱                 ╲
COUPLE            DECOUPLE
 │                   │
 ▼                   ▼
◇ Same track    ◇ Wagon in
│ as engine?    │ coupled list?
╱           ╲   ╱            ╲
YES         NO  YES          NO
│            │   │             │
▼            ▼   ▼             ▼
◇ Count    FAIL  Remove from  FAIL
│ &lt; max?        coupled list → ③
╱      ╲         Add to track
YES    NO              │
│       │              ▼
▼       ▼           PASS → ⑦
Add to  FAIL
coupled  → ③
Remove
from track
   │
   ▼
PASS → ⑦
      </div>
    </div>

    <div class="module-box yellow">
      <b>⑦ MOVE / FLY_SHUNT — Decision Flow</b>
      <div class="flow-text" style="font-size:12px;">
  ◇ Action type? ◇
 ╱                  ╲
MOVE              FLY_SHUNT
 │                    │
 ▼                    ▼
Engine + coupled   Wagon alone rolls
all travel to      through junction.
destination.       Engine stays.
 │                    │
 ▼                    ▼
Update engine      Remove wagon from
position.          coupled list.
 │                 Add to destination.
 ▼                    │
PASS → ⑧           PASS → ⑧
      </div>
    </div>
  </div>

  <div class="two-col" style="margin-top:15px;">
    <div class="module-box yellow">
      <b>⑧ STATE UPDATE</b>
      <div class="flow-text" style="font-size:12px;">
  After action execution:
    │
    ├── Update track contents
    ├── Update engine position
    ├── Update coupled list
    ├── Update junction occupancy
    ├── Increment move counter
    │
    ▼
  ◇ Was direction reversed? ◇
 ╱                            ╲
YES                           NO
 │                             │
 ▼                             ▼
GO TO ⑨                  GO TO ②
(update reversal count)  (termination check)
      </div>
    </div>

    <div class="module-box" style="background:#fce4ec;border-color:#c62828;">
      <b>⑩ FINAL VALIDATION</b>
      <div class="flow-text" style="font-size:12px;">
  ◇ Every item at goal position? ◇
 ╱                                 ╲
YES                                NO
 │                                  │
 ▼                                  ▼
◇ Nothing coupled? ◇          FAIL → ③
╱                    ╲
YES                  NO
│                     │
▼                     ▼
◇ No constraints   FAIL → ③
│ violated?
╱            ╲
YES          NO
│             │
▼             ▼
┌─────┐   FAIL → ③
│ END │
│  ✓  │
└─────┘
      </div>
    </div>
  </div>
</div>

<!-- SOLUTION PAGES -->
{solution_pages}

</body></html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 10: JPG CONVERTER
# ═══════════════════════════════════════════════════════════════════════════════

def convert_html_to_jpg(html_path, out_dir):
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from PIL import Image
        import time as _time

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1400,2200")
        driver = webdriver.Edge(options=opts)
        driver.get("file:///" + html_path.replace("\\", "/"))
        _time.sleep(2)
        pages = driver.find_elements("css selector", ".page")
        paths = []
        for i, page in enumerate(pages, 1):
            driver.execute_script("arguments[0].scrollIntoView(true);", page)
            _time.sleep(0.3)
            png = os.path.join(out_dir, f"solution_page_{i}.png")
            page.screenshot(png)
            img = Image.open(png).convert("RGB")
            jpg = os.path.join(out_dir, f"solution_page_{i}.jpg")
            img.save(jpg, "JPEG", quality=95)
            os.remove(png)
            paths.append(jpg)
            print(f"  Saved: {jpg}")
        driver.quit()
        return paths
    except Exception as e:
        print(f"  JPG conversion error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN — FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_with_config(config):
    """Run the full solve + report pipeline with a given config."""
    print("\n" + "=" * 65)
    print("  SOLVING...")
    print("=" * 65)

    all_goals = generate_all_goals(config)
    print(f"  Goal configurations to solve: {len(all_goals)}")

    analyses = []
    for i, goal in enumerate(all_goals):
        goal_str = ", ".join(f"{t}={goal.get(t, [])}" for t in config["tracks"])
        print(f"\n  [{i+1}/{len(all_goals)}] Goal: {goal_str}")
        result = solve_bfs(config, goal_override=goal, max_depth=22)
        if result:
            print(f"    ✓ Solved in {len(result.actions)} actions, {result.reversals} reversals")
            analysis = analyze_solution(result, config, goal)
            analyses.append(analysis)
        else:
            print(f"    ✗ No solution found")
            analyses.append(None)

    # Generate report
    out_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(out_dir, "dynamic_report.html")
    generate_html_report(
        [a for a in analyses if a is not None],
        config, html_path,
    )
    print(f"\n  HTML report: {html_path}")

    # Convert to JPG
    print("\n  Converting to JPG...")
    jpgs = convert_html_to_jpg(html_path, out_dir)

    # Summary
    solved = sum(1 for a in analyses if a is not None)
    print(f"\n{'=' * 65}")
    print(f"  COMPLETE: {solved}/{len(all_goals)} goals solved")
    if solved > 0:
        best = min(a["total_actions"] for a in analyses if a is not None)
        print(f"  Best solution: {best} actions")
    print(f"  HTML: {html_path}")
    print(f"  JPGs: {len(jpgs)} pages generated")
    print(f"{'=' * 65}")

    return analyses


def main():
    print("Select input mode:")
    print("  1. Interactive (enter values manually)")
    print("  2. Use preset examples")
    choice = input("Choice (1/2): ").strip()

    if choice == "1":
        config = build_config_interactive()
    else:
        print("\nPreset examples:")
        print("  1. Original 2S puzzle (A=EE,B=XX,C=YY,D=ZZ → A=EE,B=ZZ,C=XX,D=YY)")
        print("  2. 3-wagon swap on triangle (no siding D)")
        print("  3. Uncertain goal — all permutations")
        print("  4. Custom JSON input")
        ex = input("Example (1/2/3/4): ").strip()

        if ex == "1":
            config = build_config_from_dict(PRESET_ORIGINAL)
        elif ex == "2":
            config = build_config_from_dict(PRESET_TRIANGLE)
        elif ex == "3":
            config = build_config_from_dict(PRESET_UNCERTAIN)
        elif ex == "4":
            path = input("Path to JSON config file: ").strip()
            with open(path) as f:
                config = build_config_from_dict(json.load(f))
        else:
            config = build_config_from_dict(PRESET_ORIGINAL)

    run_with_config(config)


# ═══════════════════════════════════════════════════════════════════════════════
# PRESET CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════════

PRESET_ORIGINAL = {
    "junctions": {
        ("A", "B"): 24, ("B", "C"): float("inf"),
        ("C", "A"): 8, ("B", "D"): 16,
    },
    "stock_length": {"EE": 16, "XX": 8, "YY": 8, "ZZ": 8},
    "engine": "EE",
    "max_coupled": 2,
    "siding_limits": {"D": 1},
    "initial": {"A": ["EE"], "B": ["XX"], "C": ["YY"], "D": ["ZZ"]},
    "goal": {"A": ["EE"], "B": ["ZZ"], "C": ["XX"], "D": ["YY"]},
    "tracks": ["A", "B", "C", "D"],
}

PRESET_TRIANGLE = {
    "junctions": {
        ("A", "B"): 24, ("B", "C"): float("inf"), ("C", "A"): 8,
    },
    "stock_length": {"EE": 16, "XX": 8, "YY": 8},
    "engine": "EE",
    "max_coupled": 2,
    "siding_limits": {},
    "initial": {"A": ["EE"], "B": ["XX"], "C": ["YY"]},
    "goal": {"A": ["EE"], "B": ["YY"], "C": ["XX"]},
    "tracks": ["A", "B", "C"],
}

PRESET_UNCERTAIN = {
    "junctions": {
        ("A", "B"): 24, ("B", "C"): float("inf"),
        ("C", "A"): 8, ("B", "D"): 16,
    },
    "stock_length": {"EE": 16, "XX": 8, "YY": 8, "ZZ": 8},
    "engine": "EE",
    "max_coupled": 2,
    "siding_limits": {"D": 1},
    "initial": {"A": ["EE"], "B": ["XX"], "C": ["YY"], "D": ["ZZ"]},
    "goal": {"A": ["EE"], "B": ["ANY"], "C": ["ANY"], "D": ["ANY"]},
    "tracks": ["A", "B", "C", "D"],
    "uncertain_tracks": ["B", "C", "D"],
}


if __name__ == "__main__":
    main()
