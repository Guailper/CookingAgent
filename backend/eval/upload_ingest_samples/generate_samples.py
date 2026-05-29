"""Generate upload ingestion evaluation files.

The generated DOCX files are intentionally simple and dependency-free so they
can be recreated in any Python environment. They are meant for manual upload
testing of attachment parsing, content validation, and knowledge-base ingestion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


OUTPUT_DIR = Path(__file__).resolve().parent

SAMPLES = {
    "01_recipe_should_ingest.docx": [
        "番茄炒蛋家庭菜谱",
        "食材：番茄 2 个，鸡蛋 3 个，葱花少许，盐 2 克，白糖 1 克。",
        "步骤：鸡蛋打散后先炒至凝固盛出。番茄切块下锅翻炒出汁，再倒回鸡蛋。",
        "调味：加入盐和少量白糖，最后撒葱花，适合进入烹饪知识库。",
    ],
    "02_business_report_should_reject.docx": [
        "季度经营复盘报告",
        "本季度营业收入同比增长，项目预算执行情况稳定。",
        "风险项包括供应商回款周期、市场投放转化率和人力成本控制。",
        "本文档不包含菜谱、烹饪流程、食材处理或厨房技巧。",
    ],
    "03_mixed_low_confidence_should_reject.docx": [
        "周末活动安排和午餐备注",
        "上午进行团队分享，下午整理项目计划和预算表。",
        "午餐可能订番茄炒蛋套餐，但没有提供食材、做法、烹饪步骤或可复用厨房知识。",
        "该文档主题混杂，适合作为低置信度或不确定样本。",
    ],
}


def main() -> None:
    for filename, paragraphs in SAMPLES.items():
        write_docx(OUTPUT_DIR / filename, paragraphs)

    unsupported_path = OUTPUT_DIR / "04_unsupported_plain_text_should_fail_upload.txt"
    unsupported_path.write_text(
        "\n".join(
            [
                "这个文件用于验证上传扩展名白名单。",
                "当前上传服务不接受 .txt，因此预期在上传阶段失败。",
            ]
        ),
        encoding="utf-8",
    )


def write_docx(path: Path, paragraphs: list[str]) -> None:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml())
        archive.writestr("_rels/.rels", package_relationships_xml())
        archive.writestr("docProps/core.xml", core_properties_xml(path.stem))
        archive.writestr("docProps/app.xml", app_properties_xml())
        archive.writestr("word/document.xml", document_xml(paragraphs))
        archive.writestr("word/_rels/document.xml.rels", document_relationships_xml())


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def package_relationships_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def core_properties_xml(title: str) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>CookingAgent upload ingestion eval</dc:creator>
  <cp:lastModifiedBy>CookingAgent upload ingestion eval</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created_at}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created_at}</dcterms:modified>
</cp:coreProperties>
"""


def app_properties_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>CookingAgent</Application>
</Properties>
"""


def document_relationships_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def document_xml(paragraphs: list[str]) -> str:
    rendered = "\n".join(render_paragraph(text) for text in paragraphs)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
{rendered}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def render_paragraph(text: str) -> str:
    return f"""    <w:p>
      <w:r>
        <w:t>{escape(text)}</w:t>
      </w:r>
    </w:p>"""


if __name__ == "__main__":
    main()
