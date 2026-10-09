const DEFAULT_SHEET_NAME = 'Leads';
const DEFAULT_TOKEN = '';
const HEADERS = ['Year', 'Month', 'Day', 'Hour', 'Name', 'Phone Number', 'Mail', 'Birth Date', 'Program', 'Branch', 'Source', 'Identifier'];

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
      normalizeValue(lead.mail || lead.email),
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
    migrateLegacySheet_(sheet);
  }
}

function migrateLegacySheet_(sheet) {
  const allRows = sheet.getDataRange().getValues();
  if (!allRows.length) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    return;
  }

  const legacyRows = allRows.slice(1);
  const normalizedRows = legacyRows.map(function(row) {
    const legacyDate = row[0];
    const splitDate = splitLegacyDate_(legacyDate);
    return [
      splitDate.year,
      splitDate.month,
      splitDate.day,
      splitDate.hour,
      normalizeValue(row[1]),
      normalizeValue(row[2]),
      '',
      '',
      normalizeValue(row[3]) || 'Sin especificar',
      normalizeValue(row[4]) || 'Sin especificar',
      normalizeValue(row[5]) || 'Instagram',
      normalizeValue(row[6]),
    ];
  });

  sheet.clearContents();
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  if (normalizedRows.length) {
    sheet.getRange(2, 1, normalizedRows.length, HEADERS.length).setValues(normalizedRows);
  }
}

function splitLegacyDate_(value) {
  if (value instanceof Date) {
    return {
      year: String(value.getFullYear()),
      month: pad2_(value.getMonth() + 1),
      day: pad2_(value.getDate()),
      hour: pad2_(value.getHours()) + ':00',
    };
  }

  const text = String(value || '').trim();
  if (!text) {
    return { year: '', month: '', day: '', hour: '' };
  }

  const isoMatch = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2})(?::\d{2}(?::\d{2})?)?)?/);
  if (isoMatch) {
    return {
      year: isoMatch[1],
      month: pad2_(isoMatch[2]),
      day: pad2_(isoMatch[3]),
      hour: pad2_(isoMatch[4] || '0') + ':00',
    };
  }

  const slashMatch = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:\s+(\d{1,2})(?::\d{2})?)?/);
  if (slashMatch) {
    return {
      year: slashMatch[3].length === 2 ? '20' + slashMatch[3] : slashMatch[3],
      month: pad2_(slashMatch[2]),
      day: pad2_(slashMatch[1]),
      hour: pad2_(slashMatch[4] || '0') + ':00',
    };
  }

  return {
    year: text.slice(0, 4),
    month: '',
    day: '',
    hour: '',
  };
}

function pad2_(value) {
  return String(value || '').padStart(2, '0');
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