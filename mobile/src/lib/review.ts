import * as StoreReview from 'expo-store-review';

import { readJson, writeJson } from './storage';

const MIN_OPENS = 5;

/** Cuenta una apertura de ficha. Llamar una vez al abrir cada ficha. */
export async function countDetailOpen(): Promise<void> {
  try {
    const opens = (await readJson<number>('openCount', 0)) + 1;
    await writeJson('openCount', opens);
  } catch {
    // Nunca debe molestar.
  }
}

/**
 * Pide valoración una sola vez en la vida de la app, justo después de guardar un proyecto
 * (un momento de satisfacción) y solo si ya se han abierto ≥ 5 fichas.
 */
export async function maybeAskForReviewAfterSave(): Promise<void> {
  try {
    const opens = await readJson<number>('openCount', 0);
    if (opens < MIN_OPENS || (await readJson<boolean>('reviewAsked', false))) return;
    if (!(await StoreReview.isAvailableAsync()) || !(await StoreReview.hasAction())) return;
    await writeJson('reviewAsked', true);
    await StoreReview.requestReview();
  } catch {
    // Nunca debe molestar: si falla, no pasa nada.
  }
}
