from __future__ import annotations

import hashlib
import html
import json
import random
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from .lexicons import (GEL, MICROGRAPH_STRONG, MICROSCOPY_STRONG, MICROSCOPY_WEAK,
                       NON_IMAGE_FIGURE, PLOT, SCALE_EVIDENCE, SCHEMATIC,
                       SPECIMEN_EVIDENCE, STRUCTURE)
from .config import (LABEL_NAMES, MAX_CAPTION_CHARS, MIN_CAPTION_CHARS,
                     NOT_DETECTED, PRESENT, RANDOM_SEED, UNCLEAR)
from .rules import apply_rules

def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

def iter_local(root: ET.Element, name: str) -> Iterator[ET.Element]:
    for el in root.iter():
        if local_name(el.tag) == name:
            yield el

def children_local(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in list(el) if local_name(c.tag) == name]

def attr_suffix(el: ET.Element, suffix: str) -> str:
    for k, v in el.attrib.items():
        if k.rsplit("}", 1)[-1] == suffix:
            return v
    return ""

_WS = re.compile(r"\s+")

_DOI_TRAILER = re.compile(
    r"\s*DOI\s*:?\s*(?:https?://\S+|10\.\d{4,9}/\S+)\s*$", re.IGNORECASE)

_FIG_URL = re.compile(r"https?://\S+")

def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    for ch in (" ", " ", " ", " ", " "):
        text = text.replace(ch, " ")
    text = _WS.sub(" ", text)
    return text.strip()

def element_text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return clean_text("".join(el.itertext()))

_LICENCE_SLUGS = [
    ("cc0", re.compile(r"publicdomain/zero|/cc0", re.I)),
    ("cc-by", re.compile(r"licenses/by/[\d.]+", re.I)),
    ("cc-by-sa", re.compile(r"licenses/by-sa", re.I)),
    ("cc-by-nc", re.compile(r"licenses/by-nc/[\d.]+", re.I)),
    ("cc-by-nc-sa", re.compile(r"licenses/by-nc-sa", re.I)),
    ("cc-by-nc-nd", re.compile(r"licenses/by-nc-nd", re.I)),
    ("cc-by-nd", re.compile(r"licenses/by-nd", re.I)),
]

def normalise_licence(href: str, text: str) -> str:
    blob = f"{href} {text}"
    for slug, pat in _LICENCE_SLUGS:
        if pat.search(blob):
            return slug
    low = blob.lower()
    if "creative commons attribution" in low and "noncommercial" not in low:
        return "cc-by"
    if "public domain" in low:
        return "cc0"
    if low.strip():
        return "other"
    return "unknown"

_YEAR = re.compile(r"(19|20)\d{2}")

_PUB_DATE_KINDS = ("ppub", "epub", "collection", "pub", "epub-ppub", "print")

def _publication_year(article: ET.Element) -> str:
    fronts = [f for f in iter_local(article, "front")] or [article]

    dated: List[tuple] = []
    for front in fronts:
        for pd in iter_local(front, "pub-date"):
            kind = (pd.attrib.get("pub-type", "")
                    or pd.attrib.get("date-type", "")).lower()
            for y in children_local(pd, "year"):
                txt = element_text(y)
                if _YEAR.fullmatch(txt or ""):
                    rank = (_PUB_DATE_KINDS.index(kind)
                            if kind in _PUB_DATE_KINDS else len(_PUB_DATE_KINDS))
                    dated.append((rank, int(txt), txt))
    if dated:
        dated.sort()
        return dated[0][2]

    for front in fronts:
        if front is article:
            break
        years = [element_text(y) for y in iter_local(front, "year")]
        years = [y for y in years if _YEAR.fullmatch(y or "")]
        if years:
            return min(years)
    return ""

def article_metadata(article: ET.Element) -> Dict[str, str]:
    meta: Dict[str, str] = {
        "pmcid": "", "pmid": "", "doi": "", "publisher_id": "",
        "journal": "", "article_title": "", "year": "",
        "license_type": "unknown", "license_href": "", "article_type": "",
    }
    meta["article_type"] = article.attrib.get("article-type", "")

    for aid in iter_local(article, "article-id"):
        kind = aid.attrib.get("pub-id-type", "")
        val = element_text(aid)
        if kind == "pmcid" or (kind == "pmc" and val):
            meta["pmcid"] = val if val.upper().startswith("PMC") else f"PMC{val}"
        elif kind == "pmid":
            meta["pmid"] = val
        elif kind == "doi":
            meta["doi"] = val
        elif kind == "publisher-id":
            meta["publisher_id"] = val

    for jt in iter_local(article, "journal-title"):
        meta["journal"] = element_text(jt)
        break

    for tg in iter_local(article, "title-group"):
        at = children_local(tg, "article-title")
        if at:
            meta["article_title"] = element_text(at[0])
            break

    meta["year"] = _publication_year(article)

    for lic in iter_local(article, "license"):
        href = attr_suffix(lic, "href")
        txt = element_text(lic)
        meta["license_href"] = href
        meta["license_type"] = normalise_licence(href, txt)
        break
    else:
        for perm in iter_local(article, "permissions"):
            txt = element_text(perm)
            meta["license_type"] = normalise_licence("", txt)
            break

    return meta

def _caption_parts(fig: ET.Element) -> Dict[str, str]:
    title, body = "", []
    for cap in children_local(fig, "caption"):
        for child in list(cap):
            name = local_name(child.tag)
            if name == "title" and not title:
                title = element_text(child)
            elif name in {"p", "sec"}:
                body.append(element_text(child))
    if not title and not body:
        body = [element_text(p) for p in children_local(fig, "p")]
    return {"caption_title": title, "caption_body": " ".join(b for b in body if b).strip()}

def extract_figures(article: ET.Element) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen_ids = set()
    for fig in article.iter():
        if local_name(fig.tag) != "fig":
            continue
        fid = fig.attrib.get("id", "")
        if fid and fid in seen_ids:
            continue
        seen_ids.add(fid)

        label = ""
        labels = children_local(fig, "label")
        if labels:
            label = element_text(labels[0])

        parts = _caption_parts(fig)
        caption = " ".join(p for p in (parts["caption_title"], parts["caption_body"]) if p)
        caption = _DOI_TRAILER.sub("", caption).strip()
        caption = _FIG_URL.sub("", caption).strip()
        caption = clean_text(caption)
        if not caption:
            continue

        out.append({
            "figure_id": fid,
            "figure_label": label,
            "caption_title": parts["caption_title"],
            "caption_body": parts["caption_body"],
            "caption": caption,
            "is_supplement": "1" if re.search(r"supplement", f"{fid} {label}", re.I) else "0",
        })
    return out

def legend_id(record: Dict[str, Any]) -> str:
    basis = "|".join([
        str(record.get("source_id", "")),
        str(record.get("figure_id", "")),
        clean_text(str(record.get("caption", ""))).lower(),
    ])
    return "leg_" + hashlib.sha1(basis.encode("utf-8", "ignore")).hexdigest()[:16]

def legends_from_xml_text(xml_text: str, source: str, source_path: str = "") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return rows
    articles = ([root] if local_name(root.tag) == "article"
                else [a for a in iter_local(root, "article")])
    for article in articles:
        meta = article_metadata(article)
        source_id = meta["pmcid"] or meta["doi"] or meta["publisher_id"] or source_path
        for fig in extract_figures(article):
            rec: Dict[str, Any] = {"source": source, "source_path": source_path,
                                   "source_id": source_id, **meta, **fig}
            rec["n_chars"] = len(rec["caption"])
            rec["legend_id"] = legend_id(rec)
            rows.append(rec)
    return rows

def legends_from_files(paths: Iterable[Path], source: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="replace")
        rows.extend(legends_from_xml_text(text, source=source, source_path=Path(p).name))
    return rows

def microscopy_score(caption: str) -> Dict[str, Any]:
    strong = [m.group(0) for m in MICROSCOPY_STRONG.finditer(caption)]
    weak = [m.group(0) for m in MICROSCOPY_WEAK.finditer(caption)]
    non_image = [m.group(0) for m in NON_IMAGE_FIGURE.finditer(caption)]

    strong_kinds = {s.lower() for s in strong}
    score = 2 * len(strong_kinds) + min(len(set(w.lower() for w in weak)), 4)
    penalty = min(len(set(n.lower() for n in non_image)), 4)

    return {
        "strong_hits": sorted(strong_kinds)[:8],
        "weak_hits": sorted({w.lower() for w in weak})[:8],
        "non_image_hits": sorted({n.lower() for n in non_image})[:8],
        "n_strong": len(strong_kinds),
        "microscopy_score": score,
        "non_image_penalty": penalty,
    }

def microscopy_classify(caption: str, min_strong: int = 1) -> Tuple[str, str, Dict[str, Any]]:
    n = len(caption)
    sc = microscopy_score(caption)

    if n < MIN_CAPTION_CHARS:
        return "drop", f"caption_too_short(<{MIN_CAPTION_CHARS})", sc
    if n > MAX_CAPTION_CHARS:
        return "drop", f"caption_too_long(>{MAX_CAPTION_CHARS})", sc
    if sc["n_strong"] < min_strong:
        return "drop", "no_strong_microscopy_cue", sc
    if sc["non_image_penalty"] >= 3 and sc["n_strong"] <= 1:
        return "drop", "dominated_by_non_image_content", sc
    if sc["non_image_hits"]:
        return "keep_mixed", "mixed_figure_kept", sc
    return "keep", "microscopy_cue_present", sc

def microscopy_filter(rows: List[Dict[str, Any]], min_strong: int = 1
                ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept, dropped = [], []
    for r in rows:
        decision, reason, sc = microscopy_classify(r.get("caption", ""), min_strong=min_strong)
        r = {**r, **sc, "filter_decision": decision, "filter_reason": reason}
        (kept if decision.startswith("keep") else dropped).append(r)
    return kept, dropped

_NORM = re.compile(r"[^a-z0-9 ]+")

def dedupe(rows: List[Dict[str, Any]], per_article_cap: int = 4
           ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    seen_norm: set = set()
    per_article: Dict[str, int] = {}
    kept, dropped = [], []
    rows = sorted(rows, key=lambda r: (str(r.get("source_id")), -len(r.get("caption", ""))))
    for r in rows:
        norm = _NORM.sub(" ", r.get("caption", "").lower())
        norm = " ".join(norm.split())
        aid = str(r.get("source_id", ""))
        if norm in seen_norm:
            dropped.append({**r, "dedupe_reason": "duplicate_caption"})
            continue
        if per_article.get(aid, 0) >= per_article_cap:
            dropped.append({**r, "dedupe_reason": "per_article_cap"})
            continue
        seen_norm.add(norm)
        per_article[aid] = per_article.get(aid, 0) + 1
        kept.append(r)
    return kept, dropped

def _ft_hits(pattern: re.Pattern[str], text: str, cap: int = 6) -> List[str]:
    seen: List[str] = []
    for m in pattern.finditer(text):
        t = m.group(0).lower()
        if t not in seen:
            seen.append(t)
        if len(seen) >= cap:
            break
    return seen

def figure_type_score(caption: str) -> Dict[str, Any]:
    mg = _ft_hits(MICROGRAPH_STRONG, caption)
    sp = _ft_hits(SPECIMEN_EVIDENCE, caption)
    sc = _ft_hits(SCALE_EVIDENCE, caption)
    st = _ft_hits(STRUCTURE, caption)
    gl = _ft_hits(GEL, caption)
    pl = _ft_hits(PLOT, caption)
    sh = _ft_hits(SCHEMATIC, caption)

    micrograph = 2.0 * len(mg) + 1.5 * len(sc)
    if mg and sp:
        micrograph += 0.5

    scores = {
        "micrograph": micrograph,
        "structure": 2.0 * len(st),
        "gel": 2.0 * len(gl),
        "plot": 1.0 * len(pl),
        "schematic": 1.5 * len(sh),
    }
    return {
        "type_scores": {k: round(v, 2) for k, v in scores.items()},
        "micrograph_hits": mg, "specimen_hits": sp, "scale_hits": sc,
        "structure_hits": st, "gel_hits": gl, "plot_hits": pl,
        "schematic_hits": sh,
    }

def figure_type_classify(caption: str, keep_mixed: bool = True,
             keep_structure: bool = False, min_micrograph: float = 2.0
             ) -> Tuple[str, str, str, Dict[str, Any]]:
    ev = figure_type_score(caption)
    s = ev["type_scores"]
    mg = s["micrograph"]
    others = {k: v for k, v in s.items() if k != "micrograph"}
    top_other, top_other_score = max(others.items(), key=lambda kv: kv[1])

    if mg < min_micrograph:
        if top_other_score <= 0:
            return "unknown", "drop", "no figure-type evidence at all", ev
        return top_other, "drop", f"no micrograph evidence; looks like {top_other}", ev

    if top_other_score > mg * 1.5:
        if top_other == "structure" and not keep_structure:
            return "structure", "drop", (
                "dominated by structural-biology rendering; these are images of "
                "molecules, not micrographs of specimens"), ev
        if top_other in {"gel", "schematic"}:
            return top_other, "drop", f"dominated by {top_other} content", ev
        if top_other == "plot":
            return "mixed", ("keep_mixed" if keep_mixed else "drop"), (
                "micrograph evidence present but plot content dominates"), ev

    if top_other_score > 0:
        return "mixed", ("keep_mixed" if keep_mixed else "drop"), (
            f"micrograph plus {top_other} panels"), ev
    return "micrograph", "keep", "clear micrograph evidence", ev

def figure_type_annotate(rows: Sequence[Dict[str, Any]], **kw) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        ftype, decision, reason, ev = figure_type_classify(r.get("caption", ""), **kw)
        rec = dict(r)
        rec["figure_type"] = ftype
        rec["figure_type_decision"] = decision
        rec["figure_type_reason"] = reason
        rec["figure_type_scores"] = ev["type_scores"]
        rec["figure_type_evidence"] = "; ".join(
            ev["micrograph_hits"][:3] + ev["specimen_hits"][:2])
        out.append(rec)
    return out

def figure_type_filter(rows: Sequence[Dict[str, Any]], **kw
                ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    annotated = figure_type_annotate(rows, **kw)
    kept = [r for r in annotated if r["figure_type_decision"].startswith("keep")]
    dropped = [r for r in annotated if not r["figure_type_decision"].startswith("keep")]
    return kept, dropped

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

DEFAULT_PMC_QUERY = (
    '("confocal microscopy"[All Fields] OR "fluorescence microscopy"[All Fields] '
    'OR "immunofluorescence"[All Fields] OR "electron microscopy"[All Fields] '
    'OR "phase contrast"[All Fields] OR "bright field"[All Fields] '
    'OR "immunohistochemistry"[All Fields] OR "scale bar"[All Fields] '
    'OR "DAPI"[All Fields] OR "micrograph"[All Fields]) '
    'AND "open access"[filter]'
)

ELIFE_REPO = "https://github.com/elifesciences/elife-article-xml.git"

def _http_get(url: str, params: Dict[str, Any], retries: int = 3,
              sleep_s: float = 0.34, timeout: int = 90) -> bytes:
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            full = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(
                full, headers={"User-Agent":
                               "mlc-pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            time.sleep(sleep_s)
            return data
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url} :: {last}")

def esearch_pmc(query: str, retmax: int, retstart: int = 0, email: str = "",
                api_key: str = "") -> Tuple[List[str], int]:
    params: Dict[str, Any] = {
        "db": "pmc", "term": query, "retmax": retmax, "retstart": retstart,
        "retmode": "json", "tool": "mlc-pipeline",
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    payload = json.loads(_http_get(NCBI_ESEARCH, params).decode("utf-8", "replace"))
    result = payload.get("esearchresult", {})
    return list(result.get("idlist", [])), int(result.get("count", 0) or 0)

def efetch_pmc_batch(pmc_ids: Sequence[str], email: str = "", api_key: str = "",
                     sleep_s: float = 0.34) -> str:
    params: Dict[str, Any] = {
        "db": "pmc", "id": ",".join(str(i).replace("PMC", "") for i in pmc_ids),
        "retmode": "xml", "tool": "mlc-pipeline",
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return _http_get(NCBI_EFETCH, params, sleep_s=sleep_s).decode("utf-8", "replace")


def collect_pmc(out_dir: Path, target_articles: int = 400, batch_size: int = 20,
                query: str = DEFAULT_PMC_QUERY, email: str = "", api_key: str = ""
                ) -> List[Dict[str, Any]]:
    raw_dir = Path(out_dir) / "raw_xml"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ids: List[str] = []
    seen: set = set()
    start = 0
    while len(ids) < target_articles:
        want = min(200, target_articles - len(ids))
        page, total = esearch_pmc(query, retmax=want, retstart=start,
                                  email=email, api_key=api_key)
        if not page:
            break
        for pid in page:
            if pid not in seen:
                seen.add(pid)
                ids.append(pid)
        start += len(page)
        if start >= total:
            break
    ids = ids[:target_articles]
    rows: List[Dict[str, Any]] = []
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        tag = f"batch_{i // batch_size:04d}"
        xml_text = efetch_pmc_batch(batch, email=email, api_key=api_key)
        (raw_dir / f"pmc_{tag}.xml").write_text(xml_text, encoding="utf-8")
        rows.extend(legends_from_xml_text(xml_text, source="pmc_oa", source_path=tag))
    return rows

_ELIFE_NAME = re.compile(r"elife-(\d+)-v(\d+)\.xml$")

def _run(cmd: Sequence[str], cwd: Optional[Path] = None, timeout: int = 1800) -> str:
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} failed:\n{proc.stderr[-2000:]}")
    return proc.stdout

def clone_elife_sample(work_dir: Path, n_articles: int = 500, seed: int = RANDOM_SEED
                       ) -> Path:
    work_dir = Path(work_dir)
    repo = work_dir / "elife-article-xml"
    if not (repo / ".git").exists():
        work_dir.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--filter=blob:none", "--depth", "1", "--sparse",
              "--single-branch", ELIFE_REPO, str(repo)], timeout=1800)

    listing = _run(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "articles"],
                   cwd=repo)
    latest: Dict[str, Tuple[int, str]] = {}
    for line in listing.splitlines():
        m = _ELIFE_NAME.search(line.strip())
        if not m:
            continue
        aid, ver = m.group(1), int(m.group(2))
        if aid not in latest or ver > latest[aid][0]:
            latest[aid] = (ver, line.strip())
    paths = sorted(v[1] for v in latest.values())

    rng = random.Random(seed)
    sample = sorted(rng.sample(paths, min(n_articles, len(paths))))
    spec = repo / ".git" / "info" / "mlc_sample.txt"
    spec.write_text("\n".join(sample) + "\n", encoding="utf-8")

    proc = subprocess.run(["git", "sparse-checkout", "set", "--no-cone", "--stdin"],
                          cwd=str(repo), input="\n".join(sample) + "\n",
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:])
    _run(["git", "checkout", "HEAD"], cwd=repo, timeout=3600)
    return repo / "articles"

def collect_elife(articles_dir: Path) -> List[Dict[str, Any]]:
    return legends_from_files(sorted(Path(articles_dir).glob("*.xml")), source="elife")

def collect_local(xml_dir: Path) -> List[Dict[str, Any]]:
    return legends_from_files(sorted(Path(xml_dir).rglob("*.xml")), source="local")

def build_corpus(raw_rows: List[Dict[str, Any]], per_article_cap: int = 3,
                 min_strong: int = 1, target_legends: Optional[int] = None,
                 seed: int = RANDOM_SEED) -> Dict[str, List[Dict[str, Any]]]:
    kept, dropped_filter = microscopy_filter(raw_rows, min_strong=min_strong)
    kept, dropped_figtype = figure_type_filter(kept)
    deduped, dropped_dedupe = dedupe(kept, per_article_cap=per_article_cap)
    if target_legends and len(deduped) > target_legends:
        by_article: Dict[str, List[Dict[str, Any]]] = {}
        for r in deduped:
            by_article.setdefault(str(r["source_id"]), []).append(r)
        aids = sorted(by_article)
        random.Random(seed).shuffle(aids)
        chosen: List[Dict[str, Any]] = []
        for aid in aids:
            if len(chosen) >= target_legends:
                break
            chosen.extend(by_article[aid])
        deduped = chosen[:target_legends + per_article_cap]
    return {"corpus": deduped, "dropped_microscopy": dropped_filter,
            "dropped_figure_type": dropped_figtype, "dropped_dedupe": dropped_dedupe}


def annotate_row(row: Dict[str, Any]) -> Dict[str, Any]:
    res = apply_rules(row.get("caption", ""))
    out: Dict[str, Any] = dict(row)
    for label in LABEL_NAMES:
        out[f"silver_{label}"] = res.labels[label]
        out[f"evidence_{label}"] = res.evidence_text(label, limit=3)
        out[f"spans_{label}"] = res.spans(label)
    out["scale_evidence_subtype"] = res.subtypes.get("scale_magnification", "")
    for cue, val in res.cues.items():
        out[f"cue_{cue}"] = int(bool(val))
    out["n_silver_present"] = sum(
        1 for lb in LABEL_NAMES if out[f"silver_{lb}"] == PRESENT)
    return out

def annotate_corpus(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [annotate_row(r) for r in rows]

LENGTH_BANDS = (("short", 0, 700), ("mid", 700, 1600), ("long", 1600, 10 ** 9))

def length_band(caption: str) -> str:
    n = len(caption or "")
    for name, lo, hi in LENGTH_BANDS:
        if lo <= n < hi:
            return name
    return "long"

def stratified_pilot(rows: Sequence[Dict[str, Any]], n_total: int = 300,
                     seed: int = RANDOM_SEED, max_per_article: int = 2
                     ) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        buckets[_stratum_of(r)].append(r)
    for key in buckets:
        rng.shuffle(buckets[key])
    keys = sorted(buckets)
    chosen: List[Dict[str, Any]] = []
    seen_articles: Counter = Counter()
    idx = 0
    while len(chosen) < n_total and any(buckets[k] for k in keys):
        key = keys[idx % len(keys)]
        idx += 1
        pool = buckets[key]
        while pool:
            cand = pool.pop()
            aid = str(cand.get("source_id", ""))
            if seen_articles[aid] >= max_per_article:
                continue
            seen_articles[aid] += 1
            chosen.append(cand)
            break
    return chosen[:n_total]

def _stratum_of(r: Dict[str, Any]) -> str:
    npos = int(r.get("n_silver_present", 0))
    rich = "rich" if npos >= 5 else ("mid" if npos >= 3 else "sparse")
    return f"{length_band(r.get('caption', ''))}|{rich}"

def blind_sheet(rows: Sequence[Dict[str, Any]], round_name: str = "round1"
                ) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        rec = {
            "legend_id": r["legend_id"],
            "source_id": r.get("source_id", ""),
            "figure_label": r.get("figure_label", ""),
            "length_band": length_band(r.get("caption", "")),
            "caption": r.get("caption", ""),
        }
        for lb in LABEL_NAMES:
            rec[f"manual_{lb}"] = ""
        rec["annotator_note"] = ""
        rec["round"] = round_name
        out.append(rec)
    return out

_ALIASES = {
    "P": PRESENT, "PRESENT": PRESENT, "1": PRESENT, "Y": PRESENT, "YES": PRESENT,
    "N": NOT_DETECTED, "NOT_DETECTED": NOT_DETECTED, "ND": NOT_DETECTED,
    "0": NOT_DETECTED, "NO": NOT_DETECTED, "NOT DETECTED": NOT_DETECTED,
    "U": UNCLEAR, "UNCLEAR": UNCLEAR, "?": UNCLEAR,
    "是": PRESENT, "有": PRESENT,
    "否": NOT_DETECTED, "没有": NOT_DETECTED,
    "无": NOT_DETECTED,
    "不确定": UNCLEAR, "存疑": UNCLEAR,
    "TRUE": PRESENT, "FALSE": NOT_DETECTED,
}

def normalise_value(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip().upper()
    if not s:
        return ""
    return _ALIASES.get(s, "")

def parse_sheet(rows: Sequence[Dict[str, str]], column_prefix: str = "manual"
                ) -> Dict[str, Dict[str, str]]:
    labels: Dict[str, Dict[str, str]] = {}
    for r in rows:
        lid = str(r.get("legend_id", "")).strip()
        if not lid:
            continue
        vals = {lb: normalise_value(r.get(f"{column_prefix}_{lb}", ""))
                for lb in LABEL_NAMES}
        if not any(vals.values()):
            continue
        labels[lid] = vals
    return labels
