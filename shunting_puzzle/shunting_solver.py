"""
2S Triangular Shunting Puzzle Solver
====================================
Tracks: A, B, C (triangle) + D (siding off B)
Junctions: AB(24m), BC(unlimited), CA(8m), BD(16m)

Rolling Stock: EE(16m), XX(8m), YY(8m), ZZ(8m)
Initial: A=EE, B=XX, C=YY, D=ZZ
Goal:    A=EE, B=ZZ, C=XX, D=YY

Junction capacity = max total length of coupled consist passing through.
Fly shunting allowed: engine pushes wagon, decouples before junction,
wagon rolls through alone (only wagon length counts against capacity).
"""

from dataclasses import dataclass, field
from typing import Optional
from copy import deepcopy

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

JUNCTION_CAPACITY = {
    ("A", "B"): 24, ("B", "A"): 24,
    ("B", "C"): float("inf"), ("C", "B"): float("inf"),
    ("C", "A"): 8, ("A", "C"): 8,
    ("B", "D"): 16, ("D", "B"): 16,
}

STOCK_LENGTH = {"EE": 16, "XX": 8, "YY": 8, "ZZ": 8}
MAX_COUPLED_WAGONS = 2
ENGINE = "EE"
ENGINE_MIN_SPACE = 16


# ─── STATE MODULE ─────────────────────────────────────────────────────────────

@dataclass
class State:
    """Immutable snapshot of puzzle state."""
    tracks: dict = field(default_factory=dict)       # track -> list of items
    junctions: dict = field(default_factory=dict)    # junction_key -> list of items
    engine_track: str = ""
    coupled: list = field(default_factory=list)      # wagons coupled to engine
    engine_direction: str = ""                       # last direction of travel
    reversal_count: int = 0
    move_count: int = 0

    def copy(self):
        s = State(
            tracks={k: list(v) for k, v in self.tracks.items()},
            junctions={k: list(v) for k, v in self.junctions.items()},
            engine_track=self.engine_track,
            coupled=list(self.coupled),
            engine_direction=self.engine_direction,
            reversal_count=self.reversal_count,
            move_count=self.move_count,
        )
        return s


def create_initial_state() -> State:
    return State(
        tracks={"A": ["EE"], "B": ["XX"], "C": ["YY"], "D": ["ZZ"]},
        junctions={},
        engine_track="A",
        coupled=[],
        engine_direction="",
        reversal_count=0,
        move_count=0,
    )


GOAL_STATE = {"A": ["EE"], "B": ["ZZ"], "C": ["XX"], "D": ["YY"]}


# ─── VALIDATE_CAPACITY MODULE ────────────────────────────────────────────────

def validate_capacity(consist: list, from_track: str, to_track: str) -> tuple[bool, str]:
    """
    Check if a consist can pass through the junction between two tracks.
    Returns (is_valid, reason).
    """
    junction_key = (from_track, to_track)
    if junction_key not in JUNCTION_CAPACITY:
        return False, f"No junction exists between {from_track} and {to_track}"

    capacity = JUNCTION_CAPACITY[junction_key]
    total_length = sum(STOCK_LENGTH[item] for item in consist)

    if total_length > capacity:
        return False, (
            f"Consist length {total_length}m exceeds "
            f"{from_track}-{to_track} junction capacity {capacity}m"
        )
    return True, "OK"


# ─── DEADLOCK_CHECK MODULE ────────────────────────────────────────────────────

def deadlock_check(state: State) -> tuple[bool, str]:
    """
    Detect if engine is in a deadlock (no valid moves possible).
    Returns (is_deadlocked, explanation).
    """
    engine_loc = state.engine_track
    possible_destinations = [
        t for (f, t) in JUNCTION_CAPACITY if f == engine_loc
    ]

    for dest in possible_destinations:
        consist = [ENGINE] + state.coupled
        valid, _ = validate_capacity(consist, engine_loc, dest)
        if valid:
            return False, f"Engine can move to {dest}"

        # Even alone?
        valid_alone, _ = validate_capacity([ENGINE], engine_loc, dest)
        if valid_alone:
            return False, f"Engine can move alone to {dest}"

    return True, f"Engine stuck on track {engine_loc} with no valid moves"


# ─── COUPLE / DECOUPLE MODULE ────────────────────────────────────────────────

def couple(state: State, wagon: str) -> tuple[State, bool, str]:
    """Couple a wagon to the engine. Both must be on the same track."""
    new_state = state.copy()

    if wagon in new_state.coupled:
        return state, False, f"{wagon} already coupled"

    if wagon not in new_state.tracks.get(new_state.engine_track, []):
        return state, False, f"{wagon} not on engine's track ({new_state.engine_track})"

    if len(new_state.coupled) >= MAX_COUPLED_WAGONS:
        return state, False, f"Max {MAX_COUPLED_WAGONS} wagons already coupled"

    new_state.coupled.append(wagon)
    new_state.tracks[new_state.engine_track].remove(wagon)
    return new_state, True, f"Coupled {wagon} to EE on track {new_state.engine_track}"


def decouple(state: State, wagon: str) -> tuple[State, bool, str]:
    """Decouple a wagon from the engine. Wagon stays on current track."""
    new_state = state.copy()

    if wagon not in new_state.coupled:
        return state, False, f"{wagon} not coupled to engine"

    new_state.coupled.remove(wagon)
    new_state.tracks[new_state.engine_track].append(wagon)
    return new_state, True, f"Decoupled {wagon} on track {new_state.engine_track}"


# ─── MOVE MODULE ─────────────────────────────────────────────────────────────

def move(state: State, to_track: str) -> tuple[State, bool, str]:
    """
    Move engine (with coupled wagons) from current track to destination.
    Validates junction capacity and updates state.
    """
    from_track = state.engine_track
    consist = [ENGINE] + state.coupled

    # Capacity validation
    valid, reason = validate_capacity(consist, from_track, to_track)
    if not valid:
        return state, False, reason

    new_state = state.copy()

    # Remove engine from current track
    if ENGINE in new_state.tracks[from_track]:
        new_state.tracks[from_track].remove(ENGINE)

    # Add engine and coupled wagons to destination
    new_state.tracks[to_track].append(ENGINE)
    new_state.engine_track = to_track

    # Track direction and reversals
    direction = f"{from_track}->{to_track}"
    if new_state.engine_direction and _is_reversal(new_state.engine_direction, direction):
        new_state.reversal_count += 1

    new_state.engine_direction = direction
    new_state.move_count += 1

    consist_str = "+".join(consist)
    return new_state, True, (
        f"MOVE [{consist_str}] {from_track}→{to_track} "
        f"(junction capacity: {JUNCTION_CAPACITY[(from_track, to_track)]}m, "
        f"consist: {sum(STOCK_LENGTH[i] for i in consist)}m)"
    )


def fly_shunt(state: State, wagon: str, to_track: str) -> tuple[State, bool, str]:
    """
    Fly shunt: engine pushes coupled wagon through junction, decouples before junction.
    Wagon rolls to destination alone. Engine stays on current track.
    Only wagon length counts against junction capacity.
    """
    from_track = state.engine_track

    if wagon not in state.coupled:
        return state, False, f"{wagon} not coupled to engine for fly shunt"

    # Validate wagon alone through junction
    valid, reason = validate_capacity([wagon], from_track, to_track)
    if not valid:
        return state, False, f"Fly shunt failed: {reason}"

    # Check Track D single-wagon constraint
    wagons_on_dest = [
        item for item in state.tracks.get(to_track, [])
        if item != ENGINE
    ]
    if to_track == "D" and len(wagons_on_dest) >= 1:
        return state, False, "Track D cannot store more than one wagon"

    new_state = state.copy()
    new_state.coupled.remove(wagon)
    new_state.tracks[to_track].append(wagon)
    new_state.move_count += 1

    # Fly shunt involves a push direction then staying - counts as half-reversal
    push_dir = f"{from_track}->{to_track}"
    if new_state.engine_direction and _is_reversal(new_state.engine_direction, push_dir):
        new_state.reversal_count += 1
    new_state.engine_direction = push_dir

    return new_state, True, (
        f"FLY_SHUNT {wagon}({STOCK_LENGTH[wagon]}m) {from_track}→{to_track} "
        f"(junction capacity: {JUNCTION_CAPACITY[(from_track, to_track)]}m). "
        f"Engine stays on {from_track}."
    )


def _is_reversal(prev_direction: str, new_direction: str) -> bool:
    """Determine if direction change constitutes a reversal."""
    if not prev_direction:
        return False
    prev_parts = prev_direction.split("->")
    new_parts = new_direction.split("->")
    # Reversal if new direction is exact opposite of previous
    return prev_parts[0] == new_parts[1] and prev_parts[1] == new_parts[0]


# ─── STATE_UPDATE MODULE ─────────────────────────────────────────────────────

def state_update(state: State, action_fn, *args) -> tuple[State, bool, str]:
    """
    Generic state update wrapper. Applies action, performs deadlock check.
    Single entry, single exit.
    """
    new_state, success, message = action_fn(state, *args)
    if not success:
        return state, False, f"FAILED: {message}"

    # Deadlock check after every state change
    is_deadlocked, dl_reason = deadlock_check(new_state)
    if is_deadlocked:
        return state, False, f"DEADLOCK DETECTED: {dl_reason}. Rolling back."

    return new_state, True, message


# ─── TERMINATION_CHECK MODULE ────────────────────────────────────────────────

def termination_check(state: State) -> tuple[bool, list]:
    """
    Verify if current state matches goal state.
    Returns (is_complete, list_of_violations).
    """
    violations = []

    for track, expected_items in GOAL_STATE.items():
        actual = [
            item for item in state.tracks.get(track, [])
            if item not in state.coupled
        ]
        for item in expected_items:
            if item not in actual:
                violations.append(f"{item} should be on track {track}, found elsewhere")

    # Engine must not be coupled with anything
    if state.coupled:
        violations.append(f"Engine still coupled with: {state.coupled}")

    return len(violations) == 0, violations


# ─── SOLUTION EXECUTION ──────────────────────────────────────────────────────

def solve():
    """Execute the optimized 8-move solution with full validation."""
    state = create_initial_state()
    steps = []

    def execute(action_fn, *args, description=""):
        nonlocal state
        state, success, msg = state_update(state, action_fn, *args)
        step_info = {
            "step": len(steps) + 1,
            "action": description or msg,
            "result": msg,
            "success": success,
            "state_snapshot": {
                k: list(v) for k, v in state.tracks.items()
            },
            "coupled": list(state.coupled),
            "engine_track": state.engine_track,
            "reversals": state.reversal_count,
            "moves": state.move_count,
        }
        steps.append(step_info)
        if not success:
            raise RuntimeError(f"Step {len(steps)} failed: {msg}")
        return state

    print("=" * 70)
    print("  2S TRIANGULAR SHUNTING PUZZLE - OPTIMIZED SOLUTION")
    print("=" * 70)
    print(f"\nINITIAL STATE:")
    print(f"  Track A: {state.tracks['A']}")
    print(f"  Track B: {state.tracks['B']}")
    print(f"  Track C: {state.tracks['C']}")
    print(f"  Track D: {state.tracks['D']}")
    print(f"\nGOAL: A=EE, B=ZZ, C=XX, D=YY")
    print("-" * 70)

    # ─── PHASE 1: Move XX from B to C ────────────────────────────────────
    print("\n▶ PHASE 1: Deliver XX to Track C")

    execute(move, "B", description="Move EE from A to B (via AB junction)")
    execute(couple, "XX", description="Couple XX to EE on Track B")
    execute(move, "C", description="Move [EE+XX] from B to C (via BC junction)")
    execute(decouple, "XX", description="Decouple XX on Track C (XX at goal!)")

    # ─── PHASE 2: Bring YY to staging area (Track B) ─────────────────────
    print("\n▶ PHASE 2: Stage YY on Track B for D delivery")

    execute(couple, "YY", description="Couple YY to EE on Track C")
    execute(move, "B", description="Move [EE+YY] from C to B (via BC junction)")
    execute(decouple, "YY", description="Decouple YY on Track B")

    # ─── PHASE 3: Extract ZZ from Track D ────────────────────────────────
    print("\n▶ PHASE 3: Extract ZZ from Track D to Track B")

    execute(move, "D", description="Move EE alone from B to D (via BD junction)")
    execute(couple, "ZZ", description="Couple ZZ to EE on Track D")
    execute(fly_shunt, "ZZ", "B",
            description="Fly-shunt ZZ from D to B (ZZ rolls through BD junction alone)")
    execute(move, "B", description="Move EE alone from D to B (via BD junction)")

    # ─── PHASE 4: Deliver YY to Track D ──────────────────────────────────
    print("\n▶ PHASE 4: Deliver YY to Track D")

    execute(couple, "YY", description="Couple YY to EE on Track B")
    execute(fly_shunt, "YY", "D",
            description="Fly-shunt YY from B to D (YY rolls through BD junction alone)")

    # ─── PHASE 5: Return engine to Track A ───────────────────────────────
    print("\n▶ PHASE 5: Return EE to Track A")

    execute(move, "A", description="Move EE from B to A (via AB junction)")

    # ─── FINAL VALIDATION ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  FINAL STATE VALIDATION")
    print("=" * 70)

    is_complete, violations = termination_check(state)

    print(f"\n  Track A: {state.tracks['A']}")
    print(f"  Track B: {state.tracks['B']}")
    print(f"  Track C: {state.tracks['C']}")
    print(f"  Track D: {state.tracks['D']}")
    print(f"\n  Total moves: {state.move_count}")
    print(f"  Total reversals: {state.reversal_count}")
    print(f"  Coupled wagons remaining: {state.coupled}")
    print(f"  Goal achieved: {'YES ✓' if is_complete else 'NO ✗'}")

    if violations:
        print(f"  Violations: {violations}")

    # Print step-by-step log
    print("\n" + "=" * 70)
    print("  STEP-BY-STEP EXECUTION LOG")
    print("=" * 70)
    for step in steps:
        status = "✓" if step["success"] else "✗"
        print(f"\n  Step {step['step']:2d} [{status}]: {step['action']}")
        print(f"           State: A={step['state_snapshot']['A']}, "
              f"B={step['state_snapshot']['B']}, "
              f"C={step['state_snapshot']['C']}, "
              f"D={step['state_snapshot']['D']}")
        if step["coupled"]:
            print(f"           Coupled: {step['coupled']}")
        print(f"           Engine on: Track {step['engine_track']} | "
              f"Moves: {step['moves']} | Reversals: {step['reversals']}")

    return state, steps


if __name__ == "__main__":
    solve()
