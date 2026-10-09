const DEFAULT_SHEET_NAME = 'Leads';
const DEFAULT_TOKEN = '';
const HEADERS = ['Year', 'Month', 'Day', 'Hour', 'Name', 'Phone Number', 'Email', 'Birth Date', 'Program', 'Branch', 'Source', 'Identifier'];

function doGet() {
  return jsonResponse({ ok: true, service: 'chatbot-leads-sheet' });
}

function doPost(e) {
  try {
    const payload = parsePayload(e);
    const token = String(payload.token || '').trim();
    if (DEFAULT_TOKEN && token !== DEFAULT_TOKEN) {
      return jsonResponse({ ok: false, error: 'invalid_token' });
    }

    if (payload.action !== 'upsert_lead') {
      return jsonResponse({ ok: false, error: 'unsupported_action' });
    }

    const lead = payload.lead || {};
    const identifier = normalizeValue(lead.identifier);
    if (!identifier) {
      return jsonResponse({ ok: false, error: 'missing_identifier' });
    }

    const sheet = getLeadSheet_();
    ensureHeaders_(sheet);
    const rows = sheet.getDataRange().getValues();
    const rowIndex = findLeadRow_(rows, identifier);
    const values = [[
      normalizeValue(lead.year),
      normalizeValue(lead.month),
      normalizeValue(lead.day),
      normalizeValue(lead.hour),
      normalizeValue(lead.name),
      normalizeValue(lead.phone),
      normalizeValue(lead.email),
      normalizeValue(lead.birth_date),
      normalizeValue(lead.program) || 'Sin especificar',
      normalizeValue(lead.branch) || 'Sin especificar',
      normalizeValue(lead.source) || 'Instagram',
      identifier,
    ]];

    if (rowIndex === -1) {
      sheet.getRange(sheet.getLastRow() + 1, 1, 1, HEADERS.length).setValues(values);
    } else {
      sheet.getRange(rowIndex, 1, 1, HEADERS.length).setValues(values);
    }

    return jsonResponse({ ok: true, identifier: identifier });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error) });
  }
}

function parsePayload(e) {
  if (!e || !e.postData || !e.postData.contents) {
    throw new Error('missing_body');
  }
  return JSON.parse(e.postData.contents);
}

function getLeadSheet_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(DEFAULT_SHEET_NAME);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(DEFAULT_SHEET_NAME);
  }
  return sheet;
}

function ensureHeaders_(sheet) {
  const existing = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  const hasHeaders = existing.some(function(value) {
    return String(value || '').trim() !== '';
  });
  if (!hasHeaders) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    return;
  }
  const sameHeaders = HEADERS.every(function(header, index) {
    return String(existing[index] || '').trim() === header;
  });
  if (!sameHeaders) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  }
}

function findLeadRow_(rows, identifier) {
  for (let index = 1; index < rows.length; index += 1) {
    const rowIdentifier = normalizeValue(rows[index][11]);
    if (rowIdentifier === identifier) {
      return index + 1;
    }
  }
  return -1;
}

function normalizeValue(value) {
  return String(value || '').trim();
}

function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}