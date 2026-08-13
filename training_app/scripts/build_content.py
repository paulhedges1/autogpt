"""
Parses the Modern Digital Workplace Training Academy source Word document
into a structured JSON content file consumed by the training app frontend.

Usage:
    python3 build_content.py <source.docx> <output.json>

The document is read in a single linear pass (paragraphs and tables in
document order) and grouped into modules, then into the nine standard
workbook sections used by every module. Content is converted into a small
set of typed "blocks" (heading / paragraph / list / checklist / input /
table / callout) that the frontend renders generically, plus two richer
structures (confidence scale, knowledge-check quiz) that the frontend turns
into real interactive widgets.
"""
import json
import re
import sys
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

SECTION_MARKERS = [
    ("introduction", re.compile(r"^1\.\s*Module introduction$", re.I)),
    ("lesson", re.compile(r"^2\.\s*Complete lesson$", re.I)),
    ("worked_example", re.compile(r"^3\.\s*Worked example$", re.I)),
    ("guided_practice", re.compile(r"^4\.\s*Guided practice$", re.I)),
    ("independent_challenge", re.compile(r"^5\.\s*.*Independent Challenge$", re.I)),
    ("knowledge_check", re.compile(r"^6\.\s*Check your learning$", re.I)),
    ("answers_feedback", re.compile(r"^7\.\s*Answers and feedback$", re.I)),
    ("confidence_reflection", re.compile(r"^8\.\s*Confidence and reflection$", re.I)),
]
QUICK_REF_MARKER = re.compile(r"quick reference$", re.I)
MODULE_MARKER = re.compile(r"^MODULE\s+1\.(\d+)\s*\n(.+)$", re.S)
CAPSTONE_MARKER = re.compile(r"^Volume 1 completion review$", re.I)
KC_ANSWERS_MARKER = re.compile(r"Knowledge check answers", re.I)


def iter_body_items(doc):
    """Yield ('p', paragraph) / ('t', table) in document order."""
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield "p", Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield "t", Table(child, doc)


def heading_level(p):
    name = p.style.name if p.style else ""
    m = re.match(r"Heading (\d)", name or "")
    return int(m.group(1)) if m else None


def clean(text):
    return re.sub(r"[ \t]+", " ", text.strip())


def split_checkbox_line(text):
    """A paragraph like '☐ Safe to try   ☐ Ask first   ☐ Stop' -> list of options."""
    parts = [clean(x) for x in text.split("☐") if clean(x)]
    return parts


class BlockBuilder:
    """Turns a flat item list (already sliced to one section) into typed blocks."""

    def __init__(self, module_id, section_key):
        self.module_id = module_id
        self.section_key = section_key
        self.blocks = []
        self._counter = 0
        self._pending_checklist = None

    def _new_id(self):
        self._counter += 1
        return f"{self.module_id}.{self.section_key}.{self._counter}"

    def _flush_checklist(self):
        if self._pending_checklist:
            self.blocks.append(self._pending_checklist)
            self._pending_checklist = None

    def add_heading(self, level, text):
        self._flush_checklist()
        self.blocks.append({"type": "heading", "level": level, "text": clean(text), "id": self._new_id()})

    def add_paragraph(self, text):
        text = text.strip()
        if not text:
            return
        if "☐" in text:
            opts = split_checkbox_line(text)
            if opts:
                if self._pending_checklist is None:
                    self._pending_checklist = {"type": "checklist", "id": self._new_id(), "items": []}
                self._pending_checklist["items"].append(opts if len(opts) > 1 else opts[0])
                return
        self._flush_checklist()
        # bullet / numbered list paragraphs from python-docx retain the visible text only;
        # detect simple leading markers left in text (e.g. "1.  ") and keep as-is, rendered as paragraph.
        self.blocks.append({"type": "paragraph", "text": clean(text), "id": self._new_id()})

    def add_table(self, table):
        self._flush_checklist()
        rows = [[c.text.strip() for c in r.cells] for r in table.rows]
        # Single cell, empty -> fill-in input box
        if len(rows) == 1 and len(rows[0]) == 1:
            cell_text = rows[0][0]
            if cell_text == "":
                self.blocks.append({"type": "input", "id": self._new_id(), "multiline": True})
                return
            # Single cell, non-empty -> callout note (often "Label\nBody")
            first_line, _, rest = cell_text.partition("\n")
            self.blocks.append({
                "type": "callout",
                "id": self._new_id(),
                "label": clean(first_line),
                "text": clean(rest) if rest else "",
            })
            return
        self.blocks.append({"type": "table", "id": self._new_id(), "rows": rows})

    def finish(self):
        self._flush_checklist()
        return self.blocks


def build_confidence_widget(module_id, when):
    return {
        "type": "confidence",
        "id": f"{module_id}.confidence.{when}",
        "when": when,
        "scale": [
            {"value": 1, "label": "Very unsure"},
            {"value": 2, "label": "Unsure"},
            {"value": 3, "label": "Not sure yet"},
            {"value": 4, "label": "Quite confident"},
            {"value": 5, "label": "Very confident"},
        ],
    }


def parse_overview_table(rows):
    return [{"label": clean(r[0]), "value": clean(r[1])} for r in rows if len(r) >= 2]


SIMPLE_QUESTION = re.compile(r"^(\d+)\.\s*(.*)$")
INLINE_ANSWER = re.compile(
    r"^(\d+)\.\s*(.*?)\s*Correct answer:\s*(.*?)(?:\s*If different.*)?$", re.I | re.S
)


def parse_knowledge_check_rich(items):
    """Format A (module 1.1): Heading2 questions, optional tick options, separate score table."""
    questions = []
    intro_blocks = []
    score_table = None
    current = None

    def flush():
        nonlocal current
        if current:
            questions.append(current)
            current = None

    seen_first_heading = False
    for kind, obj in items:
        if kind == "p":
            lvl = heading_level(obj)
            text = obj.text.strip()
            if not text:
                continue
            if lvl == 1:
                continue
            if lvl == 2:
                if text.strip().lower() == "knowledge score":
                    flush()
                    current = {"_score_marker": True}
                    seen_first_heading = True
                    continue
                flush()
                seen_first_heading = True
                m = re.match(r"^(\d+)\.\s*(.*)$", text)
                number = int(m.group(1)) if m else len(questions) + 1
                stem = m.group(2) if m else text
                current = {
                    "number": number,
                    "prompt": clean(stem),
                    "options": [],
                    "multi": bool(re.search(r"tick two|tick 2", stem, re.I)),
                    "kind": "choice",
                }
                continue
            if not seen_first_heading:
                intro_blocks.append(("p", text))
                continue
            if current is None:
                continue
            if current.get("_score_marker"):
                continue
            if "☐" in text:
                opts = split_checkbox_line(text)
                current["options"].extend(opts)
            else:
                current.setdefault("free_text", [])
                current["free_text"].append(clean(text))
                current["kind"] = "open"
        else:  # table
            rows = [[c.text.strip() for c in r.cells] for r in obj.rows]
            if current and current.get("_score_marker"):
                score_table = rows
                current = None
                continue
            if current is None:
                if not seen_first_heading:
                    intro_blocks.append(("t", rows))
                continue
            # blank spacer table under a question -> ignore (answer goes in the app UI)
    flush()
    questions = [q for q in questions if not q.get("_score_marker")]
    return intro_blocks, questions, score_table


def parse_knowledge_check_simple(items):
    """Format B (modules 1.2-1.9): plain numbered open questions, no options, no score table."""
    questions = []
    intro_blocks = []
    for kind, obj in items:
        if kind == "p":
            text = obj.text.strip()
            if not text:
                continue
            m = SIMPLE_QUESTION.match(text)
            if m and heading_level(obj) != 1:
                questions.append({
                    "number": int(m.group(1)),
                    "prompt": clean(m.group(2)),
                    "options": [],
                    "multi": False,
                    "kind": "open",
                })
            elif heading_level(obj) == 1:
                continue
            else:
                intro_blocks.append(("p", text))
        # blank answer-space tables are ignored; the app renders its own input box
    return intro_blocks, questions, None


def attach_answers(questions, answers_by_number):
    for q in questions:
        ans = answers_by_number.get(q["number"])
        if not ans:
            continue
        q["correct_answer_text"] = ans["correct_answer"]
        q["where_taught"] = ans.get("where_taught", "")
        q["points"] = ans.get("points", "")
        if q["options"]:
            correct_idx = []
            for i, opt in enumerate(q["options"]):
                norm_opt = opt.lower().strip(" .")
                if norm_opt and norm_opt in ans["correct_answer"].lower():
                    correct_idx.append(i)
            if correct_idx:
                q["correct_indices"] = correct_idx
    return questions


def parse_knowledge_check(items, module_id, answers_by_number):
    has_rich = any(kind == "p" and heading_level(obj) == 2 for kind, obj in items)
    if has_rich:
        intro, questions, score_table = parse_knowledge_check_rich(items)
    else:
        intro, questions, score_table = parse_knowledge_check_simple(items)
    questions = attach_answers(questions, answers_by_number)
    for q in questions:
        if not q["options"]:
            q["kind"] = "open"
    return intro, questions, score_table


def parse_inline_answers(items):
    """Format B answers: 'N. <question> Correct answer: <answer>. If different, ...' inline in section 7."""
    result = {}
    for kind, obj in items:
        if kind != "p":
            continue
        text = obj.text.strip()
        if "Correct answer:" not in text:
            continue
        m = INLINE_ANSWER.match(text)
        if m:
            result[int(m.group(1))] = {
                "correct_answer": clean(m.group(3)),
                "where_taught": "",
                "points": "4",
            }
    return result


def parse_knowledge_answers(items):
    """Find the answers table inside the answers_feedback section items."""
    result = {}
    trigger = False
    for kind, obj in items:
        if kind == "p" and heading_level(obj) == 2 and KC_ANSWERS_MARKER.search(obj.text):
            trigger = True
            continue
        if kind == "t" and trigger:
            rows = [[c.text.strip() for c in r.cells] for r in obj.rows]
            header = [c.lower() for c in rows[0]] if rows else []
            if header and "question" in header[0]:
                for r in rows[1:]:
                    if len(r) < 4:
                        continue
                    try:
                        qnum = int(re.sub(r"\D", "", r[0]) or 0)
                    except ValueError:
                        continue
                    result[qnum] = {
                        "correct_answer": clean(r[1]),
                        "where_taught": clean(r[2]),
                        "points": clean(r[3]),
                    }
            trigger = False
    return result


def slugify(text):
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-")


CONFIDENCE_SCALE_TEXT = re.compile(r"^(Confidence (before|after) the module:?\s*)?[\d\s]+$", re.I)


def is_overview_table(block):
    if block["type"] != "table" or not block["rows"]:
        return False
    header = block["rows"][0][0].lower() if block["rows"][0] else ""
    return header in ("what you will learn", "module information")


def is_confidence_scale_block(block):
    if block["type"] == "paragraph":
        return bool(CONFIDENCE_SCALE_TEXT.match(block["text"]))
    if block["type"] == "table":
        flat = " ".join(c for row in block["rows"] for c in row)
        return "☐" in flat and re.search(r"very unsure", flat, re.I) is not None
    return False


def is_module_title_paragraph(block):
    return block["type"] == "paragraph" and block["text"].startswith("MODULE 1.")


def clean_section_blocks(blocks, drop_title=False, drop_overview=False, drop_confidence=False):
    out = []
    for i, b in enumerate(blocks):
        if drop_title and i == 0 and is_module_title_paragraph(b):
            continue
        if drop_overview and is_overview_table(b):
            continue
        if drop_confidence and is_confidence_scale_block(b):
            continue
        out.append(b)
    return out


def render_generic_blocks(items, module_id, section_key):
    bb = BlockBuilder(module_id, section_key)
    for kind, obj in items:
        if kind == "p":
            lvl = heading_level(obj)
            text = obj.text
            if not text.strip():
                continue
            if lvl:
                bb.add_heading(lvl, text)
            else:
                bb.add_paragraph(text)
        else:
            bb.add_table(obj)
    return bb.finish()


def main():
    src, out = sys.argv[1], sys.argv[2]
    doc = Document(src)
    all_items = list(iter_body_items(doc))

    # Locate module boundaries
    module_starts = []  # (module_number, start_index, title_text)
    for i, (kind, obj) in enumerate(all_items):
        if kind != "p":
            continue
        m = MODULE_MARKER.match(obj.text.strip())
        if m:
            module_starts.append((int(m.group(1)), i, obj.text.strip()))
    # Module 1.1 has no MODULE marker paragraph (its title is in a cover table); it starts at doc start.
    module_starts.insert(0, (1, 0, "MODULE 1.1"))

    capstone_start = None
    for i, (kind, obj) in enumerate(all_items):
        if kind == "p" and heading_level(obj) == 1 and CAPSTONE_MARKER.match(obj.text.strip()):
            capstone_start = i
            break

    module_titles = {
        1: "Digital Confidence and Safe Actions",
        2: "Windows Navigation and Controlling Application Windows",
        3: "Files, Folders, Searching and Professional Naming",
        4: "Microsoft Word Foundations",
        5: "Reviewing and Finalising Word Documents",
        6: "Microsoft Excel Foundations",
        7: "Excel Formulas, Checking and Simple Charts",
        8: "Internet Research and Checking Sources",
        9: "Everyday Troubleshooting",
    }

    modules_out = []
    for idx, (num, start, _title) in enumerate(module_starts):
        end = module_starts[idx + 1][1] if idx + 1 < len(module_starts) else (capstone_start or len(all_items))
        items = all_items[start:end]
        module_id = f"1.{num}"
        title = module_titles.get(num, f"Module {module_id}")

        # Find section boundaries within this module by heading text.
        bounds = []  # (key, item_index)
        for i, (kind, obj) in enumerate(items):
            if kind != "p":
                continue
            lvl = heading_level(obj)
            text = obj.text.strip()
            if lvl == 1:
                for key, pattern in SECTION_MARKERS:
                    if pattern.match(text):
                        bounds.append((key, i))
                        break
                else:
                    if QUICK_REF_MARKER.search(text):
                        bounds.append(("quick_reference", i))
        if not any(b[0] == "introduction" for b in bounds):
            # Modules 1.2-1.9 have no explicit "1. Module introduction" heading; the module
            # title/purpose/overview table sits directly at the start of the module's items.
            bounds.append(("introduction", 0))

        bounds.sort(key=lambda b: b[1])
        section_items = {}
        for j, (key, i0) in enumerate(bounds):
            i1 = bounds[j + 1][1] if j + 1 < len(bounds) else len(items)
            section_items.setdefault(key, []).extend(items[i0:i1])

        overview_rows = []
        for kind, obj in section_items.get("introduction", []):
            if kind == "t":
                rows = [[c.text.strip() for c in r.cells] for r in obj.rows]
                if rows and len(rows[0]) == 2 and rows[0][0].lower() in ("what you will learn", "module information"):
                    overview_rows = parse_overview_table(rows if rows[0][0].lower() != "module information" else rows[1:])

        answers_items = section_items.get("answers_feedback", [])
        kc_answer_map = parse_knowledge_answers(answers_items)
        if not kc_answer_map:
            kc_answer_map = parse_inline_answers(answers_items)

        kc_items = section_items.get("knowledge_check", [])
        kc_intro, kc_questions, kc_score_table = parse_knowledge_check(kc_items, module_id, kc_answer_map)

        sections_out = {}
        for key in ["introduction", "lesson", "worked_example", "guided_practice",
                    "independent_challenge", "answers_feedback", "confidence_reflection", "quick_reference"]:
            raw = section_items.get(key, [])
            sections_out[key] = render_generic_blocks(raw, module_id, key)

        sections_out["introduction"] = clean_section_blocks(
            sections_out["introduction"], drop_title=True, drop_overview=True, drop_confidence=True
        )
        sections_out["confidence_reflection"] = clean_section_blocks(
            sections_out["confidence_reflection"], drop_confidence=True
        )

        intro_blocks_simple = []
        for j, (kind, val) in enumerate(kc_intro):
            bid = f"{module_id}.knowledge_check_intro.{j}"
            if kind == "p":
                intro_blocks_simple.append({"type": "paragraph", "text": clean(val), "id": bid})
            elif len(val) == 1 and len(val[0]) == 1 and val[0][0].strip():
                first_line, _, rest = val[0][0].strip().partition("\n")
                intro_blocks_simple.append({
                    "type": "callout", "id": bid,
                    "label": clean(first_line), "text": clean(rest) if rest else "",
                })
            elif not (len(val) == 1 and len(val[0]) == 1):
                intro_blocks_simple.append({"type": "table", "rows": val, "id": bid})

        sections_out["knowledge_check"] = {
            "intro_blocks": intro_blocks_simple,
            "questions": kc_questions,
            "score_table": kc_score_table,
        }

        modules_out.append({
            "id": module_id,
            "number": num,
            "slug": f"module-{num}-{slugify(title)}",
            "title": title,
            "overview": overview_rows,
            "confidence_before": build_confidence_widget(module_id, "before"),
            "confidence_after": build_confidence_widget(module_id, "after"),
            "sections": sections_out,
        })

    capstone_blocks = []
    if capstone_start is not None:
        capstone_blocks = render_generic_blocks(all_items[capstone_start:], "capstone", "review")

    content = {
        "meta": {
            "title": "The Modern Digital Workplace Training Academy",
            "subtitle": "Volume 1: Digital Foundations",
            "tagline": "Teach • Explain • Show • Practise • Check • Reflect",
        },
        "modules": modules_out,
        "capstone": {"title": "Volume 1 completion review", "blocks": capstone_blocks},
    }

    with open(out, "w") as f:
        json.dump(content, f, indent=2)
    print(f"Wrote {out}: {len(modules_out)} modules")
    for m in modules_out:
        qc = len(m["sections"]["knowledge_check"]["questions"])
        print(f"  {m['id']} {m['title']!r}: {qc} quiz questions")


if __name__ == "__main__":
    main()
