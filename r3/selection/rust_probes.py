#!/usr/bin/env python3
"""R3 eligibility, Rust part: insert one probe per (fault, enclosing function) into a copy of Qiskit 2.6.1's Rust
source. A probe records the fault id the first time its function runs. After building this instrumented copy and
compiling the corpus with it (probe_corpus.py), the probe file lists the faults whose changed Rust functions ran.
Function-level, like the Python rule in exercised.py. Uses no check, no fault build and no detection label.

    python rust_probes.py candidates.json <clean 2.6.1 tree> <copy to instrument>
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from exercised import changed_lines_post  # noqa: E402

FN = re.compile(r'^\s*(pub(\([^)]*\))?\s+)?(default\s+)?(async\s+)?(unsafe\s+)?(extern\s+"[^"]*"\s+)?fn\s+\w+')
PROBE_FILE = "/tmp/qk_r3_probes.txt"
FLAG_FILE = "/tmp/qk_r3_on"


def probe(fid: str) -> str:
    """Records fid once, at the first call made while the flag file exists (so circuit construction before
    compilation is not counted)."""
    return ('{ static __R3P: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false); '
            'if !__R3P.load(std::sync::atomic::Ordering::Relaxed) && std::path::Path::new("' + FLAG_FILE + '").exists() '
            '&& !__R3P.swap(true, std::sync::atomic::Ordering::Relaxed) { use std::io::Write as _; '
            f'if let Ok(mut __f) = std::fs::OpenOptions::new().create(true).append(true).open("{PROBE_FILE}") '
            f'{{ let _ = writeln!(__f, "{fid}"); }} }} }}')


def functions(lines: list[str]):
    """(start, body_open, end) line indices of every fn with a body; brace counting ignores // comments."""
    out = []
    for i, l in enumerate(lines):
        if not FN.match(l) or re.match(r"^\s*(pub\s+)?const\s+fn", l):
            continue
        j = i
        while j < len(lines) and not lines[j].split("//")[0].rstrip().endswith("{"):
            if lines[j].split("//")[0].rstrip().endswith(";"):
                j = None; break
            j += 1
        if j is None or j >= len(lines):
            continue
        depth, k = 0, j
        for k in range(j, len(lines)):
            code = lines[k].split("//")[0]
            depth += code.count("{") - code.count("}")
            if depth <= 0 and k > j:
                break
        out.append((i, j, k))
    return out


def main() -> int:
    cands = json.load(open(sys.argv[1]))
    src, dst = Path(sys.argv[2]), Path(sys.argv[3])
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git"))
    inserts: dict[str, dict[int, list[str]]] = {}
    report = {}
    for r in cands:
        if not r.get("rust"):
            continue
        fid = r["pr"] or r["h"]
        ch = {f: s for f, s in changed_lines_post(Path(r["patch"]).read_text()).items()
              if f.startswith("crates/") and f.endswith(".rs")}
        n = 0
        for f, ls in ch.items():
            lines = (src / f).read_text().splitlines()
            fns = functions(lines)
            for l in ls:
                i0 = l - 1
                enc = [(a, b, c) for a, b, c in fns if a <= i0 <= c]
                if not enc:
                    continue
                a, b, c = max(enc, key=lambda x: x[0])          # innermost
                inserts.setdefault(f, {}).setdefault(b, [])
                if probe(fid) not in inserts[f][b]:
                    inserts[f][b].append(probe(fid)); n += 1
        report[fid] = n
    for f, at in inserts.items():
        lines = (dst / f).read_text().splitlines()
        for b in sorted(at, reverse=True):
            lines[b + 1:b + 1] = at[b]
        (dst / f).write_text("\n".join(lines) + "\n")
    json.dump(report, sys.stdout, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
