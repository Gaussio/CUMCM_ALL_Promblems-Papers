#!/usr/bin/env python3
"""生成仓库索引与元数据。

运行：
    python3 工具/build_index.py

输出：
    INDEX.md
    metadata.csv
    优秀论文_MarkDown/<年份>/INDEX.md
    赛题/<年份>/INDEX.md
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS = ROOT / "优秀论文"
MD = ROOT / "优秀论文_MarkDown"
PROBLEMS = ROOT / "赛题"
PAPER_YEARS = [str(y) for y in range(2010, 2026)]
PROBLEM_YEARS = [str(y) for y in range(1992, 2027)]
BOOKS = ["1992-2000优秀论文汇编", "2005-2011优秀论文评析A", "2005-2011优秀论文评析B"]


GENERIC_SUBSTR = ("高教社杯", "全国大学生数学建模竞赛", "数学建模竞赛", "电子科技大学",
                  "优秀论文", "竞赛论坛", "docin", "豆丁")
GENERIC_EXACT = {"摘要", "摘 要", "论文标题", "题目", "数学建模竞赛", "竞赛论坛"}


def good_title(title: str) -> bool:
    title = title.strip()
    if len(title) < 2 or title in GENERIC_EXACT:
        return False
    return not any(s in title for s in GENERIC_SUBSTR)


def md_title(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    for prefix in ("# ", "## "):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(prefix):
                title = line[len(prefix):].strip()
                if good_title(title):
                    return title
    return ""


DOCX_TITLES = {
    "2011-A-4605": "城市表层土壤重金属污染分析",
    "2013-A-6738": "车道被占用对城市道路通行能力的影响",
    "2015-C-0010": "月上柳梢头",
    "2015-C-7024": "月上柳梢头",
}


def docx_title(path: Path) -> str:
    if path.stem in DOCX_TITLES:
        return DOCX_TITLES[path.stem]
    try:
        out = subprocess.run(
            ["pandoc", str(path), "-t", "plain"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        line = line.strip()
        if line and len(line) <= 120:
            return line
    return ""


def rel(path: Path, start: Path) -> str:
    return os.path.relpath(path, start).replace(os.sep, "/")


def paper_rows() -> list[dict]:
    rows: list[dict] = []
    for year in PAPER_YEARS:
        pdir = PAPERS / year
        mdir = MD / year
        ids: set[str] = set()
        if pdir.is_dir():
            for p in pdir.iterdir():
                if p.is_file() and p.suffix.lower() in {".pdf", ".doc", ".docx"}:
                    ids.add(p.stem)
        if mdir.is_dir():
            for p in mdir.iterdir():
                if p.is_dir():
                    ids.add(p.name)
        for pid in sorted(ids):
            md_path = mdir / pid / f"{pid}.md"
            pdf_path = pdir / f"{pid}.pdf"
            doc_path = next(
                (pdir / f"{pid}{suf}" for suf in (".doc", ".docx") if (pdir / f"{pid}{suf}").exists()),
                None,
            )
            notes = []
            if md_path.exists():
                title = md_title(md_path)
                md_rel = rel(md_path, ROOT)
                md_bytes = md_path.stat().st_size
            else:
                md_rel = ""
                md_bytes = 0
                title = ""
                notes.append("仅 docx，未转 Markdown")
            if not md_path.exists() and doc_path:
                title = title or docx_title(doc_path)
            if pdf_path.exists() and doc_path:
                notes.append("多格式")
            if not pdf_path.exists():
                notes.append("无 PDF")
            img_dir = mdir / pid / "images"
            images = len(list(img_dir.iterdir())) if img_dir.is_dir() else 0
            problem = pid.split("-")[1] if len(pid.split("-")) > 2 else ""
            rows.append(
                {
                    "year": year,
                    "problem": problem,
                    "id": pid,
                    "title": title or "（未提取标题）",
                    "pdf": rel(pdf_path, ROOT) if pdf_path.exists() else "",
                    "doc": rel(doc_path, ROOT) if doc_path else "",
                    "md": md_rel,
                    "images": images,
                    "md_bytes": md_bytes,
                    "notes": "；".join(notes),
                }
            )
    return rows


def write_metadata(rows: list[dict]) -> None:
    fields = ["year", "problem", "id", "title", "pdf", "doc", "md", "images", "md_bytes", "notes"]
    with (ROOT / "metadata.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_paper_indexes(rows: list[dict]) -> None:
    by_year: dict[str, list[dict]] = {}
    for row in rows:
        by_year.setdefault(row["year"], []).append(row)
    for year in PAPER_YEARS:
        items = by_year.get(year, [])
        lines = [f"# {year} 年优秀论文", "", f"共 {len(items)} 篇。", ""]
        lines += [
            "| 题号 | 编号 | 标题 | PDF | Markdown | 图片 | 备注 |",
            "| :--: | ---- | ---- | :--: | :------: | ---: | ---- |",
        ]
        for r in items:
            pdf = f"[PDF]({rel(ROOT / r['pdf'], MD / year)})" if r["pdf"] else "—"
            md = f"[MD]({r['id']}/{r['id']}.md)" if r["md"] else "—"
            title = r["title"].replace("|", "\\|")
            lines.append(
                f"| {r['problem'] or '—'} | {r['id']} | {title} | {pdf} | {md} | {r['images']} | {r['notes']} |"
            )
        lines += ["", "---", "", "[返回总索引](../../INDEX.md)"]
        (MD / year / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_problem_indexes() -> None:
    for year in PROBLEM_YEARS:
        ydir = PROBLEMS / year
        if not ydir.is_dir():
            continue
        subdirs = sorted(p.name for p in ydir.iterdir() if p.is_dir())
        problem_dirs = [n for n in subdirs if n in {"A", "B", "C", "D", "E"}]
        other_dirs = [n for n in subdirs if n not in {"A", "B", "C", "D", "E"}]
        root_files = sorted(p.name for p in ydir.iterdir() if p.is_file() and p.name != "INDEX.md")
        lines = [f"# {year} 年赛题", ""]
        if problem_dirs:
            lines += ["## 题目目录", "", "| 题号 | 目录 | 文件 |", "| :--: | ---- | ---- |"]
            for name in problem_dirs:
                files = sorted(p.name for p in (ydir / name).iterdir())
                lines.append(f"| {name} | `{name}/` | {'、'.join(files) if files else '—'} |")
            lines.append("")
        else:
            lines += ["> 本年份题目为合并 PDF，覆盖当年全部题目。", ""]
        if root_files:
            lines += ["## 文件", ""] + [f"- `{f}`" for f in root_files] + [""]
        if other_dirs:
            lines += ["## 其他目录", ""] + [f"- `{d}/`" for d in other_dirs] + [""]
        lines += ["---", "", "[返回总索引](../../INDEX.md)"]
        (ydir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_index(rows: list[dict]) -> None:
    total_pdf = sum(1 for r in rows if r["pdf"])
    total_doc = sum(1 for r in rows if r["doc"])
    total_md = sum(1 for r in rows if r["md"])
    total_ids = len({r["id"] for r in rows})
    missing = [r for r in rows if not r["md"]]
    lines = [
        "# 资料总索引",
        "",
        "> 本文件由 `python3 工具/build_index.py` 自动生成，请勿手工编辑。",
        "",
        "## 总览",
        "",
        f"- 论文覆盖：{PAPER_YEARS[0]}–{PAPER_YEARS[-1]}",
        f"- 论文编号：{total_ids} 个",
        f"- PDF 原件：{total_pdf} 份",
        f"- doc/docx 原件：{total_doc} 份",
        f"- Markdown 论文：{total_md} 篇",
        f"- 赛题覆盖：{PROBLEM_YEARS[0]}–{PROBLEM_YEARS[-1]}（{len(PROBLEM_YEARS)} 个年份）",
        "",
        "## 赛题索引（1992–2026）",
        "",
    ]
    years = [int(y) for y in PROBLEM_YEARS]
    for start in range(years[0], years[-1] + 1, 10):
        chunk = [y for y in years if start <= y < start + 10]
        if chunk:
            lines.append(" · ".join(f"[{y}](赛题/{y}/INDEX.md)" for y in chunk))
    lines += [
        "",
        "## 论文分年索引（2010–2025）",
        "",
        "| 年份 | 优秀论文 | PDF | Markdown |",
        "| :--: | -------- | --: | -------: |",
    ]
    for year in PAPER_YEARS:
        items = [r for r in rows if r["year"] == year]
        lines.append(
            f"| {year} | [论文](优秀论文_MarkDown/{year}/INDEX.md) | "
            f"{sum(1 for r in items if r['pdf'])} | {sum(1 for r in items if r['md'])} |"
        )
    lines += [
        "",
        "## 汇编与评析",
        "",
    ]
    for name in BOOKS:
        md_path = MD / name / f"{name}.md"
        pdf_path = PAPERS / f"{name}.pdf"
        lines.append(f"- [{name}]({rel(md_path, ROOT)})" + (f" · [PDF]({rel(pdf_path, ROOT)})" if pdf_path.exists() else ""))
    lines += [
        "",
        "## 已知缺口",
        "",
        f"- **缺 Markdown**：{len(missing)} 篇（仅保留 doc/docx 原件）。",
    ]
    for r in missing:
        lines.append(f"  - `{r['year']}/{r['id']}`")
    lines += [
        "- **讲评缺失**：1992–2017 年整段缺失；2018 年仅 A 题；2021 年无资料；2023 年缺“参赛和评阅情况”。",
        "- **2025 年论文仅 7 篇**，数量明显少于其他年份。",
        "",
        "## 其他文件",
        "",
        "- [metadata.csv](metadata.csv)：全部论文的结构化元数据",
        "- [DUPLICATES.md](DUPLICATES.md)：重复论文与多格式说明",
        "- [orphan-images.txt](orphan-images.txt)：未被 Markdown 引用的图片清单",
        "",
    ]
    (ROOT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = paper_rows()
    write_metadata(rows)
    write_paper_indexes(rows)
    write_problem_indexes()
    write_root_index(rows)
    print(f"papers={len(rows)} pdf={sum(1 for r in rows if r['pdf'])} md={sum(1 for r in rows if r['md'])}")


if __name__ == "__main__":
    main()
