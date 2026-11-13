/** Textos del aviso de plazo (comparten el control en línea y los toasts de guardar). */
import { formatDate, formatDateLong } from '@/lib/format';
import { reminderPlan } from '@/lib/reminders';
import type { Opportunity } from '@/lib/types';

type Target = Pick<Opportunity, 'identifier' | 'title' | 'application_deadline' | 'deadline_estimated' | 'status'>;

function isoOf(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

export interface ReminderWhen {
  /** "9 dic" */
  short: string;
  /** "9 de diciembre de 2026" (para el lector) */
  long: string;
  /** "3 días antes del cierre", "1 día antes del cierre", "el día del cierre" */
  relative: string;
  /** "Avísame 3 días antes", "Avísame 1 día antes", "Avísame el día del cierre" */
  action: string;
}

/** Cuándo saltaría el aviso, en texto. null si no se puede poner. */
export function reminderWhen(o: Target): ReminderWhen | null {
  const plan = reminderPlan(o);
  if (!plan.ok) return null;
  const iso = isoOf(plan.fireAt);
  const n = plan.daysBefore;
  const relative = n === 0 ? 'el día del cierre' : `${n} ${n === 1 ? 'día' : 'días'} antes del cierre`;
  const action = n === 0 ? 'Avísame el día del cierre' : `Avísame ${n} ${n === 1 ? 'día' : 'días'} antes`;
  return { short: formatDate(iso, true) ?? '', long: formatDateLong(iso) ?? '', relative, action };
}

/** Por qué no se puede poner el aviso (o null si sí se puede). */
export function reminderUnavailableReason(o: Target): string | null {
  const plan = reminderPlan(o);
  return plan.ok ? null : plan.reason;
}
