#!/usr/bin/env python3
"""Generate per-method Word docs for pooling ideas and experiment steps."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import zipfile
from pathlib import Path


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
}


METHOD_DESC = {
    "pooler": {
        "title": "POOLER方法思想与实验步骤说明",
        "idea": "POOLER 方法直接使用 DINOv2 模型输出的 pooler_output 作为图像全局描述子。它代表当前 PoC 的主基线实现，重点在于保留模型原生的全局语义表示能力，尽量不额外改变特征聚合机制。",
        "feature": "在本实验中，卫星瓦片和无人机查询图都经过同一个 DINOv2-base 模型，并统一取 pooler_output，再做 L2 归一化后进入 FAISS 内积索引检索。",
        "note": "POOLER 是当前最重要的基线方法，适合用来衡量其他 pooling 方案是否真正带来收益。",
    },
    "cls": {
        "title": "CLS Token方法思想与实验步骤说明",
        "idea": "CLS 方法直接取 DINOv2 最后一层输出中的 CLS token 作为全局描述子。其核心思想是利用 Transformer 中专门承担全局汇聚作用的分类标记来代表整幅图像。",
        "feature": "在本实验中，卫星瓦片和无人机查询图都经过同一个 DINOv2-base 模型，并统一取 last_hidden_state[:, 0] 作为全局特征，再做 L2 归一化与 FAISS 检索。",
        "note": "CLS 的意义在于验证：不依赖 pooler_output，仅依赖显式 CLS token，是否仍能维持跨视角粗检索性能。",
    },
    "mean": {
        "title": "Mean Pooling方法思想与实验步骤说明",
        "idea": "Mean Pooling 方法对 DINOv2 最后一层的 patch tokens 做平均池化，用所有局部 token 的均值来构成全局图像描述子。它强调把整幅图像的局部信息平均整合到一个向量中。",
        "feature": "在本实验中，卫星瓦片和无人机查询图都统一取 patch tokens，再沿 token 维度做 mean pooling，之后做 L2 归一化并进入 FAISS 检索。",
        "note": "Mean Pooling 的价值在于检验：相比单点式的 CLS 表示，均值聚合是否能更好吸收局部结构信息。",
    },
    "gem": {
        "title": "GeM Pooling方法思想与实验步骤说明",
        "idea": "GeM Pooling 可以看成是介于平均池化和最大池化之间的一种广义池化方式。它通过指数参数 p 控制对高响应 token 的强调程度，从而在保留整体信息的同时突出更显著的局部区域。",
        "feature": "在本实验中，卫星瓦片和无人机查询图都对 patch tokens 做 GeM 聚合，参数 p 固定为 3.0，然后做 L2 归一化与 FAISS 检索。",
        "note": "GeM 常用于图像检索场景，因此这里对比它的目的，是验证它在无人机-卫星跨视角粗定位中能否兼顾召回与定位误差。",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate method-specific pooling Word docs.")
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--overall-csv", required=True)
    parser.add_argument("--per-flight-csv", required=True)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def xml_text(text: str) -> str:
    return html.escape(text, quote=False)


def paragraph(text: str = "", style: str | None = None, bold: bool = False) -> str:
    runs = []
    for idx, chunk in enumerate(text.split("\n")):
        if idx:
            runs.append("<w:r><w:br/></w:r>")
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        runs.append(f"<w:r>{rpr}<w:t xml:space=\"preserve\">{xml_text(chunk)}</w:t></w:r>")
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def table(rows: list[list[str]]) -> str:
    col_count = max(len(r) for r in rows)
    grid = "".join("<w:gridCol w:w=\"1700\"/>" for _ in range(col_count))
    trs = []
    for ridx, row in enumerate(rows):
        tcs = []
        for cell in row:
            shade = "<w:shd w:fill=\"DCE6F1\"/>" if ridx == 0 else ""
            tcs.append(
                "<w:tc><w:tcPr><w:tcW w:w=\"1700\" w:type=\"dxa\"/>"
                f"{shade}</w:tcPr>{paragraph(cell, bold=(ridx == 0))}</w:tc>"
            )
        trs.append(f"<w:tr>{''.join(tcs)}</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{''.join(trs)}"
        "</w:tbl>"
    )


def build_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:rPr><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
</w:styles>"""


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
</w:document>"""


def build_content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def build_root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def build_doc_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def build_core_xml(title: str) -> str:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{xml_text(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def build_app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>"""


def write_docx(path: Path, title: str, body_parts: list[str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", build_content_types())
        zf.writestr("_rels/.rels", build_root_rels())
        zf.writestr("docProps/core.xml", build_core_xml(title))
        zf.writestr("docProps/app.xml", build_app_xml())
        zf.writestr("word/styles.xml", build_styles_xml())
        zf.writestr("word/document.xml", build_document_xml(body_parts))
        zf.writestr("word/_rels/document.xml.rels", build_doc_rels())


def flight_short_name(flight_id: str) -> str:
    parts = flight_id.split("_")
    return parts[2] if len(parts) >= 3 else flight_id


def main() -> None:
    args = parse_args()
    comparison_root = Path(args.comparison_root)
    overall_rows = {row["method"]: row for row in load_csv(Path(args.overall_csv))}
    per_flight_rows = load_csv(Path(args.per_flight_csv))

    for method in ["pooler", "cls", "mean", "gem"]:
        meta = METHOD_DESC[method]
        overall = overall_rows[method]
        flight_rows = [row for row in per_flight_rows if row["method"] == method]
        body = []
        body.append(paragraph(meta["title"], style="Title"))
        body.append(paragraph(f"日期：{dt.date.today().isoformat()}"))

        body.append(paragraph("一、方法思想", style="Heading1"))
        body.append(paragraph(meta["idea"]))
        body.append(paragraph(meta["feature"]))
        body.append(paragraph(meta["note"]))

        body.append(paragraph("二、在当前实验中的具体处理链路", style="Heading1"))
        body.append(paragraph(
            "1. 读取当前公平查询集和既有卫星瓦片库。"
            "\n2. 卫星瓦片全部经过 DINOv2-base，并使用当前方法对应的 pooling 生成卫星全局特征。"
            "\n3. 用卫星特征建立 FAISS IndexFlatIP 索引。"
            "\n4. 无人机查询图也经过同一个 DINOv2-base，并使用同一种 pooling 生成查询特征。"
            "\n5. 对查询特征做 L2 归一化后，在同一索引中做 Top-K 检索。"
            "\n6. 根据统一的 truth_tile_ids 评估 Recall@1、Recall@5、Recall@10、MRR、Top-1定位误差及查询时延。"
        ))

        body.append(paragraph("三、实验步骤概述", style="Heading1"))
        body.append(paragraph(
            "1. 数据准备：复用 validation_round3_200m_fair 的 4 条航线、20 个 200m 查询块。"
            "\n2. 特征构建：生成该方法对应的卫星特征库。"
            "\n3. 索引建立：构建当前方法的 FAISS 内积索引。"
            "\n4. 查询提特征：对每条航线的查询图提取同类特征。"
            "\n5. 粗检索：输出 Top-10 候选卫星瓦片。"
            "\n6. 结果评估：统计总体与分航线指标。"
            "\n7. 时延统计：记录单次特征提取、单次检索和单次总耗时。"
        ))

        body.append(paragraph("四、该方法当前实验总体结果", style="Heading1"))
        overall_table = [
            ["指标", "数值"],
            ["Recall@1", f"{float(overall['recall@1']):.3f}"],
            ["Recall@5", f"{float(overall['recall@5']):.3f}"],
            ["Recall@10", f"{float(overall['recall@10']):.3f}"],
            ["MRR", f"{float(overall['mrr']):.3f}"],
            ["Top-1定位误差均值(m)", f"{float(overall['top1_error_m_mean']):.3f}"],
            ["单次特征提取均值(ms)", f"{float(overall['feature_ms_mean']):.3f}"],
            ["单次检索均值(ms)", f"{float(overall['retrieval_ms_mean']):.3f}"],
            ["单次总耗时均值(ms)", f"{float(overall['total_ms_mean']):.3f}"],
        ]
        body.append(table(overall_table))

        body.append(paragraph("五、分航线结果", style="Heading1"))
        flight_table = [["航线", "R@1", "R@5", "R@10", "MRR", "Top-1误差(m)", "总耗时(ms)"]]
        for row in flight_rows:
            flight_table.append(
                [
                    flight_short_name(row["flight_id"]),
                    f"{float(row['recall@1']):.3f}",
                    f"{float(row['recall@5']):.3f}",
                    f"{float(row['recall@10']):.3f}",
                    f"{float(row['mrr']):.3f}",
                    f"{float(row['top1_error_m_mean']):.3f}",
                    f"{float(row['total_ms_mean']):.3f}",
                ]
            )
        body.append(table(flight_table))

        body.append(paragraph("六、简要解读", style="Heading1"))
        if method in {"pooler", "cls"}:
            summary = "该方法在当前实验中属于召回表现最稳定的一组，尤其在 009 和 011 航线上保持较强的粗检索能力。"
        elif method == "mean":
            summary = "该方法速度较快且部分航线的 Top-1 误差更低，但总体召回能力下降，尤其在 011 和 012 航线出现明显退化。"
        else:
            summary = "该方法同样具备较快的推理速度，并在部分样本上给出更小的定位误差，但整体 Recall@1/5 仍低于 pooler/cls。"
        body.append(paragraph(summary))

        out_path = comparison_root / method / f"{method.upper()}方法思想与实验步骤_2026-03-12.docx"
        write_docx(out_path, meta["title"], body)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
