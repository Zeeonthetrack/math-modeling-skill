#!/usr/bin/env python3
"""One-command sanity check for DOCX paper helpers."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(os.environ.get("MATH_MODELING_SKILL_ROOT", Path(__file__).resolve().parents[3]))
SCRIPTS = ROOT / "tools" / "docx" / "scripts"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def find_template() -> Path:
    """定位官方论文模板；优先精确路径，回退到目录内首个 .docx，找不到则报错。"""
    template_dir = ROOT / "references" / "roles" / "论文手" / "references"
    preferred = template_dir / "论文模板.docx"
    if preferred.exists():
        return preferred
    for candidate in sorted(template_dir.glob("*.docx")):
        return candidate
    raise FileNotFoundError(f"未找到论文模板：{template_dir}")


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_env():
    result = subprocess.run([sys.executable, str(SCRIPTS / "check_env.py")], check=False)
    assert result.returncode == 0


def check_formula():
    equations = load("equations")
    root = etree.fromstring(equations.latex2omml(r"\frac{1}{n}\sum_{i=1}^{n}x_i^2"))
    assert root.xpath(".//m:f", namespaces={"m": M_NS})
    assert root.xpath(".//m:sSubSup", namespaces={"m": M_NS})


def check_three_line_table():
    fmt = load("paper_format")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "table.docx"
        doc = fmt.new_document()
        fmt.title(doc, "论文题目")
        fmt.abstract_title(doc)
        fmt.body(doc, "摘要正文。")
        fmt.keywords(doc, "优化；预测")
        fmt.heading1(doc, "一、问题重述")
        fmt.heading2(doc, "1.1 问题背景")
        fmt.body(doc, "这是正文。")
        assert fmt.count_chinese_chars(doc) >= 6
        fmt.equation(doc, r"x_i^2")
        placeholder, latex = fmt.equation_placeholder(doc, r"x_i^2")
        assert placeholder.startswith("EQ_")
        assert latex == r"x_i^2"
        fmt.three_line_table(doc, [["符号", "说明", "单位"], ["x", "变量", "-"]])
        fmt.figure_caption(doc, "图1 测试图")
        fmt.page_break(doc)
        doc.save(path)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "office" / "validate.py"), str(path)],
            check=False,
        )
        assert result.returncode == 0
        with zipfile.ZipFile(path) as zf:
            document = etree.fromstring(zf.read("word/document.xml"))
        keyword_paras = document.xpath("//w:p[.//w:t='关键词：']", namespaces={"w": W_NS})
        assert keyword_paras and not "".join(keyword_paras[0].getprevious().xpath(".//w:t/text()", namespaces={"w": W_NS}))
        chapter_paras = document.xpath("//w:p[.//w:t='一、问题重述']", namespaces={"w": W_NS})
        assert chapter_paras
        chapter = chapter_paras[0]
        chapter_ppr = chapter.find(f"{{{W_NS}}}pPr")
        # 国赛章节连续排版：一级标题不强制另起一页（摘要页后的分页由显式分页符处理）
        assert chapter_ppr is None or chapter_ppr.find(f"{{{W_NS}}}pageBreakBefore") is None
        chapter_size = chapter.xpath(".//w:sz/@w:val", namespaces={"w": W_NS})
        assert chapter_size == ["28"]
        chapter_font = chapter.xpath(".//w:rFonts/@w:eastAsia", namespaces={"w": W_NS})
        assert chapter_font == ["黑体"]
        chapter_align = chapter.xpath("./w:pPr/w:jc/@w:val", namespaces={"w": W_NS})
        assert chapter_align == ["center"]
        heading2_size = document.xpath(
            "//w:p[.//w:t='1.1 问题背景']//w:sz/@w:val",
            namespaces={"w": W_NS},
        )
        assert heading2_size == ["24"]
        heading2_font = document.xpath(
            "//w:p[.//w:t='1.1 问题背景']//w:rFonts/@w:eastAsia",
            namespaces={"w": W_NS},
        )
        assert heading2_font == ["黑体"]
        tbl_borders = document.xpath("//w:tbl[1]/w:tblPr/w:tblBorders/*", namespaces={"w": W_NS})
        vals = {node.tag.rsplit("}", 1)[1]: node.get(f"{{{W_NS}}}val") for node in tbl_borders}
        assert vals["top"] == "single"
        assert vals["bottom"] == "single"
        assert vals["insideV"] == "nil"
        header_bottom = document.xpath(
            "//w:tbl[1]/w:tr[1]/w:tc[1]/w:tcPr/w:tcBorders/w:bottom/@w:val",
            namespaces={"w": W_NS},
        )
        assert header_bottom == ["single"]


def check_template_validate():
    template = find_template()
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "office" / "validate.py"), str(template)],
        check=False,
    )
    assert result.returncode == 0


def main():
    check_env()
    check_formula()
    check_three_line_table()
    check_template_validate()
    print("self_check OK")


if __name__ == "__main__":
    main()
