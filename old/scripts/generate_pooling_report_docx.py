#!/usr/bin/env python3
"""Generate a Word report for pooling comparison results without external docx libs."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image


NS = {
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "o": "urn:schemas-microsoft-com:office:office",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v": "urn:schemas-microsoft-com:vml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w10": "urn:schemas-microsoft-com:office:word",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pooling comparison Word report.")
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--overall-csv", required=True)
    parser.add_argument("--per-flight-csv", required=True)
    parser.add_argument("--figures-dir", required=True)
    parser.add_argument("--output-docx", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def short_flight(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def pct_faster(base: float, candidate: float) -> float:
    return (base - candidate) / base * 100.0 if base else 0.0


def pct_lower(base: float, candidate: float) -> float:
    return (base - candidate) / base * 100.0 if base else 0.0


def xml_text(text: str) -> str:
    return html.escape(text, quote=False)


def paragraph(text: str = "", style: str | None = None, bold: bool = False) -> str:
    runs = []
    for line_idx, chunk in enumerate(text.split("\n")):
        if line_idx:
            runs.append("<w:r><w:br/></w:r>")
        if not chunk:
            runs.append("<w:r><w:t xml:space=\"preserve\"></w:t></w:r>")
            continue
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        runs.append(f"<w:r>{rpr}<w:t xml:space=\"preserve\">{xml_text(chunk)}</w:t></w:r>")
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def table(rows: list[list[str]]) -> str:
    grid_cols = max(len(row) for row in rows)
    grid = "".join("<w:gridCol w:w=\"1800\"/>" for _ in range(grid_cols))
    body = []
    for row_idx, row in enumerate(rows):
        cells = []
        for cell in row:
            shade = "<w:shd w:fill=\"DCE6F1\"/>" if row_idx == 0 else ""
            cells.append(
                "<w:tc>"
                "<w:tcPr>"
                "<w:tcW w:w=\"1800\" w:type=\"dxa\"/>"
                f"{shade}"
                "</w:tcPr>"
                f"{paragraph(cell, bold=(row_idx == 0))}"
                "</w:tc>"
            )
        body.append(f"<w:tr>{''.join(cells)}</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{''.join(body)}"
        "</w:tbl>"
    )


def image_block(rel_id: str, name: str, width_px: int, height_px: int, docpr_id: int, max_width_inches: float = 6.4) -> str:
    max_cx = int(max_width_inches * 914400)
    cx = min(max_cx, int(width_px * 9525))
    cy = int(height_px * (cx / width_px))
    return (
        "<w:p>"
        "<w:r>"
        "<w:drawing>"
        "<wp:inline distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">"
        f"<wp:extent cx=\"{cx}\" cy=\"{cy}\"/>"
        "<wp:effectExtent l=\"0\" t=\"0\" r=\"0\" b=\"0\"/>"
        f"<wp:docPr id=\"{docpr_id}\" name=\"Picture{docpr_id}\" descr=\"figure\"/>"
        "<wp:cNvGraphicFramePr/>"
        "<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
        "<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:nvPicPr>"
        f"<pic:cNvPr id=\"0\" name=\"{xml_text(name)}\"/>"
        "<pic:cNvPicPr/>"
        "</pic:nvPicPr>"
        "<pic:blipFill>"
        f"<a:blip r:embed=\"{rel_id}\"/>"
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr>"
        "<a:xfrm>"
        "<a:off x=\"0\" y=\"0\"/>"
        f"<a:ext cx=\"{cx}\" cy=\"{cy}\"/>"
        "</a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "</pic:spPr>"
        "</pic:pic>"
        "</a:graphicData>"
        "</a:graphic>"
        "</wp:inline>"
        "</w:drawing>"
        "</w:r>"
        "</w:p>"
    )


def build_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="24"/></w:rPr>
  </w:style>
</w:styles>
"""


def build_content_types_xml(image_count: int) -> str:
    extra = ""
    if image_count:
        extra += '<Default Extension="png" ContentType="image/png"/>'
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  {extra}
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def build_root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def build_core_xml(title: str) -> str:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{xml_text(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def build_app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>
"""


def build_document_xml(body_parts: list[str]) -> str:
    ns_attrs = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document {ns_attrs} mc:Ignorable="w14 wp14">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def build_document_rels(image_names: list[str]) -> str:
    rels = [
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    for idx, image_name in enumerate(image_names, start=1):
        rels.append(
            f'<Relationship Id="rIdImg{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{image_name}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )


def main() -> None:
    args = parse_args()
    comparison_root = Path(args.comparison_root)
    overall_rows = load_csv(Path(args.overall_csv))
    per_flight_rows = load_csv(Path(args.per_flight_csv))
    figures_dir = Path(args.figures_dir)
    output_docx = Path(args.output_docx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    overall = {row["method"]: row for row in overall_rows}
    best_acc = "pooler"
    cls_gain = pct_faster(float(overall["pooler"]["total_ms_mean"]), float(overall["cls"]["total_ms_mean"]))
    mean_gain = pct_faster(float(overall["pooler"]["total_ms_mean"]), float(overall["mean"]["total_ms_mean"]))
    gem_gain = pct_faster(float(overall["pooler"]["total_ms_mean"]), float(overall["gem"]["total_ms_mean"]))
    mean_err_gain = pct_lower(float(overall["pooler"]["top1_error_m_mean"]), float(overall["mean"]["top1_error_m_mean"]))
    gem_err_gain = pct_lower(float(overall["pooler"]["top1_error_m_mean"]), float(overall["gem"]["top1_error_m_mean"]))

    body = []
    title = "DINOv2不同Pooling策略跨视角粗定位对比实验汇报"
    body.append(paragraph(title, style="Title"))
    body.append(paragraph("项目：GNSS拒止环境下无人机视觉定位全局粗定位模块", bold=True))
    body.append(paragraph(f"日期：{dt.date.today().isoformat()}"))

    body.append(paragraph("一、实验目的", style="Heading1"))
    body.append(paragraph(
        "在既有DINOv2+FAISS PoC基础上，比较 pooler、CLS token、mean pooling、GeM pooling 四种全局聚合方式对无人机-卫星跨视角粗检索定位性能、定位误差和时延的影响。"
    ))

    body.append(paragraph("二、实验设置", style="Heading1"))
    body.append(paragraph(
        "1. 数据与查询集：沿用 validation_round3_200m_fair 的 4 条航线、20 个 200m 查询块。"
        "\n2. 模型与检索：统一使用 facebook/dinov2-base、L2 normalize、FAISS IndexFlatIP。"
        "\n3. 对比变量：仅替换全局聚合方式，其余数据、真值、索引类型和评估口径保持一致。"
        "\n4. 指标：Recall@1、Recall@5、Recall@10、MRR、Top-1定位误差（米）、单次特征提取/检索/总耗时。"
    ))

    body.append(paragraph("三、总体结果表", style="Heading1"))
    overall_table = [
        ["方法", "R@1", "R@5", "R@10", "MRR", "Top-1误差(m)", "特征耗时(ms)", "检索耗时(ms)", "总耗时(ms)"]
    ]
    for method in ["pooler", "cls", "mean", "gem"]:
        row = overall[method]
        overall_table.append(
            [
                method.upper(),
                f"{float(row['recall@1']):.2f}",
                f"{float(row['recall@5']):.2f}",
                f"{float(row['recall@10']):.2f}",
                f"{float(row['mrr']):.3f}",
                f"{float(row['top1_error_m_mean']):.2f}",
                f"{float(row['feature_ms_mean']):.2f}",
                f"{float(row['retrieval_ms_mean']):.2f}",
                f"{float(row['total_ms_mean']):.2f}",
            ]
        )
    body.append(table(overall_table))

    body.append(paragraph("四、关键图表", style="Heading1"))
    figure_names = [
        ("overall_recall_bar.png", "图1 总体召回率对比"),
        ("overall_dashboard.png", "图2 总体指标总览"),
        ("per_flight_accuracy_heatmaps.png", "图3 分航线精度热力图"),
        ("per_flight_error_latency_heatmaps.png", "图4 分航线误差与时延热力图"),
        ("speed_accuracy_tradeoff.png", "图5 精度-速度折中关系"),
    ]

    image_payloads: list[tuple[str, bytes, int, int, str]] = []
    for idx, (filename, caption) in enumerate(figure_names, start=1):
        img_path = figures_dir / filename
        data = img_path.read_bytes()
        with Image.open(BytesIO(data)) as img:
            width_px, height_px = img.size
        image_payloads.append((f"image{idx}.png", data, width_px, height_px, caption))

    for idx, (_, _, width_px, height_px, caption) in enumerate(image_payloads, start=1):
        body.append(paragraph(caption, style="Heading2"))
        body.append(image_block(f"rIdImg{idx}", caption, width_px, height_px, docpr_id=idx))

    body.append(paragraph("五、面向汇报的主要结论", style="Heading1"))
    body.append(paragraph(
        f"1. 准确率层面，POOLER 与 CLS 完全一致：两者总体均为 R@1=0.50、R@5=0.80、R@10=0.90、MRR=0.601，说明在当前任务与实现下，CLS 可视为与现有基线等效的替代方案。"
        f"\n2. 速度层面，CLS 明显优于 POOLER：CLS 的单次总耗时为 {float(overall['cls']['total_ms_mean']):.2f} ms，相比 POOLER 的 {float(overall['pooler']['total_ms_mean']):.2f} ms 提升约 {cls_gain:.1f}%。在准确率不变的前提下，CLS 是更优的工程选择。"
        f"\n3. MEAN 与 GEM 的推理更快：MEAN 和 GEM 的单次总耗时分别较 POOLER 下降约 {mean_gain:.1f}% 和 {gem_gain:.1f}%。"
        f"\n4. 但 MEAN 与 GEM 的召回能力下降：两者总体 R@1 都从 0.50 降至 0.35，说明以 patch-token 聚合替代现有全局表示后，粗检索稳定性减弱。"
        f"\n5. 定位误差层面，MEAN 与 GEM 更小：MEAN 与 GEM 的 Top-1 误差均值分别比 POOLER 下降约 {mean_err_gain:.1f}% 和 {gem_err_gain:.1f}%。这说明它们在命中时可能更贴近正确位置，但整体召回更差。"
        "\n6. 分航线表现表明，MEAN 与 GEM 的退化主要集中在 011 和 012 航线，说明弱结构或更难场景下，POOLER/CLS 的鲁棒性更强。"
    ))

    body.append(paragraph("六、结论与建议", style="Heading1"))
    body.append(paragraph(
        "结论：若目标是维持当前 PoC 的粗召回能力，CLS 是最优替代方案，因为它与 POOLER 准确率一致但速度更快。"
        "\n建议1：后续默认以 CLS 作为新的主基线。"
        "\n建议2：MEAN 和 GEM 不建议直接替代当前主链路，但可作为后续精排或误差收敛方向的参考。"
        "\n建议3：如果后续继续扩展研究，可考虑在 CLS 粗检索后叠加局部几何验证或重排序，以兼顾召回和定位精度。"
    ))

    per_flight_table = [["方法", "航线", "R@1", "R@5", "R@10", "MRR", "Top-1误差(m)", "总耗时(ms)"]]
    for row in per_flight_rows:
        per_flight_table.append(
            [
                row["method"].upper(),
                short_flight(row["flight_id"]),
                f"{float(row['recall@1']):.2f}",
                f"{float(row['recall@5']):.2f}",
                f"{float(row['recall@10']):.2f}",
                f"{float(row['mrr']):.3f}",
                f"{float(row['top1_error_m_mean']):.1f}",
                f"{float(row['total_ms_mean']):.1f}",
            ]
        )
    body.append(paragraph("附录：分航线结果表", style="Heading1"))
    body.append(table(per_flight_table))

    image_names = [item[0] for item in image_payloads]

    with zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", build_content_types_xml(len(image_names)))
        zf.writestr("_rels/.rels", build_root_rels())
        zf.writestr("docProps/core.xml", build_core_xml(title))
        zf.writestr("docProps/app.xml", build_app_xml())
        zf.writestr("word/styles.xml", build_styles_xml())
        zf.writestr("word/document.xml", build_document_xml(body))
        zf.writestr("word/_rels/document.xml.rels", build_document_rels(image_names))
        for image_name, data, _, _, _ in image_payloads:
            zf.writestr(f"word/media/{image_name}", data)

    print(f"Report written to {output_docx}")


if __name__ == "__main__":
    main()
