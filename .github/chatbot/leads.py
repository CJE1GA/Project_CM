"""Lead storage for the chatbot, with cloud backends and local Excel fallback."""

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime

import re

from config import LEADS_FILE, LEAD_SOURCE

COLUMNS = ["Date", "Name", "Phone Number", "Program", "Branch", "Source"]
GOOGLE_COLUMNS = ["Date", "Name", "Phone Number", "Program", "Branch", "Source", "Identifier"]
UNSPECIFIED = "Sin especificar"
INSTAGRAM_HANDLE_RE = re.compile(r"@[_a-zA-Z0-9.]+")

_lock = threading.Lock()


def _path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), LEADS_FILE)


def _google_config() -> dict:
    return {
        "spreadsheet_id": os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip(),
        "worksheet_name": os.environ.get("GOOGLE_SHEETS_WORKSHEET_NAME", "Leads").strip() or "Leads",
        "service_account_json": os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip(),
        "service_account_file": os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip(),
    }


def _apps_script_config() -> dict:
    return {
        "url": os.environ.get("GOOGLE_APPS_SCRIPT_URL", "").strip(),
        "token": os.environ.get("GOOGLE_APPS_SCRIPT_TOKEN", "").strip(),
    }


def _sync_lead_to_apps_script(name: str, phone: str, program: str, branch: str, identifier: str) -> bool:
    config = _apps_script_config()
    if not config["url"]:
        return False

    payload = {
        "token": config["token"],
        "action": "upsert_lead",
        "lead": {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": name,
            "phone": phone or "",
            "program": program or UNSPECIFIED,
            "branch": branch or UNSPECIFIED,
            "source": LEAD_SOURCE,
            "identifier": identifier,
        },
    }
    request_obj = urllib.request.Request(
        config["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            response_body = response.read().decode("utf-8").strip()
        if not response_body:
            return True
        response_json = json.loads(response_body)
        return bool(response_json.get("ok"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[leads] No se pudo guardar en Google Apps Script: {exc}")
        return False


def _google_client():
    config = _google_config()
    if not config["spreadsheet_id"]:
        return None

    try:
        import gspread
    except ImportError:
        print("[leads] gspread no instalado; se usará Excel local.")
        return None

    try:
        if config["service_account_json"]:
            credentials_info = json.loads(config["service_account_json"])
            return gspread.service_account_from_dict(credentials_info)
        if config["service_account_file"]:
            return gspread.service_account(filename=config["service_account_file"])
    except Exception as exc:
        print(f"[leads] No se pudieron cargar credenciales de Google Sheets: {exc}")
        return None

    print("[leads] Faltan credenciales de Google Sheets; se usará Excel local.")
    return None


def _google_worksheet():
    config = _google_config()
    client = _google_client()
    if not client:
        return None

    try:
        spreadsheet = client.open_by_key(config["spreadsheet_id"])
        try:
            worksheet = spreadsheet.worksheet(config["worksheet_name"])
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=config["worksheet_name"], rows=1000, cols=len(GOOGLE_COLUMNS))
        return worksheet
    except Exception as exc:
        print(f"[leads] No se pudo abrir Google Sheets: {exc}")
        return None


def _ensure_google_headers(worksheet):
    headers = worksheet.row_values(1)
    if headers != GOOGLE_COLUMNS:
        if not headers:
            worksheet.append_row(GOOGLE_COLUMNS)
            return
        worksheet.update("A1:G1", [GOOGLE_COLUMNS])


def _sync_lead_to_google_sheet(name: str, phone: str, program: str, branch: str, identifier: str) -> bool:
    worksheet = _google_worksheet()
    if worksheet is None:
        return False

    try:
        _ensure_google_headers(worksheet)
        all_rows = worksheet.get_all_values()
        existing_row = None
        for index, row in enumerate(all_rows[1:], start=2):
            row_identifier = row[6].strip() if len(row) > 6 else ""
            if row_identifier == identifier:
                existing_row = index
                break

        values = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            name,
            phone or "",
            program or UNSPECIFIED,
            branch or UNSPECIFIED,
            LEAD_SOURCE,
            identifier,
        ]

        if existing_row is None:
            worksheet.append_row(values)
        else:
            worksheet.update(f"A{existing_row}:G{existing_row}", [values])
        return True
    except Exception as exc:
        print(f"[leads] No se pudo guardar en Google Sheets: {exc}")
        return False


def _meaningful(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip() != UNSPECIFIED)


def _coalesce(current: str | None, incoming: str | None) -> str:
    if _meaningful(incoming):
        return incoming.strip()
    if current and str(current).strip():
        return str(current).strip()
    if incoming and incoming.strip():
        return incoming.strip()
    return ""


def _ensure_workbook():
    from openpyxl import Workbook, load_workbook

    path = _path()
    if os.path.exists(path):
        workbook = load_workbook(path)
        sheet = workbook.active
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Leads"
        sheet.append(COLUMNS)

    return workbook, sheet, path


def _extract_identifier(name: str | None) -> str:
    if not name:
        return ""
    match = INSTAGRAM_HANDLE_RE.search(str(name))
    return match.group(0) if match else str(name).strip()


def normalize_identifier(value: str | None) -> str:
    return _extract_identifier(value)


def upsert_lead(
    name: str,
    phone: str = "",
    program: str = UNSPECIFIED,
    branch: str = UNSPECIFIED,
    identifier: str | None = None,
) -> None:
    with _lock:
        lookup_value = normalize_identifier(identifier or name)
        if _sync_lead_to_apps_script(name, phone, program, branch, lookup_value):
            return
        if _sync_lead_to_google_sheet(name, phone, program, branch, lookup_value):
            return

        try:
            from openpyxl import Workbook, load_workbook
        except ImportError:
            print("[leads] openpyxl no instalado; el lead no se guardó en Excel.")
            return

        del Workbook, load_workbook

        workbook, sheet, path = _ensure_workbook()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        matching_rows = []

        for row in range(sheet.max_row, 1, -1):
            row_name = sheet.cell(row=row, column=2).value
            row_source = sheet.cell(row=row, column=6).value
            row_identifier = _extract_identifier(row_name)
            if row_source == LEAD_SOURCE and row_identifier == lookup_value:
                matching_rows.append(row)

        if not matching_rows:
            sheet.append([
                timestamp,
                name,
                phone or "",
                program or UNSPECIFIED,
                branch or UNSPECIFIED,
                LEAD_SOURCE,
            ])
        else:
            merged_name = name
            merged_phone = phone or ""
            merged_program = program or UNSPECIFIED
            merged_branch = branch or UNSPECIFIED

            for row in reversed(matching_rows):
                current_name = str(sheet.cell(row=row, column=2).value or "").strip()
                if len(current_name) > len(merged_name):
                    merged_name = current_name
                merged_phone = _coalesce(merged_phone, sheet.cell(row=row, column=3).value)
                merged_program = _coalesce(merged_program, sheet.cell(row=row, column=4).value) or UNSPECIFIED
                merged_branch = _coalesce(merged_branch, sheet.cell(row=row, column=5).value) or UNSPECIFIED

            for row in matching_rows:
                sheet.delete_rows(row, 1)

            sheet.append([
                timestamp,
                merged_name,
                merged_phone,
                merged_program,
                merged_branch,
                LEAD_SOURCE,
            ])

        workbook.save(path)


def deduplicate_leads() -> int:
    try:
        from openpyxl import Workbook, load_workbook
    except ImportError:
        print("[leads] openpyxl no instalado; no se pudo consolidar el Excel.")
        return 0

    del Workbook, load_workbook

    with _lock:
        workbook, sheet, path = _ensure_workbook()
        grouped = {}
        removed = 0

        for row in range(2, sheet.max_row + 1):
            date_value = sheet.cell(row=row, column=1).value
            name_value = sheet.cell(row=row, column=2).value
            phone_value = sheet.cell(row=row, column=3).value
            program_value = sheet.cell(row=row, column=4).value
            branch_value = sheet.cell(row=row, column=5).value
            source_value = sheet.cell(row=row, column=6).value

            if not name_value:
                continue

            normalized_name = str(name_value).strip()
            key = (_extract_identifier(normalized_name), str(source_value or "").strip())
            item = grouped.setdefault(
                key,
                {
                    "date": date_value,
                    "name": normalized_name,
                    "phone": "",
                    "program": UNSPECIFIED,
                    "branch": UNSPECIFIED,
                    "source": source_value or LEAD_SOURCE,
                    "count": 0,
                },
            )

            item["count"] += 1
            if len(normalized_name) > len(item["name"]):
                item["name"] = normalized_name
            item["phone"] = _coalesce(item["phone"], phone_value)
            item["program"] = _coalesce(item["program"], program_value) or UNSPECIFIED
            item["branch"] = _coalesce(item["branch"], branch_value) or UNSPECIFIED
            item["date"] = date_value or item["date"]

        rows = [COLUMNS]
        for item in grouped.values():
            removed += max(item["count"] - 1, 0)
            rows.append([
                item["date"],
                item["name"],
                item["phone"],
                item["program"],
                item["branch"],
                item["source"],
            ])

        sheet.delete_rows(1, sheet.max_row)
        for row in rows:
            sheet.append(row)

        workbook.save(path)
        return removed
