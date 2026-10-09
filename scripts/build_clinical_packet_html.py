"""Turn docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md into a printable HTML file (open it in a browser, Print, Save as PDF).

No dependencies. Handles the Markdown this packet uses: headings, tables, bullet/numbered lists, bold, italics, inline code, rules.
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "clinical" / "BUBBLES_CLINICAL_REVIEW_PACKET.md"
OUT = SRC.with_suffix(".html")


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def convert(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    list_tag = None

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            close_list()
            head = [c.strip() for c in line.strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            close_list()
            n = len(m[1])
            out.append(f"<h{n}>{inline(m[2])}</h{n}>")
        elif re.match(r"^\s*[-*]\s+", line):
            if list_tag != "ul":
                close_list(); out.append("<ul>"); list_tag = "ul"
            out.append(f"<li>{inline(re.sub(r'^\s*[-*]\s+', '', line))}</li>")
        elif re.match(r"^\s*\d+\.\s+", line):
            if list_tag != "ol":
                close_list(); out.append("<ol>"); list_tag = "ol"
            out.append(f"<li>{inline(re.sub(r'^\s*\d+\.\s+', '', line))}</li>")
        elif line.strip() == "---":
            close_list(); out.append("<hr>")
        elif not line.strip():
            close_list()
        else:
            close_list(); out.append(f"<p>{inline(line)}</p>")
        i += 1
    close_list()
    return "\n".join(out)


STYLE = """body{font-family:Georgia,serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222;line-height:1.5}
h1,h2,h3{font-family:Arial,sans-serif}h1{border-bottom:3px solid #6A45F5}h2{margin-top:2rem;border-bottom:1px solid #ccc}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}th,td{border:1px solid #bbb;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{background:#f1ecff}code{background:#f4f4f4;padding:0 .2rem;font-size:.85em}hr{border:0;border-top:1px solid #ccc}
@media print{body{max-width:none;margin:0}h2{page-break-after:avoid}table,tr{page-break-inside:avoid}}"""

if __name__ == "__main__":
    body = convert(SRC.read_text(encoding="utf-8"))
    OUT.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Bubbles Clinical Review Packet</title><style>{STYLE}</style></head><body>{body}</body></html>", encoding="utf-8")
    print("wrote", OUT, len(body), "bytes of body")
