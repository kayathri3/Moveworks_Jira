"""
Dynamic Solver: BFS-based exploration of all valid states to find optimal solution.
Handles arbitrary initial/goal configurations and validates all constraints dynamically.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import time

# ─── CONFIGURATION (easily replaceable for different puzzles) ─────────────────

CONFIG = {
    "junctions": {
        ("A", "B"): 24, ("B", "A"): 24,
        ("B", "C"): float("inf"), ("C", "B"): float("inf"),
        ("C", "A"): 8, ("A", "C"): 8,
        ("B", "D"): 16, ("D", "B"): 16,
    },
    "stock_length": {"EE": 16, "XX": 8, "YY": 8, "ZZ": 8},
    "engine": "EE",
    "max_coupled": 2,
    "engine_min_space": 16,
    "max_wagons_track_d": 1,
    "initial": {"A": ["EE"], "B": ["XX"], "C": ["YY"], "D": ["ZZ"]},
    "goal": {"A": ["EE"], "B": ["ZZ"], "C": ["XX"], "D": ["YY"]},
    "tracks": ["A", "B", "C", "D"],
}


# ─── STATE REPRESENTATION ────────────────────────────────────────────────────

@dataclass(frozen=True)
class PuzzleState:
    """Hashable state for BFS exploration."""
    track_contents: tuple  # ((track, tuple(items)), ...)
    engine_track: str
    coupled: tuple          # wagons coupled to engine

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


# ─── VALIDATE_CAPACITY MODULE ────────────────────────────────────────────────

def validate_capacity(consist: list, from_track: str, to_track: str, config=CONFIG) -> bool:
    junction_key = (from_track, to_track)
    if junction_key not in config["junctions"]:
        return False
    capacity = config["junctions"][junction_key]
    total_length = sum(config["stock_length"][item] for item in consist)
    return total_length <= capacity


# ─── ACTION GENERATION ────────────────────────────────────────────────────────

def get_neighbors(node: SearchNode, config=CONFIG) -> list[SearchNode]:
    """Generate all valid next states from current state."""
    neighbors = []
    state = node.state
    tracks = state.get_tracks()
    engine_track = state.engine_track
    coupled = list(state.coupled)
    engine = config["engine"]
    wagons_on_track = [i for i in tracks.get(engine_track, []) if i != engine]

    # Action 1: COUPLE a wagon on current track
    if len(coupled) < config["max_coupled"]:
        for wagon in wagons_on_track:
            if wagon == engine:
                continue
            new_tracks = {k: list(v) for k, v in tracks.items()}
            new_tracks[engine_track].remove(wagon)
            new_coupled = sorted(coupled + [wagon])
            new_state = PuzzleState.from_dict(new_tracks, engine_track, new_coupled)
            neighbors.append(SearchNode(
                state=new_state,
                actions=node.actions + [f"COUPLE {wagon} on {engine_track}"],
                reversals=node.reversals,
                last_direction=node.last_direction,
            ))

    # Action 2: DECOUPLE a wagon on current track
    for wagon in coupled:
        new_tracks = {k: list(v) for k, v in tracks.items()}
        new_tracks[engine_track].append(wagon)
        new_coupled = [w for w in coupled if w != wagon]

        # Track D constraint
        non_engine = [i for i in new_tracks.get("D", []) if i != engine]
        if engine_track == "D" and len(non_engine) > config["max_wagons_track_d"]:
            continue

        new_state = PuzzleState.from_dict(new_tracks, engine_track, new_coupled)
        neighbors.append(SearchNode(
            state=new_state,
            actions=node.actions + [f"DECOUPLE {wagon} on {engine_track}"],
            reversals=node.reversals,
            last_direction=node.last_direction,
        ))

    # Action 3: MOVE engine (with coupled) to adjacent track
    consist = [engine] + coupled
    for (f, t), cap in config["junctions"].items():
        if f != engine_track:
            continue
        if not validate_capacity(consist, f, t, config):
            continue

        new_tracks = {k: list(v) for k, v in tracks.items()}
        if engine in new_tracks[f]:
            new_tracks[f].remove(engine)
        new_tracks[t].append(engine)

        # Track D constraint
        non_engine_on_t = [i for i in new_tracks[t] if i != engine] + coupled
        if t == "D" and len([w for w in non_engine_on_t if w != engine]) > config["max_wagons_track_d"]:
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
            actions=node.actions + [f"MOVE [{'+'.join(consist)}] {f}→{t}"],
            reversals=rev,
            last_direction=direction,
        ))

    # Action 4: FLY_SHUNT a coupled wagon to adjacent track
    for wagon in coupled:
        for (f, t), cap in config["junctions"].items():
            if f != engine_track:
                continue
            if not validate_capacity([wagon], f, t, config):
                continue

            # Track D constraint
            new_tracks = {k: list(v) for k, v in tracks.items()}
            new_tracks[t].append(wagon)
            non_engine_on_t = [i for i in new_tracks[t] if i != engine]
            if t == "D" and len(non_engine_on_t) > config["max_wagons_track_d"]:
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
                actions=node.actions + [f"FLY_SHUNT {wagon} {f}→{t} (engine stays {f})"],
                reversals=rev,
                last_direction=direction,
            ))

    return neighbors


# ─── GOAL CHECK ──────────────────────────────────────────────────────────────

def is_goal(state: PuzzleState, config=CONFIG) -> bool:
    tracks = state.get_tracks()
    if state.coupled:
        return False
    for track, expected in config["goal"].items():
        actual = sorted(tracks.get(track, []))
        if actual != sorted(expected):
            return False
    return True


# ─── BFS SOLVER ──────────────────────────────────────────────────────────────

def solve_bfs(config=CONFIG, max_depth=20) -> Optional[SearchNode]:
    """
    Breadth-first search for optimal solution (fewest actions).
    Returns the SearchNode with the solution path, or None if unsolvable.
    """
    initial_tracks = {k: list(v) for k, v in config["initial"].items()}
    for t in config["tracks"]:
        if t not in initial_tracks:
            initial_tracks[t] = []

    engine_track = None
    for t, items in initial_tracks.items():
        if config["engine"] in items:
            engine_track = t
            break

    initial_state = PuzzleState.from_dict(initial_tracks, engine_track, [])
    start_node = SearchNode(state=initial_state, actions=[], reversals=0)

    if is_goal(initial_state, config):
        return start_node

    visited = {initial_state}
    queue = deque([start_node])
    nodes_explored = 0

    print(f"Starting BFS search (max depth: {max_depth})...")
    start_time = time.time()

    while queue:
        node = queue.popleft()
        if len(node.actions) >= max_depth:
            continue

        nodes_explored += 1
        if nodes_explored % 1000 == 0:
            print(f"  Explored {nodes_explored} nodes, depth {len(node.actions)}...")

        for neighbor in get_neighbors(node, config):
            if neighbor.state in visited:
                continue
            visited.add(neighbor.state)

            if is_goal(neighbor.state, config):
                elapsed = time.time() - start_time
                print(f"  Solution found! Explored {nodes_explored} nodes in {elapsed:.2f}s")
                return neighbor

            queue.append(neighbor)

    print(f"  No solution found within depth {max_depth}. Explored {nodes_explored} nodes.")
    return None


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  DYNAMIC BFS SOLVER - 2S TRIANGULAR SHUNTING PUZZLE")
    print("=" * 70)
    print(f"\n  Initial: {CONFIG['initial']}")
    print(f"  Goal:    {CONFIG['goal']}")
    print()

    result = solve_bfs(CONFIG, max_depth=20)

    if result:
        print(f"\n{'=' * 70}")
        print(f"  OPTIMAL SOLUTION ({len(result.actions)} actions, {result.reversals} reversals)")
        print(f"{'=' * 70}")
        for i, action in enumerate(result.actions, 1):
            print(f"  {i:2d}. {action}")
        print(f"\n  Total actions: {len(result.actions)}")
        print(f"  Reversals: {result.reversals}")
    else:
        print("\n  No solution exists within search bounds.")


if __name__ == "__main__":
    main()
