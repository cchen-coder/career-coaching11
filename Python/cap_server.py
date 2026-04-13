#!/usr/bin/env python3
"""
Career Action Plan PPTX Generator Server
Run: python cap_server.py
Listens on http://localhost:5050
Place BCG_CAP_Template.pptx in the same folder as this script.
"""

import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "BCG_CAP_Template.pptx")
PORT = 5050

# ── Webhook helper ────────────────────────────────────────────────────────────
# Call this anywhere in the server to fire a Make.com (or any) webhook.
# Replace the placeholder URL with the one Make.com gives you when you
# create a Custom Webhook trigger in a scenario.
#
# Example usage:
#   fire_webhook("https://hook.eu1.make.com/YOUR_ID", {
#       "event": "cap_exported",
#       "coachee_name": cap_data.get("client"),
#       "filename": filename
#   })
#
# The try/except means a down or misconfigured webhook never breaks
# the main PPTX export flow — it fails silently.

MAKE_WEBHOOK_CAP_EXPORTED   = ""   # paste your Make.com URL here
MAKE_WEBHOOK_STAGE_CHANGED  = ""   # paste your Make.com URL here
MAKE_WEBHOOK_SESSION_DONE   = ""   # paste your Make.com URL here

# ── Notion configuration ──────────────────────────────────────────────────────
# Paste your Notion integration token and database IDs here.
# Get token at: https://www.notion.so/my-integrations
# Get database IDs from the Notion URL (32-char string before ?v=)

NOTION_TOKEN       = os.environ.get("NOTION_TOKEN", "")
NOTION_COACHEES_DB = os.environ.get("NOTION_COACHEES_DB", "33ea644efe8b80e0b302de888b863208")
NOTION_SESSIONS_DB = os.environ.get("NOTION_SESSIONS_DB", "33ea644efe8b80a5b85befdbdd74b720")
NOTION_API         = "https://api.notion.com/v1"


def notion_request(method, path, body=None):
    """Make an authenticated request to the Notion API."""
    url = f"{NOTION_API}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise Exception(f"Notion API error {e.code}: {e.read().decode()}")


def notion_prop(page, name, default=""):
    """Safely extract a property value from a Notion page object."""
    props = page.get("properties", {})
    prop = props.get(name, {})
    ptype = prop.get("type", "")
    if ptype == "title":
        items = prop.get("title", [])
        return items[0]["plain_text"] if items else default
    if ptype == "rich_text":
        items = prop.get("rich_text", [])
        return items[0]["plain_text"] if items else default
    if ptype == "select":
        sel = prop.get("select")
        return sel["name"] if sel else default
    if ptype == "multi_select":
        return [s["name"] for s in prop.get("multi_select", [])]
    if ptype == "checkbox":
        return "Yes" if prop.get("checkbox") else "No"
    if ptype == "email":
        return prop.get("email") or default
    if ptype == "phone_number":
        return prop.get("phone_number") or default
    if ptype == "url":
        return prop.get("url") or default
    if ptype == "date":
        d = prop.get("date")
        return d["start"] if d else default
    if ptype == "number":
        return prop.get("number", default)
    return default


def fetch_coachee_from_notion(coachee_name):
    """Query Notion for a coachee by name and return mapped profile data."""
    body = {
        "filter": {
            "property": "Name",
            "title": {"equals": coachee_name}
        }
    }
    result = notion_request("POST", f"/databases/{NOTION_COACHEES_DB}/query", body)
    pages = result.get("results", [])
    if not pages:
        return None
    p = pages[0]
    notion_id = p["id"]

    # Fetch related sessions
    sessions_body = {
        "sorts": [{"property": "Session Number", "direction": "ascending"}]
    }
    sessions_result = notion_request("POST", f"/databases/{NOTION_SESSIONS_DB}/query", sessions_body)
    session_pages = sessions_result.get("results", [])

    session_list = []
    for s in session_pages:
        session_list.append({
            "date":    notion_prop(s, "Session Date"),
            "time":    notion_prop(s, "Session Time"),
            "title":   notion_prop(s, "Focus / Topic"),
            "status":  notion_prop(s, "Status", "Scheduled").lower(),
            "next":    notion_prop(s, "Next Steps"),
            "meetUrl": notion_prop(s, "Google Meet URL"),
            "capSent": notion_prop(s, "CAP Sent"),
        })

    tags = notion_prop(p, "Labels", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return {
        "notion_id":      notion_id,
        "name":           notion_prop(p, "Name"),
        "role":           notion_prop(p, "Role"),
        "email":          notion_prop(p, "Email"),
        "contact":        notion_prop(p, "Phone"),
        "stage":          notion_prop(p, "Stage"),
        "status":         notion_prop(p, "Status"),
        "urgency":        notion_prop(p, "Urgency"),
        "employment":     notion_prop(p, "Employment Status"),
        "industry":       notion_prop(p, "Industry"),
        "targetTitles":   notion_prop(p, "Target Job Titles"),
        "bookingPref":    notion_prop(p, "Booking Preference"),
        "assignedCoach":  notion_prop(p, "Assigned Coach"),
        "goal":           notion_prop(p, "Coaching Goal"),
        "progressStatus": notion_prop(p, "Overall Progress"),
        "outcome":        notion_prop(p, "Outcome"),
        "priority":       notion_prop(p, "Main Priority"),
        "risks":          notion_prop(p, "Key Risks"),
        "riasecCodes":    notion_prop(p, "RIASEC Codes"),
        "careerMatch":    notion_prop(p, "Career Direction Match"),
        "aiCoach":        notion_prop(p, "AI Career Coach"),
        "cvReceived":     notion_prop(p, "CV Received"),
        "linkedinProvided": notion_prop(p, "LinkedIn Provided"),
        "riasecDone":     notion_prop(p, "RIASEC Completed"),
        "s1date":         notion_prop(p, "Session 1 Date"),
        "s2date":         notion_prop(p, "Session 2 Date"),
        "s3date":         notion_prop(p, "Session 3 Date"),
        "tags":           tags,
        "start":          notion_prop(p, "Start Date"),
        "goals":          notion_prop(p, "Goals (GROW)"),
        "reality":        notion_prop(p, "Reality (GROW)"),
        "options":        notion_prop(p, "Options (GROW)"),
        "wayForward":     notion_prop(p, "Way Forward (GROW)"),
        "sessionList":    session_list,
    }


def fire_webhook(hook_url, payload):
    """POST a JSON payload to a webhook URL. Fails silently if unreachable."""
    if not hook_url:
        return  # no URL configured — skip quietly
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            hook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[Webhook] Failed to fire {hook_url}: {e}")


def esc(text):
    """Escape XML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def make_run(text, sz="1000", color="595959", bold=False):
    """Build a single <a:r> run with Montserrat font."""
    b_attr = ' b="1"' if bold else ' b="0"'
    return (
        f'<a:r>'
        f'<a:rPr{b_attr} i="0" lang="en-SG" sz="{sz}" u="none" cap="none" strike="noStrike">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="Montserrat"/>'
        f'<a:ea typeface="Montserrat"/>'
        f'<a:cs typeface="Montserrat"/>'
        f'<a:sym typeface="Montserrat"/>'
        f'</a:rPr>'
        f'<a:t>{esc(text)}</a:t>'
        f'</a:r>'
    )


def make_para(text, sz="1000", color="595959", bold=False, align="l"):
    """Build a full <a:p> paragraph."""
    run = make_run(text, sz=sz, color=color, bold=bold) if text else '<a:r><a:t/></a:r>'
    return (
        f'<a:p>'
        f'<a:pPr indent="0" lvl="0" marL="0" marR="0" rtl="0" algn="{align}">'
        f'<a:lnSpc><a:spcPct val="100000"/></a:lnSpc>'
        f'<a:spcBef><a:spcPts val="0"/></a:spcBef>'
        f'<a:spcAft><a:spcPts val="0"/></a:spcAft>'
        f'<a:buNone/>'
        f'</a:pPr>'
        f'{run}'
        f'<a:endParaRPr/>'
        f'</a:p>'
    )


def make_txbody(paragraphs_xml):
    """Wrap paragraphs in a full txBody."""
    return (
        f'<p:txBody>'
        f'<a:bodyPr anchorCtr="0" anchor="t" bIns="45700" lIns="91425" spcFirstLastPara="1" rIns="91425" wrap="square" tIns="45700">'
        f'<a:spAutoFit/>'
        f'</a:bodyPr>'
        f'<a:lstStyle/>'
        f'{paragraphs_xml}'
        f'</p:txBody>'
    )


def replace_txbody(xml, shape_id, new_txbody):
    """Replace the txBody of a shape identified by its cNvPr id."""
    pattern = (
        rf'(<p:sp>(?:(?!<p:sp>).)*?<p:cNvPr id="{shape_id}"[^/]*/>'
        rf'(?:(?!<p:sp>).)*?)<p:txBody>.*?</p:txBody>'
    )
    replacement = rf'\1{new_txbody}'
    result = re.sub(pattern, replacement, xml, flags=re.DOTALL)
    return result


def lines_to_paras(lines, sz="1000", color="595959"):
    """Convert a list of strings to consecutive paragraphs."""
    paras = ""
    for line in lines:
        paras += make_para(line.strip(), sz=sz, color=color)
    return paras


def fill_slide1(xml, cap):
    """Fill all placeholders on slide 1 (Session Summary)."""

    # Shape 67 — Client name field (top left, blank)
    xml = replace_txbody(xml, "67",
        make_txbody(make_para(cap.get("client", ""), sz="1000", color="1A1814")))

    # Shape 68 — Coach field
    xml = replace_txbody(xml, "68",
        make_txbody(make_para(cap.get("coach", "Sarah Chen"), sz="1000", color="1A1814")))

    # Shape 69 — Duration field
    xml = replace_txbody(xml, "69",
        make_txbody(make_para(cap.get("duration", "60 min"), sz="1000", color="1A1814")))

    # Shape 70 — Date field
    xml = replace_txbody(xml, "70",
        make_txbody(make_para(cap.get("date", ""), sz="1000", color="1A1814")))

    # Shape 71 — Career Interests (Top 3)
    interests = cap.get("career_interests", [])
    paras = lines_to_paras(interests if interests else ["—"], sz="1000", color="595959")
    xml = replace_txbody(xml, "71", make_txbody(paras))

    # Shape 72 — Target Sectors
    sectors = cap.get("target_sectors", [])
    paras = lines_to_paras(sectors if sectors else ["—"], sz="1000", color="595959")
    xml = replace_txbody(xml, "72", make_txbody(paras))

    # Shape 73 — Key Strengths
    strengths = cap.get("key_strengths", [])
    paras = lines_to_paras(strengths if strengths else ["—"], sz="1000", color="595959")
    xml = replace_txbody(xml, "73", make_txbody(paras))

    # Shape 74 — Development Areas
    dev_areas = cap.get("development_areas", [])
    paras = lines_to_paras(dev_areas if dev_areas else ["—"], sz="1000", color="595959")
    xml = replace_txbody(xml, "74", make_txbody(paras))

    # Shape 75 — Target Job Roles/Titles
    roles = cap.get("target_roles", [])
    paras = lines_to_paras(roles if roles else ["—"], sz="1000", color="595959")
    xml = replace_txbody(xml, "75", make_txbody(paras))

    # Shape 76 — Salary Range
    salary = cap.get("salary_range", "To be confirmed")
    xml = replace_txbody(xml, "76",
        make_txbody(make_para(salary, sz="1000", color="595959")))

    # Shape 77 — Value Proposition
    vp = cap.get("value_proposition", "")
    xml = replace_txbody(xml, "77",
        make_txbody(make_para(vp, sz="1000", color="595959")))

    # Shape 78 — Reality (Coaching Insights)
    reality = cap.get("reality", "")
    xml = replace_txbody(xml, "78",
        make_txbody(make_para(reality, sz="1000", color="595959", align="ctr")))

    # Shape 79 — Goals (Coaching Insights)
    goals = cap.get("goals", "")
    xml = replace_txbody(xml, "79",
        make_txbody(make_para(goals, sz="1000", color="595959", align="ctr")))

    # Shape 80 — Options (Coaching Insights)
    options = cap.get("options", "")
    xml = replace_txbody(xml, "80",
        make_txbody(make_para(options, sz="1000", color="595959", align="ctr")))

    # Shape 81 — Way Forward (Coaching Insights)
    way_forward = cap.get("way_forward", "")
    xml = replace_txbody(xml, "81",
        make_txbody(make_para(way_forward, sz="1000", color="595959", align="ctr")))

    # Shape 82 — spare/notes area
    notes = cap.get("coach_notes", "")
    xml = replace_txbody(xml, "82",
        make_txbody(make_para(notes, sz="1000", color="595959")))

    return xml


def fill_slide2(xml, cap):
    """Fill action item placeholders on slide 2 (Action Plan Timeline)."""

    def action_paras(items, label=":", sz="1100"):
        """Build the paragraph block for one action column."""
        paras = make_para(label, sz=sz, color="595959")
        for item in items[:3]:
            paras += make_para(item.strip(), sz=sz, color="595959")
            paras += make_para("", sz=sz, color="595959")  # spacer
        # pad to 3 items
        while len(items) < 3:
            paras += make_para("", sz=sz, color="595959")
            paras += make_para("", sz=sz, color="595959")
            items.append("")
        return paras

    # Shape 87 — Quick Wins (Immediate, col 1)
    qw = cap.get("quick_wins", ["", "", ""])
    xml = replace_txbody(xml, "87", make_txbody(action_paras(qw)))

    # Shape 88 — Active Preparation (Short Term, col 2)
    ap = cap.get("active_preparation", ["", "", ""])
    xml = replace_txbody(xml, "88", make_txbody(action_paras(ap)))

    # Shape 89 — Implementation & Outreach (Medium Term, col 3)
    io = cap.get("implementation_outreach", ["", "", ""])
    xml = replace_txbody(xml, "89", make_txbody(action_paras(io)))

    # Shape 90 — Sustained Effort (Long Term, col 4)
    se = cap.get("sustained_effort", ["", "", ""])
    xml = replace_txbody(xml, "90", make_txbody(action_paras(se)))

    return xml


def generate_pptx(cap_data: dict) -> bytes:
    """Clone the template, fill in data, return bytes of the populated .pptx."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_pptx = os.path.join(tmpdir, "CAP_filled.pptx")
        shutil.copy2(TEMPLATE_PATH, out_pptx)

        # Read the zip, modify slide XMLs, write back
        with zipfile.ZipFile(out_pptx, "r") as zin:
            names = zin.namelist()
            file_contents = {}
            for name in names:
                file_contents[name] = zin.read(name)

        # Modify slides
        slide1_key = "ppt/slides/slide1.xml"
        slide2_key = "ppt/slides/slide2.xml"

        if slide1_key in file_contents:
            s1 = file_contents[slide1_key].decode("utf-8")
            s1 = fill_slide1(s1, cap_data)
            file_contents[slide1_key] = s1.encode("utf-8")

        if slide2_key in file_contents:
            s2 = file_contents[slide2_key].decode("utf-8")
            s2 = fill_slide2(s2, cap_data)
            file_contents[slide2_key] = s2.encode("utf-8")

        # Write new zip
        out2 = os.path.join(tmpdir, "CAP_output.pptx")
        with zipfile.ZipFile(out2, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in names:
                zout.writestr(name, file_contents[name])

        with open(out2, "rb") as f:
            return f.read()


class CAPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[CAP Server] {format % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # GET /notion/coachee?name=James+Lee
        if self.path.startswith("/notion/coachee"):
            if not NOTION_TOKEN or not NOTION_COACHEES_DB:
                self._json_response({"error": "Notion not configured. Set NOTION_TOKEN and NOTION_COACHEES_DB in cap_server.py."}, 503)
                return
            from urllib.parse import urlparse, parse_qs, unquote_plus
            query = parse_qs(urlparse(self.path).query)
            name = unquote_plus(query.get("name", [""])[0])
            if not name:
                self._json_response({"error": "Missing ?name= parameter"}, 400)
                return
            try:
                data = fetch_coachee_from_notion(name)
                if data is None:
                    self._json_response({"error": f"No coachee found in Notion with name: {name}"}, 404)
                else:
                    self._json_response({"ok": True, "coachee": data})
            except Exception as e:
                self._json_response({"error": str(e)}, 500)
            return

        # GET /notion/status — check if Notion is configured
        if self.path == "/notion/status":
            configured = bool(NOTION_TOKEN and NOTION_COACHEES_DB)
            self._json_response({"configured": configured})
            return

        self.send_response(404)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/generate":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            cap_data = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Invalid JSON: {e}".encode())
            return

        if not os.path.exists(TEMPLATE_PATH):
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"BCG_CAP_Template.pptx not found. Place it next to cap_server.py.")
            return

        try:
            pptx_bytes = generate_pptx(cap_data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Generation error: {e}".encode())
            return

        client_name = cap_data.get("client", "Coachee").replace(" ", "_")
        filename = f"CAP_{client_name}.pptx"

        # ── Fire webhook: CAP exported ────────────────────────────────────────
        fire_webhook(MAKE_WEBHOOK_CAP_EXPORTED, {
            "event": "cap_exported",
            "coachee_name": cap_data.get("client", ""),
            "coachee_email": cap_data.get("coachee_email", ""),
            "filename": filename,
            "session_date": cap_data.get("date", ""),
            "coach": cap_data.get("coach", ""),
            "goals": cap_data.get("goals", ""),
            "way_forward": cap_data.get("way_forward", ""),
            "quick_wins": cap_data.get("quick_wins", []),
        })

        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(pptx_bytes)))
        self.end_headers()
        self.wfile.write(pptx_bytes)


def main():
    if not os.path.exists(TEMPLATE_PATH):
        print(f"⚠️  Warning: BCG_CAP_Template.pptx not found at {TEMPLATE_PATH}")
        print("    Place BCG_CAP_Template.pptx in the same folder as this script.")
    else:
        print(f"✅ Template found: {TEMPLATE_PATH}")

    server = HTTPServer(("localhost", PORT), CAPHandler)
    print(f"🚀 CAP Server running at http://localhost:{PORT}")
    print("   POST JSON to /generate to download a filled PPTX.")
    print("   Press Ctrl+C to stop.\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
