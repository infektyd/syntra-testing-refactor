# Tools/common/type_utils.py
import re
from typing import Optional, Dict, Any

_CANON = {
    "dmrg": "DMRG",
    "ed":   "ED",
    "hf":   "HF",
    "peps": "PEPS",
    "qmc":  "QMC",
    "sm":   "SM",
    "vmc":  "VMC",
    "mcq_arc": "MCQ_ARC",
}

_ID_RE = re.compile(r"hf_(dmrg|ed|hf|peps|qmc|sm|vmc)_[0-9]+", re.IGNORECASE)

_KEYWORDS = [
    (re.compile(r"\bDMRG\b", re.IGNORECASE), "DMRG"),
    (re.compile(r"\b(?:Exact\s+Diagonalization|ED)\b", re.IGNORECASE), "ED"),
    (re.compile(r"\b(?:Hartree[\-\s]?Fock|HF)\b", re.IGNORECASE), "HF"),
    (re.compile(r"\bPEPS\b", re.IGNORECASE), "PEPS"),
    (re.compile(r"\bQMC\b", re.IGNORECASE), "QMC"),
    (re.compile(r"\b(?:spin\s+model|Heisenberg|Ising)\b", re.IGNORECASE), "SM"),
    (re.compile(r"\bVMC\b", re.IGNORECASE), "VMC"),
    (re.compile(r"\bMCQ[_\s]?ARC\b", re.IGNORECASE), "MCQ_ARC"),
]

def canon(s: str) -> Optional[str]:
    if not s: return None
    k = s.strip().lower()
    return _CANON.get(k)

def type_from_id(sample_id: str) -> Optional[str]:
    if not isinstance(sample_id, str):
        return None
    m = _ID_RE.search(sample_id)
    if not m: return None
    return canon(m.group(1))

def type_from_meta(meta: Dict[str, Any]) -> Optional[str]:
    # Try explicit fields first
    for key in ("type", "category", "task_type", "bench", "suite_type"):
        if key in meta:
            t = canon(str(meta[key]))
            if t: return t
    # Try keywords in prompt text/params if available
    txt = " ".join(str(meta.get(k,"")) for k in ("prompt", "text", "body", "title"))
    for rx, label in _KEYWORDS:
        if rx.search(txt):
            return label
    return None

def resolve_type(sample: Dict[str, Any]) -> Optional[str]:
    # Preferred order: explicit meta → ID pattern → keyword match
    t = type_from_meta(sample) or type_from_id(sample.get("id",""))
    if t: return t
    # As a last resort, try keywords on 'question' or 'parameters'
    params = sample.get("parameters") or {}
    txt = " ".join([str(params)] + [str(sample.get("question",""))])
    for rx, label in _KEYWORDS:
        if rx.search(txt):
            return label
    return None
