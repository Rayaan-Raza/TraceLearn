#!/usr/bin/env python3
"""CPG parser + feature extraction (master plan §9.3 R3, R-I6).

Reads PROGpedia's shipped Code Property Graph and computes the `cpg` feature
block the extractor consumes. Format is pinned by `progpedia (1)/data.md`:

- `*.dsc.csv` nodes: id, type, token, location, code
- `*.cpg.csv` edges: source_id, target_id, type (AST/EOG/DFG), index, branch, name

Structural features (counts, depth) are exact. The four pg-rule detectors and
the two class-8/10 candidate detectors are *conservative* — each is only one of
the two independent signals a pg conjunction requires (the compiler warning is
the other), so precision is protected by the conjunction, not the detector
alone. A detector that cannot decide drops the case (never guesses, §9.3 R3).

R3 milestone: >=95% parse rate on real data; failures return None and are
logged by the caller, never guessed.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

COMPARISONS = frozenset({"<", ">", "<=", ">=", "==", "!="})
ASSIGN_OPS = frozenset({"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="})
UPDATE_OPS = frozenset({"++", "--"})

LOOP_TYPES = frozenset({"FORSTATEMENT", "WHILESTATEMENT", "FOREACHSTATEMENT", "DOSTATEMENT"})
CONTROL_TYPES = frozenset({"IFSTATEMENT", "WHILESTATEMENT", "DOSTATEMENT",
                           "FORSTATEMENT", "FOREACHSTATEMENT", "CONDITIONALEXPRESSION"})
# Node types that are statements (never the *condition* of a control node).
STATEMENT_TYPES = frozenset({
    "COMPOUNDSTATEMENT", "IFSTATEMENT", "FORSTATEMENT", "WHILESTATEMENT",
    "DOSTATEMENT", "FOREACHSTATEMENT", "RETURNSTATEMENT", "BREAKSTATEMENT",
    "CONTINUESTATEMENT", "DECLARATIONSTATEMENT", "SWITCHSTATEMENT",
    "TRYSTATEMENT", "CASESTATEMENT", "LABELSTATEMENT", "SYNCHRONIZEDSTATEMENT",
    "EMPTYSTATEMENT", "STATEMENT", "GOTOSTATEMENT",
})
FUNCTION_TYPES = frozenset({"FUNCTIONDECLARATION", "METHODDECLARATION", "CONSTRUCTORDECLARATION"})
CALL_TYPES = frozenset({"CALLEXPRESSION", "MEMBERCALLEXPRESSION", "STATICCALLEXPRESSION"})
OUTPUT_TOKENS = frozenset({"printf", "puts", "print", "println", "cout",
                           "System.out.print", "System.out.println", "fprintf", "write"})

_DECL_SIZE_RE = re.compile(r"\b(\w+)\s*\[\s*(\d+)\s*\]")
_DECL_MACRO_RE = re.compile(r"\b(\w+)\s*\[\s*([A-Za-z_]\w*)\s*\]")
_DEFINE_RE = re.compile(r"#\s*define\s+([A-Za-z_]\w*)\s+(\d+)\b")


@dataclass
class CPGNode:
    id: str
    type: str
    token: str = ""
    location: str = ""
    code: str = ""


@dataclass
class CPGGraph:
    nodes: dict[str, CPGNode] = field(default_factory=dict)
    # AST adjacency, both directions — the detectors traverse the AST only.
    ast_children: dict[str, list[str]] = field(default_factory=dict)
    ast_parent: dict[str, str] = field(default_factory=dict)
    # `#define NAME NUM` constants read from the sibling C/C++ source, used to
    # resolve fixed array sizes declared via macros (`int v[MAX]`).
    macros: dict[str, int] = field(default_factory=dict)
    _edge_count: int = 0

    def add_node(self, nid: str, ntype: str, token: str = "", location: str = "", code: str = "") -> None:
        self.nodes[nid] = CPGNode(id=nid, type=ntype, token=token, location=location, code=code)

    def add_edge(self, src: str, dst: str, etype: str, branch: str = "", name: str = "") -> None:
        self._edge_count += 1
        if etype == "AST":
            self.ast_children.setdefault(src, []).append(dst)
            # A node may have several AST parents in this CPG (e.g. a call site
            # is linked to both its syntactic parent and its callee declaration).
            # Keep the first as the "syntactic" parent for upward walks.
            self.ast_parent.setdefault(dst, src)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def ast(self, nid: str) -> list[CPGNode]:
        return [self.nodes[c] for c in self.ast_children.get(nid, []) if c in self.nodes]


def _subtree(graph: CPGGraph, roots: Iterable[str]) -> set[str]:
    """All node ids reachable from `roots` via AST edges (inclusive, cycle-safe)."""
    seen: set[str] = set()
    stack = [r for r in roots if r in graph.nodes]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        stack.extend(graph.ast_children.get(nid, []))
    return seen


# ------------------------------------------------------------------ parsing


def parse_graph_text(dsc_text: str, cpg_text: str) -> CPGGraph:
    """Parse dsc nodes + cpg edges into a CPGGraph. Malformed rows are dropped."""
    graph = CPGGraph()
    for row in csv.DictReader(io.StringIO(dsc_text)):
        nid = (row.get("id") or "").strip()
        ntype = (row.get("type") or "").strip()
        if not nid or not ntype or not nid.lstrip("-").isdigit():
            continue  # data.md pins id as Integer — malformed row, drop it
        graph.add_node(
            nid, ntype,
            (row.get("token") or "").strip(),
            (row.get("location") or "").strip(),
            row.get("code") or "",
        )
    for row in csv.DictReader(io.StringIO(cpg_text)):
        src = (row.get("source_id") or "").strip()
        dst = (row.get("target_id") or "").strip()
        etype = (row.get("type") or "").strip()
        if src not in graph.nodes or dst not in graph.nodes:
            continue  # drop dangling edges whose endpoints were not parsed
        graph.add_edge(src, dst, etype, (row.get("branch") or "").strip(),
                       (row.get("name") or "").strip())
    return graph


def parse_submission(cpg_path: Path, dsc_path: Path) -> CPGGraph | None:
    """Parse one submission's CPG. None on missing files or zero nodes (R3)."""
    if not dsc_path.is_file():
        return None
    try:
        dsc_text = dsc_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    cpg_text = ""
    if cpg_path.is_file():
        try:
            cpg_text = cpg_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            cpg_text = ""
    graph = parse_graph_text(dsc_text, cpg_text)
    if graph.node_count == 0:
        return None  # parse failure — caller logs and drops
    # read #define constants from the sibling C/C++ source (macro array sizes)
    for src in sorted(dsc_path.parent.iterdir()):
        if src.is_file() and src.suffix.lower() in (".c", ".cpp", ".cc", ".cxx"):
            try:
                src_text = src.read_text(encoding="utf-8", errors="replace")
            except OSError:
                break
            for m in _DEFINE_RE.finditer(src_text):
                graph.macros[m.group(1)] = int(m.group(2))
            break
    return graph


# ----------------------------------------------------------------- features


def _max_depth(graph: CPGGraph) -> int:
    """Longest AST chain (node count), memoized and cycle-safe."""
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(nid: str) -> int:
        if nid in memo:
            return memo[nid]
        if nid in visiting:
            return 0  # cycle guard
        visiting.add(nid)
        best = 1
        for child in graph.ast_children.get(nid, []):
            if child in graph.nodes:
                best = max(best, 1 + depth(child))
        visiting.discard(nid)
        memo[nid] = best
        return best

    if not graph.nodes:
        return 0
    return max(depth(nid) for nid in graph.nodes)


def _decl_sizes(graph: CPGGraph) -> dict[str, int]:
    """variable name -> literal declared size (`int a[3]`, `v[MAX]` via #define)."""
    sizes: dict[str, int] = {}
    for node in graph.nodes.values():
        if node.type != "VARIABLEDECLARATION":
            continue
        code = node.code or ""
        m = _DECL_SIZE_RE.search(code)
        if m:
            sizes[m.group(1)] = int(m.group(2))
            continue
        m = _DECL_MACRO_RE.search(code)
        if m and m.group(2) in graph.macros:
            sizes[m.group(1)] = graph.macros[m.group(2)]
    return sizes


def _is_write_target(graph: CPGGraph, nid: str) -> bool:
    """True when node `nid` is the left-hand side of an assignment operator."""
    parent_id = graph.ast_parent.get(nid)
    if not parent_id or parent_id not in graph.nodes:
        return False
    parent = graph.nodes[parent_id]
    if parent.type != "BINARYOPERATOR" or parent.token not in ASSIGN_OPS:
        return False
    # LHS is the first AST child of the assignment node.
    children = graph.ast_children.get(parent_id, [])
    return bool(children) and children[0] == nid


def _assign_in_condition(graph: CPGGraph) -> set[str]:
    """Ids of assignment operators that sit inside a control node's *condition*.

    For if/while/do/conditional the condition is the first non-statement AST
    child (the CPG lists the condition before the body). For for/foreach only a
    comparison child counts as the condition, so `for (i = 0; ...)` init and the
    `i++` update are never mistaken for an assignment-in-condition.
    """
    found: set[str] = set()
    for node in graph.nodes.values():
        if node.type not in CONTROL_TYPES:
            continue
        children = graph.ast(node.id)
        if node.type in ("FORSTATEMENT", "FOREACHSTATEMENT"):
            cond_ids = [c.id for c in children
                        if c.type == "BINARYOPERATOR" and c.token in COMPARISONS]
        else:
            cond_ids = [c.id for c in children if c.type not in STATEMENT_TYPES][:1]
        for cid in _subtree(graph, cond_ids):
            cnode = graph.nodes[cid]
            if cnode.type == "BINARYOPERATOR" and cnode.token in ASSIGN_OPS:
                found.add(cid)
    return found


def _assigned_lhs_var(graph: CPGGraph, assign_id: str) -> str | None:
    """The variable assigned by an assignment/update node, if simple."""
    for child in graph.ast_children.get(assign_id, []):
        cnode = graph.nodes.get(child)
        if cnode and cnode.type == "DECLAREDREFERENCEEXPRESSION":
            return cnode.token
    return None


def _assign_feeds_output(graph: CPGGraph, assign_ids: set[str]) -> int:
    """Count in-condition assignments whose target var reaches a return/output."""
    # pre-index every var referenced inside a return or an output call
    feeding_vars: set[str] = set()
    for node in graph.nodes.values():
        if node.type == "RETURNSTATEMENT" or (
            node.type in CALL_TYPES and node.token in OUTPUT_TOKENS
        ):
            for nid in _subtree(graph, [node.id]):
                cnode = graph.nodes[nid]
                if cnode.type == "DECLAREDREFERENCEEXPRESSION":
                    feeding_vars.add(cnode.token)
    count = 0
    for aid in assign_ids:
        var = _assigned_lhs_var(graph, aid)
        if var and var in feeding_vars:
            count += 1
    return count


_SELF_RECEIVERS = frozenset({"self", "this", "super"})


def _call_receiver(code: str, token: str) -> str | None:
    """Receiver expression of a member/static call, read from its `code` text
    (the receiver is not an AST child in this CPG). None when unreadable."""
    text = (code or "").strip()
    for marker in (f".{token}(", f"->{token}(", f"::{token}("):
        idx = text.rfind(marker)
        if idx >= 0:
            return text[:idx].strip()
    return None


def _is_self_call(fn_name: str, call: CPGNode) -> bool:
    """True when a same-name call can only target `fn_name` itself.

    A bare CALLEXPRESSION resolves to the enclosing function in C/C++/Python
    scoping. A member/static call must have receiver exactly self/this/super —
    `self.vertexes.append(...)` inside `def append` calls the *list's* append
    (measured: 79 of 251 same-name member calls are other-object calls; all
    five real-data pg-2 false flags were this shape). Unknown receiver ->
    never guessed (R3).
    """
    if call.token != fn_name:
        return False
    if call.type == "CALLEXPRESSION":
        return True
    return _call_receiver(call.code, call.token) in _SELF_RECEIVERS


def _same_arity(graph: CPGGraph, fn: CPGNode, call: CPGNode) -> bool:
    """Bare calls must match the function's parameter count to be recursion.

    C/C++ overloads share a name: the measured pg-2 false flags were a 2-arg
    `search(vec, target)` wrapper delegating to the 5-arg `search` overload —
    same name, different function. Measured on real gcc AST: a bare
    CALLEXPRESSION's AST children ARE its arguments, and a function's
    PARAMVARIABLEDECLARATION children are its parameters. Member/static calls
    are exempt here (their children include the receiver); the receiver rule
    covers them.
    """
    if call.type != "CALLEXPRESSION":
        return True
    fn_arity = sum(1 for c in graph.ast(fn.id)
                   if c.type == "PARAMVARIABLEDECLARATION")
    return len(graph.ast(call.id)) == fn_arity


def _unguarded_recursion(graph: CPGGraph) -> int:
    """Functions that call themselves with nothing that can stop the recursion.

    Guarded when (a) an if->return base case exists, OR (b) the self-call is
    itself nested under a conditional/loop (`if (n>0) f(n-1);`,
    `for (child) walk(child);` both terminate). Only truly unguarded recursion
    always crashes, which keeps the RUNTIME_ERROR pg-2 conjunction coherent —
    the (b) rule alone removed ~300 false flags on real data, and the receiver
    rule removed the remaining 5.
    """
    count = 0
    for node in graph.nodes.values():
        if node.type not in FUNCTION_TYPES or not node.token:
            continue
        # the body is a direct COMPOUNDSTATEMENT child; declaration stubs
        # (external functions) have none and are skipped
        bodies = [c.id for c in graph.ast(node.id) if c.type == "COMPOUNDSTATEMENT"]
        if not bodies:
            continue
        body_ids = _subtree(graph, bodies)
        self_calls = [
            nid for nid in body_ids
            if graph.nodes[nid].type in CALL_TYPES
            and _is_self_call(node.token, graph.nodes[nid])
            and _same_arity(graph, node, graph.nodes[nid])
        ]
        if not self_calls:
            continue
        # (a) base-case return: an if whose subtree holds a return
        if any(
            graph.nodes[nid].type == "IFSTATEMENT"
            and any(graph.nodes[x].type == "RETURNSTATEMENT" for x in _subtree(graph, [nid]))
            for nid in body_ids
        ):
            continue
        # (b) a self-call nested under a conditional / loop is guarded
        guarded_call = False
        for nid in self_calls:
            anc = graph.ast_parent.get(nid)
            while anc and anc in body_ids and anc != node.id:
                if graph.nodes[anc].type in CONTROL_TYPES:
                    guarded_call = True
                    break
                anc = graph.ast_parent.get(anc)
            if guarded_call:
                break
        if not guarded_call:
            count += 1
    return count


def _literal_value(node: CPGNode) -> int | None:
    """Numeric value of a LITERAL: the value lives in `token`, else in `code`
    (20% of real LITERAL rows carry an empty token with the value in code)."""
    raw = (node.token or node.code or "").strip().strip("'\"")
    return int(raw) if raw.lstrip("-").isdigit() else None


def _index_is_unsafe(graph: CPGGraph, sub: CPGNode, size: int) -> bool | None:
    """Judge one array write against its fixed declared size.

    True  -> write can reach >= size (count it);
    False -> statically bounded below size (skip);
    None  -> undecidable complex index (skip, never guess).

    A variable index is safe only when the innermost enclosing loop's condition
    bounds it: `<` L with L <= size, or `<=` L with L < size (the bound literal
    must be a *direct* child of the comparison — `i < n-1` carries a literal 1
    that says nothing about n). No enclosing loop, or no usable bound, is
    unsafe: real-data pg-3 crashes are input-driven unbounded writes like
    `for (i=0; loc!=0; i++) aux[i]=loc;` on `int aux[30]`.
    """
    has_literal = False
    index_var = False
    seen_base = False
    for child in graph.ast(sub.id):
        if child.type == "LITERAL":
            value = _literal_value(child)
            if value is not None:
                has_literal = True
                if value >= size:
                    return True
        elif child.type == "DECLAREDREFERENCEEXPRESSION":
            if seen_base:
                index_var = True      # first var ref is the array base, rest are index
            else:
                seen_base = True
        elif child.type == "UNARYOPERATOR" and child.token in UPDATE_OPS:
            index_var = True          # `a[i++]`: variable index
    if not index_var:
        # literal-only (all < size here) -> safe; no var and no literal -> undecidable
        return False if has_literal else None

    # variable index: look for the innermost enclosing loop's bound
    anc = graph.ast_parent.get(sub.id)
    loop: CPGNode | None = None
    while anc and anc in graph.nodes:
        if graph.nodes[anc].type in LOOP_TYPES:
            loop = graph.nodes[anc]
            break
        anc = graph.ast_parent.get(anc)
    if loop is None:
        return True                  # `a[idx] = ...` with no loop: idx from input

    conds = [c.id for c in graph.ast(loop.id) if c.type not in STATEMENT_TYPES]
    for cid in _subtree(graph, conds):
        cnode = graph.nodes[cid]
        if cnode.type != "BINARYOPERATOR" or cnode.token not in ("<", "<="):
            continue
        literals = [
            value
            for child in graph.ast(cid)
            if child.type == "LITERAL"
            for value in [_literal_value(child)]
            if value is not None
        ]
        if not literals:
            continue                 # `i < n` / `i < n-1`: no direct literal bound
        bound = max(literals)
        if cnode.token == "<" and bound <= size:
            return False
        if cnode.token == "<=" and bound < size:
            return False
    return True


def _array_write_oob(graph: CPGGraph) -> int:
    """Writes to fixed-size arrays whose index is not statically bounded below
    the size (the refined pg-3 detector, ground-truthed at ~100 rows/run)."""
    sizes = _decl_sizes(graph)
    count = 0
    for node in graph.nodes.values():
        if node.type != "ARRAYSUBSCRIPTIONEXPRESSION":
            continue
        if not _is_write_target(graph, node.id):
            continue
        base = next(
            (c.token for c in graph.ast(node.id) if c.type == "DECLAREDREFERENCEEXPRESSION"),
            None,
        )
        if base is None or base not in sizes:
            continue                 # non-simple base, or size not fixed/known
        if _index_is_unsafe(graph, node, sizes[base]):
            count += 1
    return count


def _use_before_init(graph: CPGGraph) -> int:
    """Count the CPG's own UNINITIALIZEDVALUE markers (its use-before-init signal)."""
    return sum(1 for n in graph.nodes.values() if n.type == "UNINITIALIZEDVALUE")


def _decrement_in_loop(graph: CPGGraph) -> int:
    """`--` operators that sit inside some loop's subtree (class-8 candidate)."""
    count = 0
    for node in graph.nodes.values():
        if node.type != "UNARYOPERATOR" or node.token != "--":
            continue
        nid: str | None = node.id
        while nid:
            if nid in graph.nodes and graph.nodes[nid].type in LOOP_TYPES:
                count += 1
                break
            nid = graph.ast_parent.get(nid)
    return count


def _loop_cond_var_unassigned(graph: CPGGraph) -> int:
    """while/do loops whose condition variable is never updated in the body.

    Class-10 candidate detector. Restricted to while/do — a for-loop's update is
    in its header, not its body, so it would be a false positive. Address-taking
    (`&k` passed to scanf) counts as an update to avoid input-loop false alarms.
    """
    count = 0
    for node in graph.nodes.values():
        if node.type not in ("WHILESTATEMENT", "DOSTATEMENT"):
            continue
        children = graph.ast(node.id)
        cond_ids = [c.id for c in children if c.type not in STATEMENT_TYPES][:1]
        body_ids = [c.id for c in children if c.type in STATEMENT_TYPES or c.type == "COMPOUNDSTATEMENT"]
        if not cond_ids:
            continue
        cond_vars = {
            graph.nodes[nid].token
            for nid in _subtree(graph, cond_ids)
            if graph.nodes[nid].type == "DECLAREDREFERENCEEXPRESSION"
        }
        if not cond_vars:
            continue
        assigned: set[str] = set()
        body = _subtree(graph, body_ids)
        for nid in body:
            bnode = graph.nodes[nid]
            if bnode.type == "BINARYOPERATOR" and bnode.token in ASSIGN_OPS:
                var = _assigned_lhs_var(graph, nid)
                if var:
                    assigned.add(var)
            elif bnode.type == "UNARYOPERATOR":
                if bnode.token in UPDATE_OPS:
                    var = _assigned_lhs_var(graph, nid)
                    if var:
                        assigned.add(var)
                elif bnode.token == "&":
                    for x in _subtree(graph, [nid]):
                        if graph.nodes[x].type == "DECLAREDREFERENCEEXPRESSION":
                            assigned.add(graph.nodes[x].token)
        if cond_vars - assigned:
            count += 1
    return count


def cpg_features(graph: CPGGraph) -> dict[str, Any]:
    """The `cpg` feature block for extract_features. available=True always here."""
    assign_in_cond = _assign_in_condition(graph)
    features: dict[str, Any] = {
        "available": True,
        "node_count": graph.node_count,
        "edge_count": graph.edge_count,
        "max_depth": _max_depth(graph),
        "function_count": sum(1 for n in graph.nodes.values() if n.type in FUNCTION_TYPES),
        "loop_count": sum(1 for n in graph.nodes.values() if n.type in LOOP_TYPES),
        "comparison_count": sum(
            1 for n in graph.nodes.values()
            if n.type == "BINARYOPERATOR" and n.token in COMPARISONS
        ),
        "assign_in_condition_count": len(assign_in_cond),
        "assign_feeds_output_count": _assign_feeds_output(graph, assign_in_cond),
        "unguarded_recursion_count": _unguarded_recursion(graph),
        "array_write_oob_count": _array_write_oob(graph),
        "use_before_init_count": _use_before_init(graph),
        "decrement_in_loop_count": _decrement_in_loop(graph),
        "loop_cond_var_unassigned_count": _loop_cond_var_unassigned(graph),
        # PROGpedia ships no reference solutions, so class-8 AST similarity is
        # never computable here -> None (extractor turns it into NaN, §6).
        "ast_ref_similarity": None,
    }
    return features
