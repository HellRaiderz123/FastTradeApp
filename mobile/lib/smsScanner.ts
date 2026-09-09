import { Platform, NativeModules } from 'react-native';

export type ParsedTransaction = {
  tran_date: string;
  description: string;
  merchant: string;       // clean display name, e.g. "Airtel", "Swiggy"
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

type CategoryInfo = { label: string; emoji: string; color: string; bg: string };

const CATEGORIES: Record<string, CategoryInfo> = {
  Food:              { label: 'Food',         emoji: '🍔', color: '#F97316', bg: 'rgba(249,115,22,0.15)' },
  Shopping:         { label: 'Shopping',      emoji: '🛍️', color: '#A855F7', bg: 'rgba(168,85,247,0.15)' },
  'Mobile / Internet': { label: 'Mobile',     emoji: '📱', color: '#EF4444', bg: 'rgba(239,68,68,0.15)' },
  'UPI Transfer':   { label: 'UPI',           emoji: '💸', color: '#3B82F6', bg: 'rgba(59,130,246,0.15)' },
  Bills:            { label: 'Bills',         emoji: '🧾', color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
  Investment:       { label: 'Investment',    emoji: '📈', color: '#10B981', bg: 'rgba(16,185,129,0.15)' },
  Travel:           { label: 'Travel',        emoji: '✈️', color: '#06B6D4', bg: 'rgba(6,182,212,0.15)' },
  Entertainment:    { label: 'Entertainment', emoji: '🎬', color: '#EC4899', bg: 'rgba(236,72,153,0.15)' },
  Health:           { label: 'Health',        emoji: '🏥', color: '#14B8A6', bg: 'rgba(20,184,166,0.15)' },
  Education:        { label: 'Education',     emoji: '📚', color: '#8B5CF6', bg: 'rgba(139,92,246,0.15)' },
  Grocery:          { label: 'Grocery',       emoji: '🛒', color: '#84CC16', bg: 'rgba(132,204,22,0.15)' },
  Income:           { label: 'Income',        emoji: '💰', color: '#10B981', bg: 'rgba(16,185,129,0.15)' },
  Other:            { label: 'Other',         emoji: '🏧', color: '#64748B', bg: 'rgba(100,116,139,0.15)' },
  Uncategorized:    { label: 'Others',        emoji: '💳', color: '#475569', bg: 'rgba(71,85,105,0.15)' },
};

export function getCategoryInfo(category: string): CategoryInfo {
  return CATEGORIES[category] ?? CATEGORIES['Uncategorized'];
}

function categorize(smsBody: string): string {
  const lower = smsBody.toLowerCase();
  if (/swiggy|zomato|food|restaurant|cafe|hotel|dining/.test(lower)) return 'Food';
  if (/amazon|flipkart|myntra|shopping|mall|store|mart/.test(lower)) return 'Shopping';
  if (/airtel|jio|vodafone|bsnl|recharge|mobile|internet|broadband/.test(lower)) return 'Mobile / Internet';
  if (/electricity|water|gas|bill|utility/.test(lower)) return 'Bills';
  if (/mutual fund|sip|stock|zerodha|groww|invest|nse|bse/.test(lower)) return 'Investment';
  if (/uber|ola|metro|bus|train|irctc|flight|travel/.test(lower)) return 'Travel';
  if (/netflix|spotify|prime|hotstar|entertainment|movie/.test(lower)) return 'Entertainment';
  if (/hospital|pharmacy|medical|health|doctor|clinic/.test(lower)) return 'Health';
  if (/school|college|fees|education|tuition/.test(lower)) return 'Education';
  if (/grocery|bigbasket|blinkit|zepto|dmart/.test(lower)) return 'Grocery';
  if (/atm|cash|withdrawal/.test(lower)) return 'Other';
  if (/upi|phonepe|gpay|paytm|bhim/.test(lower)) return 'UPI Transfer';
  return 'Uncategorized';
}

// Known brand name extraction from SMS body
const BRAND_PATTERNS: Array<[RegExp, string]> = [
  [/airtel/i, 'Airtel'],
  [/jio/i, 'Jio'],
  [/vodafone|vi\b/i, 'Vi'],
  [/bsnl/i, 'BSNL'],
  [/swiggy/i, 'Swiggy'],
  [/zomato/i, 'Zomato'],
  [/amazon/i, 'Amazon'],
  [/flipkart/i, 'Flipkart'],
  [/myntra/i, 'Myntra'],
  [/bigbasket/i, 'BigBasket'],
  [/blinkit/i, 'Blinkit'],
  [/zepto/i, 'Zepto'],
  [/dmart/i, 'DMart'],
  [/netflix/i, 'Netflix'],
  [/spotify/i, 'Spotify'],
  [/hotstar/i, 'Hotstar'],
  [/prime video/i, 'Prime Video'],
  [/uber/i, 'Uber'],
  [/ola\b/i, 'Ola'],
  [/irctc/i, 'IRCTC'],
  [/zerodha/i, 'Zerodha'],
  [/groww/i, 'Groww'],
  [/phonepe/i, 'PhonePe'],
  [/gpay|google pay/i, 'Google Pay'],
  [/paytm/i, 'Paytm'],
  [/hdfc/i, 'HDFC'],
  [/icici/i, 'ICICI'],
  [/axis bank/i, 'Axis Bank'],
  [/sbi/i, 'SBI'],
  [/kotak/i, 'Kotak'],
  [/rbl/i, 'RBL'],
  [/indusind/i, 'IndusInd'],
  [/yes bank/i, 'Yes Bank'],
  [/pnb/i, 'PNB'],
  [/canara/i, 'Canara Bank'],
  [/union bank/i, 'Union Bank'],
  [/federal bank/i, 'Federal Bank'],
];

function extractMerchant(smsBody: string, description: string, category: string): string {
  // Check known brands first
  for (const [pattern, name] of BRAND_PATTERNS) {
    if (pattern.test(smsBody)) return name;
  }
  // UPI: extract payee name before @
  const upiName = smsBody.match(/(?:to|from)\s+([A-Za-z][A-Za-z0-9 .]{1,25}?)\s*[\w.\-]+@[\w]+/i);
  if (upiName) return upiName[1].trim();
  // POS merchant
  const posMerchant = smsBody.match(/(?:at|to)\s+([A-Z][A-Za-z0-9 &.\-]{2,28}?)(?:\s+on|\s+for|\.|,|$)/i);
  if (posMerchant) return posMerchant[1].trim();
  // Fall back to first word of description
  const firstWord = description.split(/[\s|\-]/)[0];
  return firstWord || (category === 'UPI Transfer' ? 'UPI Transfer' : 'Others');
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

  const category = categorize(body);
  return {
    tran_date: extractDate(body, smsDate),
    description,
    merchant: extractMerchant(body, description, category),
    debit,
    credit,
    balance,
    category,
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
