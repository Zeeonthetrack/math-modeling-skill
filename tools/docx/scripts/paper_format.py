#!/usr/bin/env python3
"""Tiny python-docx helpers for the default math-modeling paper format."""

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor, Twips
from lxml import etree


SKILL_ROOT = Path(__file__).resolve().parents[3]


def set_run_font(run, font="宋体", size=12, bold=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:ascii"), "Times New Roman")
    r_fonts.set(qn("w:hAnsi"), "Times New Roman")
    r_fonts.set(qn("w:eastAsia"), font)
    return run


@dataclass(frozen=True)
class ContestProfile:
    name: str
    paper: str
    margins: tuple[float, float, float, float]
    required_markers: tuple[str, ...]
    rules_source: str


CONTEST_PROFILES = {
    "cumcm": ContestProfile(
        name="全国大学生数学建模竞赛",
        paper="A4",
        margins=(2.54, 2.54, 3.18, 3.18),
        required_markers=("摘 要", "关键词："),
        rules_source="http://www.mcm.edu.cn/",
    ),
    "mcm-icm": ContestProfile(
        name="MCM/ICM",
        paper="LETTER",
        margins=(2.54, 2.54, 2.54, 2.54),
        required_markers=("Summary",),
        rules_source="https://www.comap.com/contests/mcm-icm",
    ),
}


def get_profile(contest="cumcm"):
    try:
        return CONTEST_PROFILES[contest.lower()]
    except KeyError as exc:
        raise ValueError(f"未知竞赛配置: {contest}") from exc


def setup_page(doc, contest="cumcm"):
    profile = get_profile(contest)
    section = doc.sections[0]
    if profile.paper == "LETTER":
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
    else:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
    top, bottom, left, right = profile.margins
    section.top_margin = Cm(top)
    section.bottom_margin = Cm(bottom)
    section.left_margin = Cm(left)
    section.right_margin = Cm(right)


def paragraph(doc, text="", align=None, first_line=False, line_spacing=1.35):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = line_spacing
    if first_line:
        p.paragraph_format.first_line_indent = Pt(24)
    if align is not None:
        p.alignment = align
    if text:
        set_run_font(p.add_run(text))
    return p


def title(doc, text):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run_font(p.add_run(text), "黑体", 16, False)
    return p


def abstract_title(doc):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run_font(p.add_run("摘 要"), "黑体", 14, False)
    return p


def body(doc, text):
    return paragraph(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line=True)


def body_rich(doc, segments):
    """正文段落（首行缩进、两端对齐），支持 ("text", s)/("math", latex) 混排。"""
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line=True)
    return _add_rich(p, segments)


def _latex2omml(latex, display=False, font_size=24):
    try:
        from .equations import latex2omml
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from equations import latex2omml
    return latex2omml(latex, display=display, font_size=font_size)


def _add_rich(p, content, font="宋体", size=12, bold=False):
    """
    段落混排"文本 + 行内公式"。

    content 为纯 str（向后兼容，整体作为文本），或 segments 列表：
    [("text", "普通文字"), ("math", r"T_{\\text{环境}}(x)"), ...]
    ——凡含等号、上下标、希腊字母、运算符链、函数名、元组、区间的数学
    字块一律走 ("math", latex)（行内 oMath），禁止用 Unicode 上下标
    或下划线冒充；纯数字+单位的简单值（如 20%、0.004 cm）可留文本。
    """
    if isinstance(content, str):
        content = [("text", content)]
    for kind, payload in content:
        if kind == "math":
            math = OxmlElement("m:oMath")
            for child in etree.fromstring(
                _latex2omml(payload, font_size=round(size * 2))
            ):
                math.append(child)
            p._element.append(math)
        else:
            set_run_font(p.add_run(payload), font, size, bold)
    return p


def equation(doc, latex, number=None, tab_pos_twips=8300):
    """
    居中大公式（display）：居中制表位 + 行内 oMath（display 内容）
    + 右制表位悬挂编号 "(n)"；单倍行距。∑/∏ 上下限正上正下，
    min/max/lim 下极限正下方，算子与中文自动正体。

    tab_pos_twips 默认 8300（A4 + CUMCM 3.18cm 边距的版心右端），
    居中制表位自动取其一半；其他页面配置请显式传入。

    注意：不要用 m:oMathPara + m:jc=center 与编号 run 同段的写法——
    Word 实测在同段存在 tab/编号 run 时公式会退化为左对齐；双制表位
    方案（居中制表位 + 右制表位）才能保证视觉居中且编号悬挂右端。
    """
    p = paragraph(doc, line_spacing=1.0)
    p.paragraph_format.tab_stops.add_tab_stop(
        Twips(tab_pos_twips // 2), WD_TAB_ALIGNMENT.CENTER
    )
    p.paragraph_format.tab_stops.add_tab_stop(
        Twips(tab_pos_twips), WD_TAB_ALIGNMENT.RIGHT
    )
    p.add_run().add_tab()
    math = OxmlElement("m:oMath")
    for child in etree.fromstring(_latex2omml(latex, display=True)):
        math.append(child)
    p._element.append(math)
    if number:
        p.add_run().add_tab()
        set_run_font(p.add_run(f"({number})"))
    return p


def equation_placeholder(doc, latex, prefix="EQ"):
    placeholder = f"{prefix}_{uuid.uuid4().hex[:8].upper()}"
    body(doc, placeholder)
    return placeholder, latex


def keywords(doc, text):
    paragraph(doc)
    p = paragraph(doc)
    set_run_font(p.add_run("关键词："), bold=True)
    set_run_font(p.add_run(text))
    return p


def heading1(doc, text, page_break=False):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    if page_break:
        p.paragraph_format.page_break_before = True
    set_run_font(p.add_run(text), "黑体", 14, False)
    return p


def heading2(doc, text):
    p = paragraph(doc)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    set_run_font(p.add_run(text), "黑体", 12, False)
    return p


def heading3(doc, text):
    p = paragraph(doc)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    set_run_font(p.add_run(text), size=12, bold=True)
    return p


def page_break(doc):
    doc.add_page_break()


def section_break(doc):
    doc.add_section(WD_SECTION.NEW_PAGE)


def image(doc, path, width_cm=12.5):
    """插图：默认宽 12.5cm（版心的约 85%），图内文字渲染后不小于五号观感。"""
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    with open(path, "rb") as image_file:
        p.add_run().add_picture(image_file, width=Cm(width_cm))
    return p


def figure_caption(doc, content):
    """图题（图下五号居中），支持 ("text", s)/("math", latex) 混排。"""
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_rich(p, content, size=10.5)
    return p


def table_caption(doc, content):
    """表题（表上五号居中），支持 ("text", s)/("math", latex) 混排。"""
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_rich(p, content, size=10.5)
    return p


def reference_entry(doc, content):
    """参考文献条目：五号、悬挂缩进 2 字符、1.15 倍行距（紧凑向范本看齐）。"""
    p = paragraph(doc, line_spacing=1.15)
    p.paragraph_format.left_indent = Pt(21)
    p.paragraph_format.first_line_indent = Pt(-21)
    _add_rich(p, content, size=10.5)
    return p


def page_number_footer(doc):
    """在页脚居中插入自动页码（PAGE 域，五号）。页脚已有 PAGE 域时不再重复添加。"""
    footer = doc.sections[0].footer
    for existing in footer.paragraphs:
        if "PAGE" in existing._element.xml:
            return existing
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    r_fonts = OxmlElement("w:rFonts")
    r_fonts.set(qn("w:ascii"), "Times New Roman")
    r_fonts.set(qn("w:hAnsi"), "Times New Roman")
    r_fonts.set(qn("w:eastAsia"), "宋体")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "21")
    rpr.append(r_fonts)
    rpr.append(sz)
    run.append(rpr)
    text = OxmlElement("w:t")
    text.text = "1"
    run.append(text)
    fld.append(run)
    p._element.append(fld)
    return p


def count_chinese_chars(doc):
    text = "\n".join(p.text for p in doc.paragraphs)
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _border(val="nil", size="0"):
    elem = OxmlElement("w:bottom")
    elem.set(qn("w:val"), val)
    elem.set(qn("w:sz"), size)
    elem.set(qn("w:space"), "0")
    elem.set(qn("w:color"), "000000" if val != "nil" else "auto")
    return elem


def _set_cell_bottom(cell, val="nil", size="0"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        # CT_TcPr 元素顺序：tcBorders 必须位于 shd/tcMar/vAlign/hideMark 等之前
        tc_pr.insert_element_before(
            borders,
            "w:shd", "w:noWrap", "w:tcMar", "w:textDirection",
            "w:tcFitText", "w:vAlign", "w:hideMark",
        )
    for old in list(borders):
        if old.tag == qn("w:bottom"):
            borders.remove(old)
    borders.append(_border(val, size))


def _set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is not None:
        tbl_pr.remove(borders)
    borders = OxmlElement("w:tblBorders")
    # 细三线：顶/底线 1pt（sz=8），表头分隔线 0.5pt（在单元格层设置）
    for name, val, size in [
        ("top", "single", "8"),
        ("start", "nil", "0"),
        ("left", "nil", "0"),
        ("bottom", "single", "8"),
        ("end", "nil", "0"),
        ("right", "nil", "0"),
        ("insideH", "nil", "0"),
        ("insideV", "nil", "0"),
    ]:
        elem = OxmlElement(f"w:{name}")
        elem.set(qn("w:val"), val)
        elem.set(qn("w:sz"), size)
        elem.set(qn("w:space"), "0")
        elem.set(qn("w:color"), "000000" if val != "nil" else "auto")
        borders.append(elem)
    tbl_look = tbl_pr.find(qn("w:tblLook"))
    if tbl_look is None:
        tbl_pr.append(borders)
    else:
        tbl_pr.insert(tbl_pr.index(tbl_look), borders)


def _cell_plain_text(content):
    """提取单元格纯文本（用于列宽估计）。"""
    if isinstance(content, str):
        return content
    return "".join(payload for _kind, payload in content)


def _estimate_col_widths(rows, total_cm=14.64, min_cm=1.2):
    """按内容估计列宽：中文计 2 单位、其余计 1 单位，按版心宽度比例分配。"""
    ncols = len(rows[0])
    weights = [1.0] * ncols
    for row in rows:
        for i, cell in enumerate(row):
            text = _cell_plain_text(cell)
            units = sum(2 if "一" <= c <= "鿿" else 1 for c in text)
            weights[i] = max(weights[i], min(units, 24))
    total = sum(weights)
    widths = [max(min_cm, total_cm * w / total) for w in weights]
    scale = total_cm / sum(widths)
    return [w * scale for w in widths]


def three_line_table(doc, rows, col_widths=None, font_size=10.5, repeat_header=True):
    """
    国赛三线表（"表格五律"）：
    细三线（顶/底 1pt、表头 0.5pt）、单元格单倍行距、水平+垂直双居中、
    首行跨页自动重复、行不跨页断裂、列宽按内容分配（可用 col_widths
    显式指定，单位 cm）。单元格内容可为 str 或
    [("text", s) | ("math", latex), ...] 混排（符号列用公式斜体）。
    """
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(table)
    widths = col_widths or _estimate_col_widths(rows)
    for col, width in zip(table.columns, widths):
        col.width = Cm(width)
    for row_i, row in enumerate(rows):
        tr_pr = table.rows[row_i]._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        if row_i == 0 and repeat_header:
            tr_pr.append(OxmlElement("w:tblHeader"))
        for col_i, content in enumerate(row):
            cell = table.cell(row_i, col_i)
            cell.width = Cm(widths[col_i])
            tc_pr = cell._tc.get_or_add_tcPr()
            v_align = OxmlElement("w:vAlign")
            v_align.set(qn("w:val"), "center")
            # CT_TcPr 顺序：vAlign 位于序列尾部、hideMark 之前
            tc_pr.insert_element_before(v_align, "w:hideMark")
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf = p.paragraph_format
            pf.line_spacing = 1.0
            pf.space_before = Pt(1)
            pf.space_after = Pt(1)
            _add_rich(p, content, size=font_size, bold=(row_i == 0))
            if row_i == 0:
                _set_cell_bottom(cell, "single", "4")
    return table


# ---------------------------------------------------------------------------
# 附录代码块：等宽字体 + 语法着色 + 行号 + 细灰边框
# ---------------------------------------------------------------------------

_CODE_KEYWORDS = {
    "python": {
        "def", "return", "if", "elif", "else", "for", "while", "in", "import",
        "from", "as", "class", "try", "except", "finally", "with", "lambda",
        "and", "or", "not", "is", "None", "True", "False", "pass", "break",
        "continue", "raise", "yield", "global", "nonlocal", "assert", "del",
    },
    "matlab": {
        "function", "end", "if", "elseif", "else", "for", "while", "return",
        "switch", "case", "otherwise", "try", "catch", "global", "persistent",
        "break", "continue", "disp", "fprintf", "zeros", "ones", "length",
        "size", "linspace", "plot", "figure", "hold", "grid", "xlabel",
        "ylabel", "title", "legend",
    },
}
_CODE_COMMENT = {"python": "#", "matlab": "%"}

_CODE_TOKEN_RE = re.compile(
    r"(?P<string>'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
    r"|(?P<word>\b[A-Za-z_][A-Za-z0-9_]*\b)"
)


def _code_font(run, size, color=None):
    run.font.name = "Consolas"
    run.font.size = Pt(size)
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.get_or_add_rFonts()
    fonts.set(qn("w:ascii"), "Consolas")
    fonts.set(qn("w:hAnsi"), "Consolas")
    fonts.set(qn("w:eastAsia"), "宋体")  # 中文注释用宋体
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _code_line_runs(p, line, size, comment_mark, keywords):
    """单行代码着色：注释绿、字符串暗红、关键字蓝、其余黑。"""
    # 注释切分（不深入字符串内含注释符的极端情形，论文附录足够）
    comment_at = line.find(comment_mark)
    code_part, comment_part = line, None
    if comment_at >= 0:
        code_part, comment_part = line[:comment_at], line[comment_at:]

    pos = 0
    for match in _CODE_TOKEN_RE.finditer(code_part):
        if match.start() > pos:
            _code_font(p.add_run(code_part[pos:match.start()]), size)
        text = match.group(0)
        if match.lastgroup == "string":
            _code_font(p.add_run(text), size, color="A31515")
        elif match.lastgroup == "word" and text in keywords:
            _code_font(p.add_run(text), size, color="0000FF")
        else:
            _code_font(p.add_run(text), size)
        pos = match.end()
    if pos < len(code_part):
        _code_font(p.add_run(code_part[pos:]), size)
    if comment_part:
        _code_font(p.add_run(comment_part), size, color="008000")


def code_block(doc, code_text, size=9, line_numbers=True, language="python"):
    """
    附录代码块：Consolas 等宽、8~9pt、语法着色（关键字蓝/注释绿/字符串
    暗红）、行号、单倍行距、细灰边框。

    边框用段落 pBdr 实现（相邻同边框段落自动合并为整框），而非单格
    表格——避免被论文门禁误计为"表"而要求题注编号。
    language 支持 "python" / "matlab"。
    """
    keywords = _CODE_KEYWORDS.get(language, _CODE_KEYWORDS["python"])
    comment_mark = _CODE_COMMENT.get(language, "#")

    lines = code_text.rstrip("\n").split("\n")
    gutter = max(2, len(str(len(lines))))
    first_p = None
    for i, line in enumerate(lines, 1):
        p = paragraph(doc, line_spacing=1.0)
        if first_p is None:
            first_p = p
        p_pr = p._element.get_or_add_pPr()
        p_bdr = OxmlElement("w:pBdr")
        for name in ("top", "left", "bottom", "right"):
            elem = OxmlElement(f"w:{name}")
            elem.set(qn("w:val"), "single")
            elem.set(qn("w:sz"), "4")
            elem.set(qn("w:space"), "2")
            elem.set(qn("w:color"), "808080")
            p_bdr.append(elem)
        # CT_PPr 顺序：pBdr 必须位于 shd/tabs/spacing/ind/jc 等之前
        p_pr.insert_element_before(
            p_bdr,
            "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku",
            "w:wordWrap", "w:overflowPunct", "w:topLinePunct",
            "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi",
            "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
            "w:contextualSpacing", "w:jc", "w:textDirection",
            "w:textAlignment", "w:outlineLvl", "w:rPr",
        )
        if line_numbers:
            _code_font(p.add_run(f"{i:>{gutter}}  "), size, color="808080")
        _code_line_runs(p, line, size, comment_mark, keywords)
    return first_p


def _clear_template_body(doc):
    body_element = doc._element.body
    for child in list(body_element):
        if child.tag != qn("w:sectPr"):
            body_element.remove(child)


def new_document(contest="cumcm", template_path=None, preserve_template_content=False):
    """从空白文档或参考模板创建论文，可保留官方模板的固定正文。"""
    doc = Document(str(template_path)) if template_path else Document()
    if template_path and not preserve_template_content:
        _clear_template_body(doc)
    zoom = doc.settings.element.find(qn("w:zoom"))
    if zoom is not None and zoom.get(qn("w:percent")) is None:
        zoom.set(qn("w:percent"), "100")
    if not template_path:
        setup_page(doc, contest)
    return doc


def _document_texts(doc):
    texts = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            texts.extend(cell.text.strip() for cell in row.cells if cell.text.strip())
    return texts


def _content_units(text):
    """按中文字符和连续拉丁字母/数字词计数，用于中英文混排篇幅预警。"""
    return len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text))


def _numbered_object_issues(doc, kind, object_count):
    caption_pattern = re.compile(rf"^\s*{kind}\s*(\d+)(?!\d)")
    reference_pattern = re.compile(rf"{kind}\s*(\d+)(?!\d)")
    captions = {}
    body_references = set()
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        caption = caption_pattern.match(text)
        if caption:
            captions[int(caption.group(1))] = text
        else:
            body_references.update(int(number) for number in reference_pattern.findall(text))

    issues = []
    expected = set(range(1, object_count + 1))
    missing_captions = sorted(expected - set(captions))
    if missing_captions:
        issues.append(f"{kind}编号不完整，缺少题注: {missing_captions}")
    extra_captions = sorted(set(captions) - expected)
    if extra_captions:
        issues.append(f"{kind}题注没有对应对象或编号跳跃: {extra_captions}")
    for number in sorted(set(captions) - body_references):
        issues.append(f"{kind}{number} 已插入但未在正文引用")
    return issues


def _reference_issues(paragraphs):
    split_at = next(
        (index for index, p in enumerate(paragraphs) if p.text.strip().lower() in {"参考文献", "references"}),
        None,
    )
    if split_at is None:
        return ["未找到参考文献章节"]
    body = "\n".join(p.text for p in paragraphs[:split_at])
    bibliography = [p.text.strip() for p in paragraphs[split_at + 1:] if p.text.strip()]
    cited = set()
    for group in re.findall(r"\[([0-9,，\-–—\s]+)\]", body):
        for item in re.split(r"[,，]", group):
            item = item.strip()
            if not item:
                continue
            bounds = re.split(r"[\-–—]", item)
            if len(bounds) == 2 and all(bound.strip().isdigit() for bound in bounds):
                start, end = (int(bound.strip()) for bound in bounds)
                if start <= end:
                    cited.update(range(start, end + 1))
            elif item.isdigit():
                cited.add(int(item))
    listed = {
        int(match.group(1))
        for text in bibliography
        if (match := re.match(r"^\[(\d+)\]", text))
    }
    issues = [f"正文引用 [{number}] 未出现在参考文献表" for number in sorted(cited - listed)]
    issues.extend(f"参考文献 [{number}] 未在正文引用" for number in sorted(listed - cited))
    return issues


def validate_paper_structure(
    doc,
    contest="cumcm",
    *,
    quality_checks=True,
    min_content_units=None,
    min_equations=None,
    min_figures=None,
    min_tables=None,
    rendered_pages=None,
    target_pages=None,
    official_max_pages=None,
    require_rendered_pages=True,
):
    """检查官方结构、篇幅目标、公式图表、编号引用和参考文献对应关系。"""
    profile = get_profile(contest)
    texts = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    errors = []
    if not texts:
        errors.append("缺少论文标题")
    full_text = "\n".join(texts)
    for marker in profile.required_markers:
        if marker == "Summary":
            present = any(text.lower() in {"summary", "summary sheet"} for text in texts)
        elif marker.endswith("："):
            present = any(text.startswith(marker) for text in texts)
        else:
            present = marker in texts
        if not present:
            label = "摘要" if marker == "摘 要" else "关键词" if marker == "关键词：" else marker
            errors.append(f"缺少官方结构项: {label}")
    if "[待补充" in full_text:
        errors.append("论文仍含 [待补充] 占位符")
    if not quality_checks:
        return errors

    if contest.lower() == "cumcm":
        min_content_units = 9000 if min_content_units is None else min_content_units
        min_equations = 5 if min_equations is None else min_equations
        min_figures = 8 if min_figures is None else min_figures
        min_tables = 3 if min_tables is None else min_tables
        target_pages = 20 if target_pages is None else target_pages
        official_max_pages = 30 if official_max_pages is None else official_max_pages
    else:
        min_content_units = 0 if min_content_units is None else min_content_units
        min_equations = 0 if min_equations is None else min_equations
        min_figures = 8 if min_figures is None else min_figures
        min_tables = 0 if min_tables is None else min_tables

    all_text = "\n".join(_document_texts(doc))
    units = _content_units(all_text)
    equations = len(doc._element.findall(f".//{qn('m:oMath')}"))
    figures = len(doc._element.findall(f".//{qn('a:blip')}"))
    tables = len(doc.tables)
    if units < min_content_units:
        errors.append(
            f"预警：正文约 {units} 字词单位，低于 {min_content_units} 的质量目标；"
            "该目标不是 CUMCM 官方最低字数，可按当届规则或用户要求覆盖"
        )
    if equations < min_equations:
        errors.append(f"预警：仅检测到 {equations} 个可编辑公式，低于质量目标 {min_equations}")
    if figures < min_figures:
        errors.append(f"预警：仅检测到 {figures} 幅图，低于质量目标 {min_figures}")
    if tables < min_tables:
        errors.append(f"预警：仅检测到 {tables} 个表，低于质量目标 {min_tables}")

    errors.extend(_numbered_object_issues(doc, "图", figures))
    errors.extend(_numbered_object_issues(doc, "表", tables))
    errors.extend(_reference_issues(doc.paragraphs))

    if rendered_pages is None and require_rendered_pages and target_pages is not None:
        errors.append(
            f"预警：未提供渲染页数，无法检查约 {target_pages} 页质量目标和 "
            f"{official_max_pages} 页官方上限"
        )
    elif rendered_pages is not None:
        if target_pages is not None and rendered_pages < target_pages:
            errors.append(
                f"预警：渲染后共 {rendered_pages} 页，低于约 {target_pages} 页质量目标；"
                "该目标不是官方最低页数"
            )
        if official_max_pages is not None and rendered_pages > official_max_pages:
            errors.append(
                f"渲染后共 {rendered_pages} 页，超过当前核验的官方上限 {official_max_pages} 页"
            )
    return errors


def _is_within(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def save_document(doc, project_root, filename="完整论文.docx", contest="cumcm", overwrite=False):
    """校验后原子保存到 PROJECT_ROOT，并拒绝写入 Skill 目录。"""
    project = Path(project_root).resolve()
    if _is_within(project, SKILL_ROOT):
        raise ValueError("PROJECT_ROOT 不能位于 SKILL_ROOT 内部")
    output = (project / filename).resolve()
    if not _is_within(output, project):
        raise ValueError("论文输出必须位于 PROJECT_ROOT 内部")
    if _is_within(output, SKILL_ROOT):
        raise ValueError("论文输出不能位于 SKILL_ROOT 内部")
    issues = validate_paper_structure(doc, contest)
    errors = [issue for issue in issues if not issue.startswith("预警：")]
    if errors:
        raise ValueError("论文结构校验失败: " + "；".join(errors))
    if output.exists() and not overwrite:
        raise FileExistsError(f"输出已存在，未覆盖: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    doc.save(temporary)
    os.replace(temporary, output)
    return output


def validate_document(path, *, contest="cumcm", rendered_pages=None):
    """校验现有 DOCX，并返回可供完成门禁使用的结构化结果。"""
    source = Path(path).resolve()
    if not source.is_file() or source.suffix.casefold() != ".docx":
        raise FileNotFoundError(f"DOCX 论文不存在：{source}")
    doc = Document(source)
    issues = validate_paper_structure(
        doc,
        contest,
        quality_checks=True,
        rendered_pages=rendered_pages,
        require_rendered_pages=True,
    )
    text = "\n".join(_document_texts(doc))
    return {
        "path": str(source),
        "metrics": {
            "content_units": _content_units(text),
            "rendered_pages": rendered_pages,
            "equations": len(doc._element.findall(f".//{qn('m:oMath')}")),
            "figures": len(doc._element.findall(f".//{qn('a:blip')}")),
            "tables": len(doc.tables),
        },
        "issues": issues,
        "passed": not issues,
    }


def main():
    parser = argparse.ArgumentParser(description="生成或校验数学建模 DOCX")
    commands = parser.add_subparsers(dest="action", required=True)
    validate = commands.add_parser("validate", help="执行 DOCX 完成门禁")
    validate.add_argument("path", type=Path)
    validate.add_argument("--contest", choices=sorted(CONTEST_PROFILES), default="cumcm")
    validate.add_argument("--rendered-pages", type=int, required=True)
    arguments = parser.parse_args()
    result = validate_document(
        arguments.path,
        contest=arguments.contest,
        rendered_pages=arguments.rendered_pages,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
