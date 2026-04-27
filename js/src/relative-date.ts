/**
 * Todoosy Relative Date Parser
 *
 * Resolves keywords ("today", "tomorrow") and relative offsets ("2 weeks",
 * "in 3 days", "two months") to concrete ISO dates. The resolution always
 * happens at parse time; the persisted form on disk is always a concrete
 * date.
 */

import type { Settings } from './types.js';

export interface ResolvedNow {
  /** The user's "today" as an ISO YYYY-MM-DD string (in their TZ). */
  todayIso: string;
}

const NUMBER_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15,
  sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20,
  'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23, 'twenty-four': 24,
  'twenty-five': 25, 'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28,
  'twenty-nine': 29, thirty: 30, 'thirty-one': 31,
};

const TENS = new Set(['twenty', 'thirty']);
const ONES_AFTER_TENS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9,
};

const DAY_UNITS = new Set(['d', 'day', 'days']);
const WEEK_UNITS = new Set(['w', 'wk', 'wks', 'week', 'weeks']);
const MONTH_UNITS = new Set(['month', 'months']);
const YEAR_UNITS = new Set(['y', 'yr', 'yrs', 'year', 'years']);

export function resolveNow(now: Date | undefined, settings: Settings | undefined): ResolvedNow {
  const instant = now ?? new Date();
  const tz = settings?.timezone ?? 'UTC';
  // Use Intl to get Y-M-D in the configured timezone. en-CA gives YYYY-MM-DD.
  let todayIso: string;
  try {
    todayIso = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(instant);
  } catch {
    // Invalid timezone → fall back to UTC
    todayIso = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'UTC',
      year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(instant);
  }
  return { todayIso };
}

function parseISOAsUTC(iso: string): Date {
  // iso is YYYY-MM-DD; build a UTC Date so arithmetic doesn't drift across DST.
  const [y, m, d] = iso.split('-').map(n => parseInt(n, 10));
  return new Date(Date.UTC(y, m - 1, d));
}

function dateToISO(d: Date): string {
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDays(iso: string, days: number): string {
  const d = parseISOAsUTC(iso);
  d.setUTCDate(d.getUTCDate() + days);
  return dateToISO(d);
}

function addMonths(iso: string, months: number): string {
  // Calendar-aware: clip day if target month is shorter (Jan 31 + 1 month = Feb 28/29).
  const d = parseISOAsUTC(iso);
  const targetMonth = d.getUTCMonth() + months;
  const targetYear = d.getUTCFullYear() + Math.floor(targetMonth / 12);
  const normalizedMonth = ((targetMonth % 12) + 12) % 12;
  const desiredDay = d.getUTCDate();
  // Last day of target month: day 0 of next month.
  const lastDayOfTarget = new Date(Date.UTC(targetYear, normalizedMonth + 1, 0)).getUTCDate();
  const day = Math.min(desiredDay, lastDayOfTarget);
  return dateToISO(new Date(Date.UTC(targetYear, normalizedMonth, day)));
}

function addYears(iso: string, years: number): string {
  return addMonths(iso, years * 12);
}

/**
 * Resolve `today` or `tomorrow` (case-insensitive). Returns the ISO date or null.
 */
export function resolveKeyword(word: string, now: ResolvedNow): string | null {
  const w = word.toLowerCase();
  if (w === 'today') return now.todayIso;
  if (w === 'tomorrow') return addDays(now.todayIso, 1);
  return null;
}

/**
 * Try to parse a number-word starting at `index`. Returns count + parts consumed,
 * or null if no number-word found. Supports "twenty one" (two parts) and
 * "twenty-one" (single part with hyphen).
 */
function tryParseNumberWord(parts: string[], index: number): { value: number; partsConsumed: number } | null {
  if (index >= parts.length) return null;
  const w0 = parts[index].toLowerCase();
  // Try compound form first ("twenty one") so it doesn't get pre-empted by the
  // simple lookup of "twenty".
  if (TENS.has(w0) && index + 1 < parts.length) {
    const w1 = parts[index + 1].toLowerCase();
    if (w1 in ONES_AFTER_TENS) {
      const sum = NUMBER_WORDS[w0] + ONES_AFTER_TENS[w1];
      if (sum <= 31) return { value: sum, partsConsumed: 2 };
    }
  }
  if (w0 in NUMBER_WORDS) {
    return { value: NUMBER_WORDS[w0], partsConsumed: 1 };
  }
  return null;
}

/**
 * Identify a unit word and the relative-date "kind" it implies. Returns null
 * if the word is not a relative-date unit (estimate units `m`/`h`/`d` may
 * collide with `d`; the caller resolves that ordering — bare `2d` is parsed
 * as estimate before this is consulted).
 */
function classifyUnit(word: string): 'days' | 'weeks' | 'months' | 'years' | null {
  const w = word.toLowerCase();
  if (DAY_UNITS.has(w)) return 'days';
  if (WEEK_UNITS.has(w)) return 'weeks';
  if (MONTH_UNITS.has(w)) return 'months';
  if (YEAR_UNITS.has(w)) return 'years';
  return null;
}

function applyOffset(now: ResolvedNow, count: number, kind: 'days' | 'weeks' | 'months' | 'years'): string {
  switch (kind) {
    case 'days':   return addDays(now.todayIso, count);
    case 'weeks':  return addDays(now.todayIso, count * 7);
    case 'months': return addMonths(now.todayIso, count);
    case 'years':  return addYears(now.todayIso, count);
  }
}

const FUSED_OFFSET_RE = /^(\d+)([a-z]+)$/i;

/**
 * Try to consume a "from now" / "from today" suffix starting at `index`.
 * Returns the number of parts consumed (0, 2).
 */
function tryConsumeFromSuffix(parts: string[], index: number): number {
  if (index + 1 < parts.length) {
    const a = parts[index].toLowerCase();
    const b = parts[index + 1].toLowerCase();
    if (a === 'from' && (b === 'now' || b === 'today')) return 2;
  }
  return 0;
}

/**
 * Try to parse a relative-date expression starting at `index`. Returns the
 * resolved ISO date and parts consumed, or null if no relative date is
 * recognized at this position.
 *
 * Grammar (case-insensitive):
 *   ["in"] (digit | number-word) unit ["from now"|"from today"]
 *   ["in"] <fused>            where <fused> matches /^\d+(w|wk|wks|week|weeks|y|yr|yrs|year|years)$/
 *                             (note: bare 2d/2h/2m are estimates and parsed earlier)
 *
 * Returns null on no match. Does not throw. Bounded look-ahead.
 */
export function tryParseRelative(
  parts: string[],
  index: number,
  now: ResolvedNow,
): { date: string; partsConsumed: number } | null {
  if (index >= parts.length) return null;

  let cursor = index;
  let consumedIn = 0;
  if (parts[cursor].toLowerCase() === 'in') {
    consumedIn = 1;
    cursor++;
    if (cursor >= parts.length) return null;
  }

  // Try fused form first: "2w", "2years", etc. (single token, digits + alpha)
  const fused = parts[cursor].match(FUSED_OFFSET_RE);
  if (fused) {
    const count = parseInt(fused[1], 10);
    const kind = classifyUnit(fused[2]);
    if (kind === null) return null;
    // Day-fused (`2d`) is reserved for estimate; only weeks/months/years allowed fused.
    // (Estimate parser runs earlier and would have matched 2d/2h/2m already; if we
    // get here on `2d`, the estimate parser declined for some reason — still reject
    // to keep semantics one-way.)
    if (kind === 'days') return null;
    const after = cursor + 1;
    const suffixConsumed = tryConsumeFromSuffix(parts, after);
    return {
      date: applyOffset(now, count, kind),
      partsConsumed: consumedIn + 1 + suffixConsumed,
    };
  }

  // Split form: number then unit (each as separate part).
  // Number can be digits or a number-word (1-2 parts).
  let count: number;
  let numberPartsConsumed: number;
  const digitsMatch = parts[cursor].match(/^(\d+)$/);
  if (digitsMatch) {
    count = parseInt(digitsMatch[1], 10);
    numberPartsConsumed = 1;
  } else {
    const word = tryParseNumberWord(parts, cursor);
    if (!word) return null;
    count = word.value;
    numberPartsConsumed = word.partsConsumed;
  }

  const unitIndex = cursor + numberPartsConsumed;
  if (unitIndex >= parts.length) return null;
  const kind = classifyUnit(parts[unitIndex]);
  if (kind === null) return null;

  // Reject the day case in the *split* form when written as bare `d` ("2 d"):
  // that is a confusing form. Require "day"/"days" for clarity.
  if (kind === 'days' && parts[unitIndex].toLowerCase() === 'd') return null;

  const after = unitIndex + 1;
  const suffixConsumed = tryConsumeFromSuffix(parts, after);
  return {
    date: applyOffset(now, count, kind),
    partsConsumed: consumedIn + numberPartsConsumed + 1 + suffixConsumed,
  };
}
