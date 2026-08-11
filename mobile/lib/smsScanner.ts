import { Platform, NativeModules } from 'react-native';

export type ParsedTransaction = {
  tran_date: string;
  description: string;
  debit: number;
  credit: number;
  balance: number;
  category: string;
  source: string;
  raw_sms?: string;
};

// Bank SMS sender IDs (Indian banks use 6-char alphanumeric sender IDs)
const BANK_SENDERS = [
  'HDFCBK', 'HDFCBN', 'AXISBK', 'ICICIB', 'SBIINB', 'SBIPSG',
  'KOTAKB', 'INDUSB', 'YESBNK', 'PNBSMS', 'BOIIND', 'CANBNK',
  'UNIONB', 'CENTBK', 'IDBIBK', 'RBLBNK', 'FEDBK', 'SCBANK',
  'CITIBN', 'PAYTMB', 'PAYTMS', 'PHONEPE', 'GPAY',
];

// Regex patterns for Indian bank SMS formats
const DEBIT_PATTERNS = [
  // HDFC: "Rs.500.00 debited from a/c XX1234 on 01-01-25"
  /(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)\s*(?:debited|deducted|spent|paid|withdrawn)/i,
  // Axis: "INR 500.00 debited from your account"
  /(?:inr|rs\.?|₹)\s*([\d,]+\.?\d*)\s*(?:has been\s+)?(?:debited|deducted)/i,
  // UPI: "debited Rs 500 via UPI"
  /debited\s+(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)/i,
  // "sent Rs 500 to"
  /sent\s+(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)/i,
  // "payment of Rs 500"
  /payment\s+of\s+(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)/i,
  // "purchase of INR 500"
  /purchase\s+of\s+(?:inr|rs\.?|₹)\s*([\d,]+\.?\d*)/i,
];

const CREDIT_PATTERNS = [
  /(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)\s*(?:credited|received|deposited)/i,
  /(?:inr|rs\.?|₹)\s*([\d,]+\.?\d*)\s*(?:has been\s+)?(?:credited|received)/i,
  /credited\s+(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)/i,
  /received\s+(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)/i,
  /refund\s+of\s+(?:rs\.?|inr\.?|₹)\s*([\d,]+\.?\d*)/i,
];

const BALANCE_PATTERN = /(?:avl\.?\s*bal\.?|available\s+balance|bal\.?|balance)\s*(?:is|:)?\s*(?:rs\.?|inr\.?|₹)?\s*([\d,]+\.?\d*)/i;

const UPI_PATTERN = /(?:upi|vpa|@)/i;
const CARD_PATTERN = /(?:card|pos|atm|swipe|neft|imps|rtgs)/i;

function parseAmount(raw: string): number {
  return parseFloat(raw.replace(/,/g, '')) || 0;
}

function extractDate(smsBody: string, smsDate: number): string {
  const patterns = [
    /(\d{4}-\d{2}-\d{2})/,
    /(\d{2}[-\/]\d{2}[-\/]\d{4})/,
    /(\d{2}-[A-Za-z]{3}-\d{4})/,
    /(\d{2}[-\/]\d{2}[-\/]\d{2})/,
    /(\d{2}-[A-Za-z]{3}-\d{2})/,
  ];
  for (const p of patterns) {
    const m = smsBody.match(p);
    if (m) {
      try {
        let raw = m[1];
        // dd-mm-yyyy or dd/mm/yyyy
        let d = raw.match(/^(\d{2})[-\/](\d{2})[-\/](\d{4})$/);
        if (d) {
          const dt = new Date(`${d[3]}-${d[2]}-${d[1]}`);
          if (!isNaN(dt.getTime())) return dt.toISOString().slice(0, 10);
        }
        // dd-Mon-yyyy
        let d2 = raw.match(/^(\d{2})-([A-Za-z]{3})-(\d{4})$/);
        if (d2) {
          const dt = new Date(`${d2[1]} ${d2[2]} ${d2[3]}`);
          if (!isNaN(dt.getTime())) return dt.toISOString().slice(0, 10);
        }
        // yyyy-mm-dd
        if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
          const dt = new Date(raw);
          if (!isNaN(dt.getTime())) return dt.toISOString().slice(0, 10);
        }
        // 2-digit year: dd-mm-yy or dd/mm/yy
        let d3 = raw.match(/^(\d{2})[-\/](\d{2})[-\/](\d{2})$/);
        if (d3) {
          const yr = parseInt(d3[3]) + 2000;
          const dt = new Date(`${yr}-${d3[2]}-${d3[1]}`);
          if (!isNaN(dt.getTime())) return dt.toISOString().slice(0, 10);
        }
        // dd-Mon-yy
        let d4 = raw.match(/^(\d{2})-([A-Za-z]{3})-(\d{2})$/);
        if (d4) {
          const yr = parseInt(d4[3]) + 2000;
          const dt = new Date(`${d4[1]} ${d4[2]} ${yr}`);
          if (!isNaN(dt.getTime())) return dt.toISOString().slice(0, 10);
        }
      } catch {}
    }
  }
  return new Date(smsDate).toISOString().slice(0, 10);
}

function categorize(smsBody: string): string {
  const lower = smsBody.toLowerCase();
  if (/swiggy|zomato|food|restaurant|cafe|hotel|dining/.test(lower)) return 'Food';
  if (/amazon|flipkart|myntra|shopping|mall|store|mart/.test(lower)) return 'Shopping';
  if (/airtel|jio|vodafone|bsnl|recharge|mobile|internet|broadband/.test(lower)) return 'Mobile / Internet';
  if (/upi|phonepe|gpay|paytm|bhim/.test(lower)) return 'UPI Transfer';
  if (/electricity|water|gas|bill|utility/.test(lower)) return 'Bills';
  if (/mutual fund|sip|stock|zerodha|groww|invest|nse|bse/.test(lower)) return 'Investment';
  if (/uber|ola|metro|bus|train|irctc|flight|travel/.test(lower)) return 'Travel';
  if (/netflix|spotify|prime|hotstar|entertainment|movie/.test(lower)) return 'Entertainment';
  if (/hospital|pharmacy|medical|health|doctor|clinic/.test(lower)) return 'Health';
  if (/school|college|fees|education|tuition/.test(lower)) return 'Education';
  if (/grocery|bigbasket|blinkit|zepto|dmart/.test(lower)) return 'Grocery';
  if (/atm|cash|withdrawal/.test(lower)) return 'Other';
  return 'Uncategorized';
}

export function parseSms(smsBody: string, smsDate: number, sender: string): ParsedTransaction | null {
  const body = smsBody.trim();

  let debit = 0;
  let credit = 0;

  // Try debit patterns
  for (const p of DEBIT_PATTERNS) {
    const m = body.match(p);
    if (m) { debit = parseAmount(m[1]); break; }
  }

  // Try credit patterns (always check, pick whichever is non-zero)
  for (const p of CREDIT_PATTERNS) {
    const m = body.match(p);
    if (m) { credit = parseAmount(m[1]); break; }
  }

  // If both matched (ambiguous SMS), prefer the larger amount
  if (debit > 0 && credit > 0) {
    if (credit > debit) debit = 0;
    else credit = 0;
  }

  if (debit === 0 && credit === 0) return null;

  // Extract balance
  const balMatch = body.match(BALANCE_PATTERN);
  const balance = balMatch ? parseAmount(balMatch[1]) : 0;

  // Build description
  let description = '';
  if (UPI_PATTERN.test(body)) {
    // Try to get payee/payer name (before VPA)
    const namedVpa = body.match(/(?:to|from)\s+([^@\n]{2,30}?)\s*([\w.\-]+@[\w]+)/i);
    const vpaOnly = body.match(/(?:to|from)\s+([\w.\-@]+@[\w]+)/i);
    // Try UPI ref/txn ID
    const refMatch = body.match(/(?:upi\s*ref\.?\s*(?:no\.?)?|ref\s*no\.?|txn\s*id)\s*[:\-]?\s*(\w+)/i);
    if (namedVpa && namedVpa[1].trim().length > 1) {
      description = `UPI - ${namedVpa[1].trim()} (${namedVpa[2]})`;
    } else if (vpaOnly) {
      description = `UPI - ${vpaOnly[1]}`;
    } else {
      description = 'UPI Payment';
    }
    if (refMatch) description += ` | Ref: ${refMatch[2]}`;
  } else if (CARD_PATTERN.test(body)) {
    const txnType = body.match(/\b(pos|atm|neft|imps|rtgs|card)\b/i)?.[1]?.toUpperCase() || 'Card';
    const merchantMatch = body.match(/(?:at|to)\s+([A-Za-z][A-Za-z0-9 &.\-]{2,35}?)(?:\s+on|\s+for|\s+via|\.|,|$)/i);
    const refMatch = body.match(/(?:ref\.?\s*(?:no\.?)?|txn\s*id|rrn)\s*[:\-]?\s*(\w+)/i);
    description = merchantMatch ? `${txnType} - ${merchantMatch[1].trim()}` : `${txnType} Transaction`;
    if (refMatch) description += ` | Ref: ${refMatch[1]}`;
  } else {
    // Generic bank: try to extract narration/info
    const narration = body.match(/(?:info|narration|remarks?|desc(?:ription)?)\s*[:\-]\s*([^\n.]{3,50})/i)
      || body.match(/(?:transfer|payment|credit|debit)\s+(?:to|from|by)\s+([A-Za-z][A-Za-z0-9 .]{2,40}?)(?:\s+on|\.|,|$)/i);
    const refMatch = body.match(/(?:ref\.?\s*(?:no\.?)?|txn\s*id)\s*[:\-]?\s*(\w+)/i);
    description = narration ? narration[1].trim() : (debit > 0 ? 'Bank Debit' : 'Bank Credit');
    if (refMatch) description += ` | Ref: ${refMatch[1]}`;
  }

  return {
    tran_date: extractDate(body, smsDate),
    description,
    debit,
    credit,
    balance,
    category: categorize(body),
    source: 'SMS_SCAN',
    raw_sms: body.slice(0, 120),
  };
}

export function isBankSms(sender: string): boolean {
  const upper = (sender || '').toUpperCase();
  return BANK_SENDERS.some((s) => upper.includes(s));
}

// Native SMS reading via Android SmsManager (requires READ_SMS permission)
// Returns raw SMS list or empty array if permission denied / not Android
export async function readAndroidSms(maxCount = 200): Promise<Array<{ address: string; body: string; date: number }>> {
  if (Platform.OS !== 'android') return [];
  try {
    // expo-sms doesn't support reading; we use a native module approach via
    // react-native-get-sms-android if available, otherwise return empty.
    const SmsAndroid = (NativeModules as any).SmsAndroid;
    if (!SmsAndroid) return [];

    return new Promise((resolve) => {
      SmsAndroid.list(
        JSON.stringify({ box: 'inbox', maxCount, indexFrom: 0 }),
        (fail: string) => { console.warn('SMS read failed:', fail); resolve([]); },
        (_count: number, smsList: string) => {
          try { resolve(JSON.parse(smsList) || []); } catch { resolve([]); }
        }
      );
    });
  } catch {
    return [];
  }
}

export async function scanBankSms(maxCount = 200): Promise<ParsedTransaction[]> {
  const smsList = await readAndroidSms(maxCount);
  const results: ParsedTransaction[] = [];

  for (const sms of smsList) {
    if (!isBankSms(sms.address)) continue;
    const parsed = parseSms(sms.body, sms.date, sms.address);
    if (parsed) results.push(parsed);
  }

  return results;
}
