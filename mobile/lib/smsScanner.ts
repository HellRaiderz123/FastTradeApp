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
  // Try to extract date from SMS body
  const patterns = [
    /(\d{2}[-\/]\d{2}[-\/]\d{2,4})/,
    /(\d{2}-[A-Za-z]{3}-\d{2,4})/,
    /(\d{4}-\d{2}-\d{2})/,
  ];
  for (const p of patterns) {
    const m = smsBody.match(p);
    if (m) {
      try {
        const d = new Date(m[1].replace(/(\d{2})[-\/](\d{2})[-\/](\d{2,4})/, '$3-$2-$1'));
        if (!isNaN(d.getTime())) return d.toISOString().slice(0, 10);
      } catch {}
    }
  }
  // Fall back to SMS timestamp
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
    const vpaMatch = body.match(/(?:to|from)\s+([\w.\-@]+@[\w]+)/i);
    description = vpaMatch ? `UPI - ${vpaMatch[1]}` : 'UPI Payment';
  } else if (CARD_PATTERN.test(body)) {
    const merchantMatch = body.match(/(?:at|to)\s+([A-Z][A-Z0-9 ]{2,30}?)(?:\s+on|\s+for|\.|,|$)/i);
    description = merchantMatch ? `Card - ${merchantMatch[1].trim()}` : 'Card Transaction';
  } else {
    description = debit > 0 ? 'Bank Debit' : 'Bank Credit';
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
