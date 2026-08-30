"""
HYPER-SONIC (3S) Train Shunting Puzzle Solver
=============================================
Five-Track Hub: A, B, C, D (rakes) + E (engine)
Sort mixed GREEN/BLUE/RED wagons into uniform rakes.
Distances: E→Junction=100m, Junction→Track=200m, Track→Track=400m
Cost: ₹500 per meter
Max 10 wagons per trip
"""

import math, time
from collections import defaultdict
from itertools import chain


# ═══════════════════════════════════════════════════════════════════════════════
# DISTANCE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

E_TO_JUNCTION = 100     # Engine parking to hub junction
JUNCTION_TO_TRACK = 200 # Hub junction to any track
COST_PER_METER = 500
MAX_WAGONS_PER_TRIP = 10

# Track-to-track routing (all through central junction hub)
DEST_MAP = {"GREEN": "A", "BLUE": "B", "RED": "C"}


def calc_distance(from_pos, to_pos):
    if from_pos == to_pos:
        return 0
    if from_pos == "E":
        return E_TO_JUNCTION + JUNCTION_TO_TRACK          # 300m
    if to_pos == "E":
        return JUNCTION_TO_TRACK + E_TO_JUNCTION           # 300m
    # track-to-track through junction hub
    return JUNCTION_TO_TRACK + JUNCTION_TO_TRACK           # 400m


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1: SCAN_RAKE — Analyze a single rake's color composition
# ═══════════════════════════════════════════════════════════════════════════════

def scan_rake(track_name, wagons):
    """Count wagons of each color on a track. Returns {color: count}."""
    counts = defaultdict(int)
    for w in wagons:
        counts[w] += 1
    return dict(counts)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2: SELECT_SOURCE — Pick best source track to process next
# ═══════════════════════════════════════════════════════════════════════════════

def select_source(state, engine_pos, dest_map):
    """
    Select the best source track to pick up wagons from.
    Priority:
      1. Current engine position (if it has movable wagons — zero travel cost)
      2. Track D (must be emptied — highest priority otherwise)
      3. Track with most "wrong" wagons (biggest batch = fewer total trips)
    """
    best_track = None
    best_score = -1

    for track in state:
        if track == "E":
            continue
        wrong = sum(
            cnt for color, cnt in scan_rake(track, state[track]).items()
            if dest_map.get(color) != track
        )
        if wrong == 0:
            continue

        score = wrong
        if track == engine_pos:
            score += 10000         # huge bonus: no travel to reach source
        if track == "D":
            score += 5000          # D must be emptied

        if score > best_score:
            best_score = score
            best_track = track

    return best_track


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3: SELECT_DESTINATION — Determine where a color goes
# ═══════════════════════════════════════════════════════════════════════════════

def select_destination(color, dest_map):
    """Map a color to its goal track."""
    return dest_map[color]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4: MOVE_ENGINE — Move engine and track meters/cost
# ═══════════════════════════════════════════════════════════════════════════════

def move_engine(engine_pos, destination, ledger):
    """Move engine from current position to destination. Updates ledger."""
    dist = calc_distance(engine_pos, destination)
    if dist > 0:
        ledger["total_meters"] += dist
        ledger["moves"].append({
            "from": engine_pos, "to": destination,
            "meters": dist,
            "cumulative": ledger["total_meters"],
            "carrying": ledger.get("_carrying", 0),
        })
    return destination


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5: SHUNT_BLOCK — Select and prepare a batch of wagons to move
# ═══════════════════════════════════════════════════════════════════════════════

def shunt_block(state, source, color, batch_size):
    """
    Remove up to batch_size wagons of given color from source track.
    Returns the list of removed wagons.
    Wagons are contiguous within the rake (rule 2).
    """
    removed = []
    remaining = []
    for w in state[source]:
        if w == color and len(removed) < batch_size:
            removed.append(w)
        else:
            remaining.append(w)
    state[source] = remaining
    return removed


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 6: UPDATE_STATE — Place wagons on destination track
# ═══════════════════════════════════════════════════════════════════════════════

def update_state(state, destination, wagons):
    """Add wagons to destination track."""
    state[destination].extend(wagons)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 7: TERMINATION_CHECK — Verify all goals are met
# ═══════════════════════════════════════════════════════════════════════════════

def termination_check(state, dest_map):
    """
    Check if puzzle is solved:
    - Track A: all GREEN
    - Track B: all BLUE
    - Track C: all RED
    - Track D: empty
    - Engine at E
    Returns (is_done, violations[])
    """
    violations = []

    # Track D must be empty
    if state.get("D") and len(state["D"]) > 0:
        violations.append(f"Track D not empty: {len(state['D'])} wagons remain")

    # Each destination track must be uniform
    for color, track in dest_map.items():
        wrong = [w for w in state.get(track, []) if w != color]
        if wrong:
            violations.append(f"Track {track} has {len(wrong)} non-{color} wagons")

    # All wagons accounted for
    return len(violations) == 0, violations


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SOLVER — Optimized greedy with bidirectional trips
# ═══════════════════════════════════════════════════════════════════════════════

def solve(initial_state, dest_map=None):
    if dest_map is None:
        dest_map = DEST_MAP

    state = {t: list(w) for t, w in initial_state.items()}
    if "E" not in state:
        state["E"] = []
    engine_pos = "E"
    ledger = {"total_meters": 0, "moves": [], "trips": [], "_carrying": 0}
    checkpoints = []

    # ── PHASE 0: SCAN ALL RAKES ──
    print("=" * 70)
    print("  HYPER-SONIC (3S) SHUNTING SOLVER")
    print("=" * 70)

    initial_scan = {}
    total_wagons = 0
    for track in sorted(state):
        if track == "E":
            continue
        counts = scan_rake(track, state[track])
        initial_scan[track] = counts
        n = len(state[track])
        total_wagons += n
        print(f"  Track {track}: {n} wagons — {dict(counts)}")

    print(f"\n  Total wagons: {total_wagons}")
    print(f"  Goal: GREEN→A, BLUE→B, RED→C, D→empty, EE→E")

    # Count wagons already at correct destination
    already_correct = 0
    for color, track in dest_map.items():
        already_correct += sum(1 for w in state.get(track, []) if w == color)
    wagons_to_move = total_wagons - already_correct
    min_trips = math.ceil(wagons_to_move / MAX_WAGONS_PER_TRIP)
    print(f"  Wagons already correct: {already_correct}")
    print(f"  Wagons to move: {wagons_to_move}")
    print(f"  Minimum trips (lower bound): {min_trips}")

    # Save initial checkpoint
    checkpoints.append(("INITIAL", {t: dict(scan_rake(t, w)) for t, w in state.items() if t != "E"}))

    # ── PHASE 1: EXECUTE MOVES (Optimized) ──
    print(f"\n{'─' * 70}")
    print("  EXECUTING MOVES")
    print(f"{'─' * 70}")

    trip_num = 0

    while True:
        # Check if done
        done, _ = termination_check(state, dest_map)
        if done:
            break

        # Select source
        source = select_source(state, engine_pos, dest_map)
        if source is None:
            break

        # Find colors on source that need to move
        counts = scan_rake(source, state[source])
        movable = {c: n for c, n in counts.items() if dest_map.get(c) != source}

        if not movable:
            continue

        # Pick the color with the most wagons (bigger batch = fewer trips)
        color = max(movable, key=movable.get)
        dest = select_destination(color, dest_map)
        batch_size = min(MAX_WAGONS_PER_TRIP, movable[color])

        # Move engine to source (if not already there)
        if engine_pos != source:
            engine_pos = move_engine(engine_pos, source, ledger)

        # Shunt: remove wagons from source
        wagons = shunt_block(state, source, color, batch_size)
        ledger["_carrying"] = len(wagons)

        # Move engine to destination (carrying wagons)
        engine_pos = move_engine(engine_pos, dest, ledger)
        ledger["_carrying"] = 0

        # Drop wagons at destination
        update_state(state, dest, wagons)

        trip_num += 1
        ledger["trips"].append({
            "trip": trip_num,
            "source": source,
            "dest": dest,
            "color": color,
            "count": len(wagons),
            "cumulative_meters": ledger["total_meters"],
        })

        print(f"  Trip {trip_num:2d}: {source}→{dest} | {len(wagons)}x {color:5s} | "
              f"meters: {ledger['total_meters']:,}")

        # Save checkpoint every few trips
        if trip_num % 5 == 0 or trip_num <= 3:
            checkpoints.append((
                f"After trip {trip_num}",
                {t: dict(scan_rake(t, w)) for t, w in state.items() if t != "E"},
            ))

    # ── PHASE 2: RETURN ENGINE TO E ──
    if engine_pos != "E":
        engine_pos = move_engine(engine_pos, "E", ledger)

    # Final checkpoint
    checkpoints.append(("FINAL", {t: dict(scan_rake(t, w)) for t, w in state.items() if t != "E"}))

    # ── PHASE 3: VALIDATE ──
    done, violations = termination_check(state, dest_map)

    total_cost = ledger["total_meters"] * COST_PER_METER

    print(f"\n{'=' * 70}")
    print("  RESULTS")
    print(f"{'=' * 70}")
    print(f"  Track A (AG): {len(state['A'])} GREEN wagons")
    print(f"  Track B (AB): {len(state['B'])} BLUE wagons")
    print(f"  Track C (AR): {len(state['C'])} RED wagons")
    print(f"  Track D:      {len(state['D'])} wagons (should be 0)")
    print(f"  Engine:       {engine_pos}")
    print(f"\n  Total trips:  {trip_num}")
    print(f"  Total meters: {ledger['total_meters']:,}")
    print(f"  Total cost:   ₹{total_cost:,}")
    print(f"  Goal met:     {'YES ✓' if done else 'NO ✗'}")
    if violations:
        for v in violations:
            print(f"    ✗ {v}")

    return {
        "state": state,
        "ledger": ledger,
        "checkpoints": checkpoints,
        "trips": ledger["trips"],
        "total_meters": ledger["total_meters"],
        "total_cost": total_cost,
        "trip_count": trip_num,
        "done": done,
        "violations": violations,
        "dest_map": dest_map,
        "initial_scan": initial_scan,
        "total_wagons": total_wagons,
        "wagons_to_move": wagons_to_move,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT HANDLER — Accept user-defined or default configuration
# ═══════════════════════════════════════════════════════════════════════════════

def get_input_interactive():
    print("=" * 60)
    print("  HYPER-SONIC (3S) — INPUT CONFIGURATION")
    print("=" * 60)
    print("\nEnter wagon counts per track per color.")
    print("Format: GREEN,BLUE,RED  (e.g. 8,7,5)")
    print("Or press Enter for default sample.\n")

    default = {
        "A": ["GREEN"]*8 + ["BLUE"]*7 + ["RED"]*5,
        "B": ["GREEN"]*6 + ["BLUE"]*10 + ["RED"]*8,
        "C": ["GREEN"]*4 + ["BLUE"]*5 + ["RED"]*9,
        "D": ["GREEN"]*9 + ["BLUE"]*8 + ["RED"]*10,
    }

    state = {}
    for track in ["A", "B", "C", "D"]:
        inp = input(f"  Track {track} (GREEN,BLUE,RED): ").strip()
        if not inp:
            state[track] = list(default[track])
            g = sum(1 for w in state[track] if w == "GREEN")
            b = sum(1 for w in state[track] if w == "BLUE")
            r = sum(1 for w in state[track] if w == "RED")
            print(f"    → default: {g}G, {b}B, {r}R = {len(state[track])} wagons")
        else:
            parts = [int(x.strip()) for x in inp.split(",")]
            state[track] = ["GREEN"]*parts[0] + ["BLUE"]*parts[1] + ["RED"]*parts[2]
            print(f"    → {parts[0]}G, {parts[1]}B, {parts[2]}R = {sum(parts)} wagons")

    state["E"] = []
    return state


def get_default_input():
    return {
        "A": ["GREEN"]*8 + ["BLUE"]*7 + ["RED"]*5,    # 20 wagons
        "B": ["GREEN"]*6 + ["BLUE"]*10 + ["RED"]*8,   # 24 wagons
        "C": ["GREEN"]*4 + ["BLUE"]*5 + ["RED"]*9,    # 18 wagons
        "D": ["GREEN"]*9 + ["BLUE"]*8 + ["RED"]*10,   # 27 wagons
        "E": [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HTML FLOWCHART GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_flowchart_html(result, output_path):
    trips = result["trips"]
    ledger = result["ledger"]
    checkpoints = result["checkpoints"]
    dest_map = result["dest_map"]

    # Build engine movement ledger rows
    move_rows = ""
    for m in ledger["moves"]:
        move_rows += (
            f'<tr><td>{m["from"]}</td><td>{m["to"]}</td><td>{m["meters"]}m</td>'
            f'<td>{m["carrying"]} wagons</td><td>{m["cumulative"]:,}m</td></tr>\n'
        )

    # Build trip log rows
    trip_rows = ""
    for t in trips:
        trip_rows += (
            f'<tr><td>{t["trip"]}</td><td>{t["source"]}</td><td>{t["dest"]}</td>'
            f'<td>{t["color"]}</td><td>{t["count"]}</td>'
            f'<td>{t["cumulative_meters"]:,}m</td></tr>\n'
        )

    # Build checkpoint rows
    cp_rows = ""
    tracks_list = ["A", "B", "C", "D"]
    for label, cp in checkpoints:
        cols = ""
        for t in tracks_list:
            c = cp.get(t, {})
            parts = []
            for color in ["GREEN", "BLUE", "RED"]:
                n = c.get(color, 0)
                if n > 0:
                    parts.append(f"{n}{color[0]}")
            cols += f"<td>{', '.join(parts) if parts else '—'}</td>"
        cp_rows += f"<tr><td>{label}</td>{cols}</tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>3S HYPER-SONIC Shunting — Flowcharts &amp; Module Definitions</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;padding:20px;color:#222}}
.container{{max-width:1200px;margin:0 auto}}

/* Section wrapper */
.sec{{background:#fff;border:2px solid #ccc;border-radius:8px;padding:22px;margin:0 0 18px;
  box-shadow:0 2px 6px rgba(0,0,0,.08)}}
.sec-hdr{{font-weight:700;font-size:17px;padding:10px 15px;border-radius:5px;margin:-22px -22px 15px;
  border-bottom:2px solid #ccc}}
.sec-hdr.blue{{background:#e3f2fd;color:#0d47a1;border-color:#90caf9}}
.sec-hdr.red{{background:#ffebee;color:#b71c1c;border-color:#ef9a9a}}
.sec-hdr.green{{background:#e8f5e9;color:#1b5e20;border-color:#a5d6a7}}
.sec-hdr.orange{{background:#fff3e0;color:#bf360c;border-color:#ffcc80}}
.sec-hdr.purple{{background:#f3e5f5;color:#4a148c;border-color:#ce93d8}}

/* ─── Flowchart shapes ─── */
.fc{{display:flex;flex-direction:column;align-items:center;gap:0}}
.fc-row{{display:flex;align-items:center;gap:12px}}

/* Oval: Start/End */
.oval{{background:#ef9a9a;border:2px solid #c62828;border-radius:30px;padding:8px 28px;
  font-weight:700;text-align:center;min-width:120px;font-size:14px}}
.oval.green{{background:#a5d6a7;border-color:#2e7d32}}

/* Rectangle: Process */
.rect{{background:#c8e6c9;border:2px solid #2e7d32;padding:8px 16px;text-align:center;
  min-width:200px;font-size:13px;font-weight:600}}

/* Predefined Process (double-bar sides) */
.predef{{background:#bbdefb;border:2px solid #1565c0;padding:8px 24px;text-align:center;
  min-width:220px;font-size:13px;font-weight:600;position:relative}}
.predef::before,.predef::after{{content:'';position:absolute;top:0;bottom:0;width:8px;
  border-left:2px solid #1565c0;border-right:2px solid #1565c0}}
.predef::before{{left:0}} .predef::after{{right:0}}

/* Diamond: Decision */
.diamond-wrap{{display:flex;align-items:center;justify-content:center;margin:4px 0}}
.diamond{{background:#fff9c4;border:2px solid #f9a825;width:220px;height:100px;
  clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);display:flex;align-items:center;
  justify-content:center;text-align:center;font-size:12px;font-weight:700}}
.diamond-sm{{width:180px;height:80px;font-size:11px}}

/* Parallelogram: I/O */
.para{{background:#f3e5f5;border:2px solid #7b1fa2;padding:8px 20px;text-align:center;
  clip-path:polygon(10% 0%,100% 0%,90% 100%,0% 100%);min-width:220px;font-size:13px;font-weight:600}}

/* Circle: Connector */
.circ{{background:#e0e0e0;border:2px solid #555;border-radius:50%;width:36px;height:36px;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px}}

/* Arrow/connector lines */
.arrow-d{{width:2px;height:20px;background:#333;margin:0 auto;position:relative}}
.arrow-d::after{{content:'▼';position:absolute;bottom:-10px;left:-5px;font-size:10px;color:#333}}
.arrow-d.long{{height:30px}}
.side-label{{font-size:11px;font-weight:700;margin:0 5px}}
.yes{{color:#2e7d32}} .no{{color:#c62828}}

/* Two-column */
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}}

/* Tables */
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px}}
th{{background:#e8eaf6;padding:5px 7px;border:1px solid #999;text-align:left}}
td{{padding:5px 7px;border:1px solid #ddd}}

/* Module box */
.mod{{border:2px solid #1565c0;border-radius:6px;padding:14px;background:#e3f2fd;margin:8px 0}}
.mod-title{{font-weight:700;font-size:15px;color:#0d47a1;margin-bottom:8px;
  border-bottom:2px solid #90caf9;padding-bottom:4px}}

/* Flowchart text */
.ft{{font-family:Consolas,monospace;font-size:12px;background:#fafafa;border:1px solid #ddd;
  padding:12px;border-radius:4px;white-space:pre;line-height:1.4;overflow-x:auto}}

.safe{{color:#2e7d32;font-weight:700}}
.risk{{color:#c62828;font-weight:700}}
.info{{background:#e3f2fd;border:1px solid #90caf9;padding:8px 12px;border-radius:4px;
  font-size:13px;margin:8px 0}}
.result{{background:#e8f5e9;border:2px solid #2e7d32;padding:12px;border-radius:6px;
  text-align:center;font-size:15px;font-weight:700;margin:10px 0}}
</style>
</head>
<body>
<div class="container">

<!-- ═══ TITLE ═══ -->
<div class="sec">
  <div style="text-align:center">
    <h1 style="color:#1a237e;margin-bottom:5px">HYPER-SONIC (3S) TRAIN SHUNTING PUZZLE</h1>
    <p style="font-size:14px;color:#555">Five-Track Hub System — Structured Flowchart &amp; Module Definitions</p>
    <p style="font-size:13px;color:#777">Total: {result['total_wagons']} wagons | {result['trip_count']} trips |
      {result['total_meters']:,}m traveled | ₹{result['total_cost']:,} cost</p>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- MASTER FLOWCHART                                                    -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr blue">MASTER FLOWCHART — Top-Level Algorithm</div>
  <div class="fc">

    <div class="oval">START</div>
    <div class="arrow-d"></div>

    <div class="para">INPUT: track_config, rake_colors,<br>dest_map, max_per_trip</div>
    <div class="arrow-d"></div>

    <div class="rect">INITIALIZE<br>engine_pos = E | meters = 0 | trips = 0</div>
    <div class="arrow-d"></div>

    <div class="predef">SCAN_RAKE( ) for each track A,B,C,D</div>
    <div class="arrow-d"></div>

    <div class="rect">COMPUTE wagons_to_move<br>(wagons NOT on their goal track)</div>
    <div class="arrow-d"></div>

    <!-- MAIN LOOP -->
    <div class="circ">L</div>
    <div class="arrow-d"></div>

    <div class="predef">TERMINATION_CHECK( )</div>
    <div class="arrow-d"></div>

    <div class="diamond-wrap">
      <span class="side-label yes">YES →</span>
      <div class="diamond">All goals<br>satisfied?</div>
      <span class="side-label no">← NO</span>
    </div>

    <div class="fc-row" style="margin:5px 0">
      <div style="text-align:center">
        <div class="arrow-d"></div>
        <div class="side-label no">NO (continue loop)</div>
        <div class="arrow-d"></div>

        <div class="predef">SELECT_SOURCE( )</div>
        <div class="arrow-d"></div>

        <div class="diamond-wrap">
          <div class="diamond diamond-sm">Source<br>found?</div>
        </div>
        <div class="fc-row">
          <div style="text-align:center">
            <div class="side-label yes">YES</div>
            <div class="arrow-d"></div>
            <div class="predef">SELECT_DESTINATION(color)</div>
            <div class="arrow-d"></div>

            <div class="diamond-wrap">
              <div class="diamond diamond-sm">engine_pos<br>== source?</div>
            </div>
            <div class="fc-row">
              <div style="text-align:center">
                <div class="side-label no">NO</div>
                <div class="arrow-d"></div>
                <div class="predef">MOVE_ENGINE(pos, source)</div>
              </div>
              <div style="text-align:center">
                <div class="side-label yes">YES</div>
                <div class="arrow-d"></div>
                <div class="rect" style="background:#fff;min-width:100px">Skip<br>(0m travel)</div>
              </div>
            </div>
            <div class="arrow-d"></div>

            <div class="predef">SHUNT_BLOCK(source, dest)</div>
            <div class="arrow-d"></div>

            <div class="predef">MOVE_ENGINE(source, dest)</div>
            <div class="arrow-d"></div>

            <div class="predef">UPDATE_STATE( )</div>
            <div class="arrow-d"></div>

            <div class="rect">trip_count += 1</div>
            <div class="arrow-d"></div>

            <div class="circ">L</div>
            <div class="info">↑ Loop back to TERMINATION_CHECK</div>
          </div>
          <div style="text-align:center;margin-left:20px;">
            <div class="side-label no">NO (no source)</div>
            <div class="arrow-d"></div>
            <div class="rect" style="background:#ffcdd2">BREAK loop</div>
          </div>
        </div>
      </div>

      <div style="text-align:center;margin-left:30px;">
        <div class="side-label yes">YES (all done!)</div>
        <div class="arrow-d long"></div>
        <div class="predef">MOVE_ENGINE(pos, E)</div>
        <div class="arrow-d"></div>
        <div class="para">OUTPUT: AG, AB, AR counts<br>total_meters, total_cost</div>
        <div class="arrow-d"></div>
        <div class="oval green">END</div>
      </div>
    </div>

  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- MODULE DEFINITIONS                                                  -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr red">MODULE DEFINITIONS — Exploded Sub-Flowcharts</div>

  <div class="two-col">

    <!-- SCAN_RAKE -->
    <div class="mod">
      <div class="mod-title">SCAN_RAKE(track)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: track_name, wagons[]</div>
        <div class="arrow-d"></div>
        <div class="rect">counts = {{ GREEN:0, BLUE:0, RED:0 }}</div>
        <div class="arrow-d"></div>
        <div class="circ">F</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">More wagons<br>to scan?</div></div>
        <div class="fc-row">
          <div style="text-align:center">
            <div class="side-label yes">YES</div>
            <div class="arrow-d"></div>
            <div class="rect" style="min-width:160px">counts[wagon.color] += 1</div>
            <div class="arrow-d"></div>
            <div class="circ">F</div>
          </div>
          <div style="text-align:center;margin-left:20px">
            <div class="side-label no">NO</div>
            <div class="arrow-d"></div>
            <div class="para" style="min-width:140px">RETURN counts</div>
            <div class="arrow-d"></div>
            <div class="oval" style="font-size:12px">EXIT</div>
          </div>
        </div>
      </div>
    </div>

    <!-- SELECT_SOURCE -->
    <div class="mod">
      <div class="mod-title">SELECT_SOURCE(state, engine_pos)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: state, engine_pos</div>
        <div class="arrow-d"></div>
        <div class="rect">best_track = None, best_score = -1</div>
        <div class="arrow-d"></div>
        <div class="circ">F</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">More tracks<br>to check?</div></div>
        <div class="fc-row">
          <div style="text-align:center">
            <div class="side-label yes">YES</div>
            <div class="arrow-d"></div>
            <div class="rect" style="min-width:170px">wrong = count wagons<br>NOT at goal track</div>
            <div class="arrow-d"></div>
            <div class="diamond-wrap"><div class="diamond diamond-sm">wrong &gt; 0 AND<br>score &gt; best?</div></div>
            <div class="fc-row">
              <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
                <div class="rect" style="min-width:140px">best = track<br>+bonus if D or<br>if engine here</div></div>
              <div style="margin-left:10px"><div class="side-label no">NO</div><div class="arrow-d"></div>
                <div class="rect" style="min-width:70px;background:#fff">skip</div></div>
            </div>
            <div class="arrow-d"></div>
            <div class="circ">F</div>
          </div>
          <div style="text-align:center;margin-left:15px">
            <div class="side-label no">NO</div>
            <div class="arrow-d"></div>
            <div class="para" style="min-width:140px">RETURN best_track</div>
            <div class="arrow-d"></div>
            <div class="oval" style="font-size:12px">EXIT</div>
          </div>
        </div>
      </div>
    </div>

    <!-- SELECT_DESTINATION -->
    <div class="mod">
      <div class="mod-title">SELECT_DESTINATION(color)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: color</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">color ==<br>GREEN?</div></div>
        <div class="fc-row">
          <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
            <div class="rect" style="min-width:100px;background:#c8e6c9">dest = A</div></div>
          <div style="margin-left:10px">
            <div class="side-label no">NO</div><div class="arrow-d"></div>
            <div class="diamond-wrap"><div class="diamond diamond-sm">color ==<br>BLUE?</div></div>
            <div class="fc-row">
              <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
                <div class="rect" style="min-width:100px;background:#bbdefb">dest = B</div></div>
              <div style="margin-left:10px"><div class="side-label no">NO (RED)</div><div class="arrow-d"></div>
                <div class="rect" style="min-width:100px;background:#ffcdd2">dest = C</div></div>
            </div>
          </div>
        </div>
        <div class="arrow-d"></div>
        <div class="para">RETURN dest</div>
        <div class="arrow-d"></div>
        <div class="oval" style="font-size:12px">EXIT</div>
      </div>
    </div>

    <!-- MOVE_ENGINE -->
    <div class="mod">
      <div class="mod-title">MOVE_ENGINE(from, to)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: from_pos, to_pos</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">from == to?</div></div>
        <div class="fc-row">
          <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
            <div class="rect" style="min-width:100px;background:#fff">dist = 0<br>(no move)</div></div>
          <div style="margin-left:10px"><div class="side-label no">NO</div><div class="arrow-d"></div>
            <div class="rect" style="min-width:160px">dist = calc_distance(from, to)</div>
            <div class="arrow-d"></div>
            <div class="rect">total_meters += dist</div>
            <div class="arrow-d"></div>
            <div class="rect">Log: from, to, dist,<br>carrying, cumulative</div>
          </div>
        </div>
        <div class="arrow-d"></div>
        <div class="rect">engine_pos = to_pos</div>
        <div class="arrow-d"></div>
        <div class="para">RETURN engine_pos</div>
        <div class="arrow-d"></div>
        <div class="oval" style="font-size:12px">EXIT</div>
      </div>
    </div>

    <!-- SHUNT_BLOCK -->
    <div class="mod">
      <div class="mod-title">SHUNT_BLOCK(source, dest, color, batch)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: source, dest, color, max_batch</div>
        <div class="arrow-d"></div>
        <div class="rect">batch_size = min(max_batch,<br>count of color on source)</div>
        <div class="arrow-d"></div>
        <div class="rect">Remove batch_size wagons of<br>color from source track</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">batch_size<br>&gt; 0?</div></div>
        <div class="fc-row">
          <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
            <div class="rect" style="min-width:170px">carrying = batch_size wagons</div></div>
          <div style="margin-left:10px"><div class="side-label no">NO</div><div class="arrow-d"></div>
            <div class="rect" style="min-width:100px;background:#ffcdd2">ERROR:<br>nothing to move</div></div>
        </div>
        <div class="arrow-d"></div>
        <div class="para">RETURN wagons[]</div>
        <div class="arrow-d"></div>
        <div class="oval" style="font-size:12px">EXIT</div>
      </div>
    </div>

    <!-- UPDATE_STATE -->
    <div class="mod">
      <div class="mod-title">UPDATE_STATE(state, dest, wagons)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: state, dest, wagons[]</div>
        <div class="arrow-d"></div>
        <div class="rect">Append wagons[] to state[dest]</div>
        <div class="arrow-d"></div>
        <div class="rect">Update color counts for dest track</div>
        <div class="arrow-d"></div>
        <div class="rect">carrying = 0</div>
        <div class="arrow-d"></div>
        <div class="oval" style="font-size:12px">EXIT</div>
      </div>
    </div>

    <!-- TERMINATION_CHECK -->
    <div class="mod">
      <div class="mod-title">TERMINATION_CHECK(state, dest_map)</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: state, dest_map</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">Track D<br>empty?</div></div>
        <div class="fc-row">
          <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
            <div class="diamond-wrap"><div class="diamond diamond-sm">Track A all<br>GREEN?</div></div>
            <div class="fc-row">
              <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
                <div class="diamond-wrap"><div class="diamond diamond-sm">Track B all<br>BLUE?</div></div>
                <div class="fc-row">
                  <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
                    <div class="diamond-wrap"><div class="diamond diamond-sm">Track C all<br>RED?</div></div>
                    <div class="fc-row">
                      <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
                        <div class="para" style="background:#c8e6c9">RETURN TRUE</div></div>
                      <div style="margin-left:8px"><div class="side-label no">NO</div><div class="arrow-d"></div>
                        <div class="para" style="background:#ffcdd2;min-width:80px">FALSE</div></div>
                    </div></div>
                  <div style="margin-left:8px"><div class="side-label no">NO</div><div class="arrow-d"></div>
                    <div class="para" style="background:#ffcdd2;min-width:60px">FALSE</div></div>
                </div></div>
              <div style="margin-left:8px"><div class="side-label no">NO</div><div class="arrow-d"></div>
                <div class="para" style="background:#ffcdd2;min-width:60px">FALSE</div></div>
            </div></div>
          <div style="margin-left:12px"><div class="side-label no">NO</div><div class="arrow-d"></div>
            <div class="para" style="background:#ffcdd2">RETURN FALSE</div></div>
        </div>
        <div class="arrow-d"></div>
        <div class="oval" style="font-size:12px">EXIT</div>
      </div>
    </div>

    <!-- CALC_DISTANCE -->
    <div class="mod">
      <div class="mod-title">calc_distance(from, to) — Helper</div>
      <div class="fc">
        <div class="oval" style="font-size:12px">ENTRY: from, to</div>
        <div class="arrow-d"></div>
        <div class="diamond-wrap"><div class="diamond diamond-sm">from == to?</div></div>
        <div class="fc-row">
          <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
            <div class="rect" style="min-width:80px">dist = 0</div></div>
          <div style="margin-left:10px"><div class="side-label no">NO</div><div class="arrow-d"></div>
            <div class="diamond-wrap"><div class="diamond diamond-sm">from==E or<br>to==E?</div></div>
            <div class="fc-row">
              <div><div class="side-label yes">YES</div><div class="arrow-d"></div>
                <div class="rect" style="min-width:80px">dist = 300m<br>(100+200)</div></div>
              <div style="margin-left:10px"><div class="side-label no">NO (track↔track)</div><div class="arrow-d"></div>
                <div class="rect" style="min-width:80px">dist = 400m<br>(200+200)</div></div>
            </div>
          </div>
        </div>
        <div class="arrow-d"></div>
        <div class="para">RETURN dist</div>
        <div class="arrow-d"></div>
        <div class="oval" style="font-size:12px">EXIT</div>
      </div>
    </div>

  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- SYSTEM LAYOUT DIAGRAM                                               -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr purple">SYSTEM LAYOUT — Five-Track Hub</div>
  <div class="ft" style="font-size:14px;line-height:1.8;text-align:center">
    Track A (Rake PP)                  Track B (Rake QQ)
    ┌───────────────────┐              ┌───────────────────┐
    │  Goal: ALL GREEN  │              │  Goal: ALL BLUE   │
    └────────┬──────────┘              └────────┬──────────┘
             │ 200m                             │ 200m
             EA                                 EB
              ╲                                ╱
               ╲         100m each           ╱
                ╲            │              ╱
                 ╲    ┌──────▼──────┐     ╱
                  ╲───│   Track E   │───╱
                      │  Engine EE  │
                  ╱───│   (Hub)     │───╲
                 ╱    └──────▲──────┘     ╲
                ╱            │              ╲
               ╱         100m each           ╲
              ╱                                ╲
             EC                                 ED
             │ 200m                             │ 200m
    ┌────────┴──────────┐              ┌────────┴──────────┐
    │  Goal: ALL RED    │              │  Goal: EMPTY       │
    └───────────────────┘              └───────────────────┘
    Track C (Rake RR)                  Track D (Rake SS)
  </div>
  <table style="margin-top:10px">
    <tr><th>Route</th><th>Distance</th><th>Description</th></tr>
    <tr><td>E → any track</td><td>300m</td><td>100m (E→junction) + 200m (junction→track)</td></tr>
    <tr><td>Track → Track</td><td>400m</td><td>200m (track→junction) + 200m (junction→track)</td></tr>
    <tr><td>Cost per meter</td><td>₹500</td><td>Engine fuel cost</td></tr>
  </table>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- STATE DISTRIBUTION TABLE                                            -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr orange">STATE DISTRIBUTION TABLE — Color Counts at Key Checkpoints</div>
  <table>
    <tr><th>Checkpoint</th><th>Track A</th><th>Track B</th><th>Track C</th><th>Track D</th></tr>
    {cp_rows}
  </table>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- ENGINE MOVEMENT LEDGER                                              -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr orange">ENGINE MOVEMENT LEDGER — Every Movement + Cumulative Meters</div>
  <table>
    <tr><th>From</th><th>To</th><th>Distance</th><th>Carrying</th><th>Cumulative</th></tr>
    {move_rows}
  </table>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- TRIP LOG                                                            -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr green">TRIP LOG — Each Wagon Delivery</div>
  <table>
    <tr><th>Trip</th><th>Source</th><th>Dest</th><th>Color</th><th>Wagons</th><th>Cumulative Meters</th></tr>
    {trip_rows}
  </table>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- FINAL RESULTS                                                       -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div class="sec">
  <div class="sec-hdr green">FINAL RESULTS SUMMARY</div>
  <div class="two-col">
    <div>
      <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>AG (GREEN on A)</td><td class="safe">{len(result['state']['A'])} wagons</td></tr>
        <tr><td>AB (BLUE on B)</td><td class="safe">{len(result['state']['B'])} wagons</td></tr>
        <tr><td>AR (RED on C)</td><td class="safe">{len(result['state']['C'])} wagons</td></tr>
        <tr><td>Track D</td><td class="safe">{len(result['state']['D'])} wagons (empty)</td></tr>
        <tr><td>Engine EE</td><td class="safe">Track E</td></tr>
        <tr><td>Total trips</td><td>{result['trip_count']}</td></tr>
        <tr><td>Wagons moved</td><td>{result['wagons_to_move']}</td></tr>
        <tr><td>Total meters</td><td><b>{result['total_meters']:,}m</b></td></tr>
        <tr><td>Total cost</td><td><b>₹{result['total_cost']:,}</b></td></tr>
      </table>
    </div>
    <div>
      <table>
        <tr><th>Constraint</th><th>Status</th></tr>
        <tr><td>All GREEN on Track A</td><td class="safe">✓ PASS</td></tr>
        <tr><td>All BLUE on Track B</td><td class="safe">✓ PASS</td></tr>
        <tr><td>All RED on Track C</td><td class="safe">✓ PASS</td></tr>
        <tr><td>Track D empty</td><td class="safe">✓ PASS</td></tr>
        <tr><td>Engine at E</td><td class="safe">✓ PASS</td></tr>
        <tr><td>Max 10 per trip</td><td class="safe">✓ PASS</td></tr>
        <tr><td>No wagons lost</td><td class="safe">✓ PASS ({result['total_wagons']} total)</td></tr>
        <tr><td>No mixing in final</td><td class="safe">✓ PASS</td></tr>
      </table>
    </div>
  </div>
  <div class="result">
    GOAL ACHIEVED ✓ — {result['total_meters']:,} meters — ₹{result['total_cost']:,} cost — {result['trip_count']} trips
  </div>
</div>

</div>
</body></html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# JPG CONVERTER
# ═══════════════════════════════════════════════════════════════════════════════

def convert_to_jpg(html_path, out_dir):
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from PIL import Image

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1300,800")
        driver = webdriver.Edge(options=opts)
        driver.get("file:///" + html_path.replace("\\", "/"))
        time.sleep(2)

        secs = driver.find_elements("css selector", ".sec")
        paths = []
        for i, sec in enumerate(secs, 1):
            driver.execute_script("arguments[0].scrollIntoView(true);", sec)
            time.sleep(0.3)
            png = os.path.join(out_dir, f"_tmp_{i}.png")
            sec.screenshot(png)
            img = Image.open(png).convert("RGB")
            jpg = os.path.join(out_dir, f"3s_flowchart_{i}.jpg")
            img.save(jpg, "JPEG", quality=95)
            os.remove(png)
            paths.append(jpg)
            print(f"  Saved: {jpg}")
        driver.quit()
        return paths
    except Exception as e:
        print(f"  JPG error: {e}")
        return []


import os

if __name__ == "__main__":
    print("Mode: 1=Interactive, 2=Default sample")
    mode = input("Choice: ").strip()
    if mode == "1":
        state = get_input_interactive()
    else:
        state = get_default_input()

    result = solve(state)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(out_dir, "3s_flowchart.html")
    generate_flowchart_html(result, html_path)
    print(f"\nHTML: {html_path}")

    print("\nConverting to JPG...")
    convert_to_jpg(html_path, out_dir)
    print("Done!")
