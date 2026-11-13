/**
 * Pruebas de la lógica pura del estado (src/state/logic.ts) y de algunos textos de
 * src/lib/format.ts, sin dependencias: Node ≥22.18 quita los tipos de TypeScript por sí solo.
 *
 *   node scripts/check-logic.mjs
 *
 * Un pequeño "resolve hook" traduce el alias `@/` a `src/` y añade la extensión `.ts` a los
 * imports relativos sin extensión (como hace Metro). Si logic.ts o lo que importa llegara a
 * importar react-native, expo o react, este script falla: es la comprobación de que siguen
 * siendo puros.
 */
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { dirname, resolve as resolvePath } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolvePath(dirname(fileURLToPath(import.meta.url)), '..');
const src = resolvePath(root, 'src');
const FORBIDDEN = /^(react|react-native|expo|expo-[\w-]+|@expo\/|@react-native)/;

registerHooks({
  resolve(specifier, context, next) {
    if (FORBIDDEN.test(specifier)) {
      throw new Error(`Import no permitido en lógica pura: "${specifier}" (desde ${context.parentURL})`);
    }
    let spec = specifier;
    if (spec.startsWith('@/')) spec = pathToFileURL(resolvePath(src, spec.slice(2))).href;
    const isLocal = spec.startsWith('file:') || spec.startsWith('.');
    if (isLocal && !/\.[cm]?[jt]s$/.test(spec)) {
      const base = spec.startsWith('file:') ? fileURLToPath(spec) : resolvePath(dirname(fileURLToPath(context.parentURL)), spec);
      if (existsSync(`${base}.ts`)) spec = pathToFileURL(`${base}.ts`).href;
    }
    const result = next(spec, context);
    // Nuestros .ts son módulos ES (sin esto Node avisa al no haber "type" en package.json).
    return result.url.endsWith('.ts') ? { ...result, format: 'module-typescript' } : result;
  },
});

const logic = await import(pathToFileURL(resolvePath(src, 'state/logic.ts')).href);
const format = await import(pathToFileURL(resolvePath(src, 'lib/format.ts')).href);

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
  } catch (e) {
    console.error(`✗ ${name}`);
    throw e;
  }
}
const ids = (set) => [...set].sort();

const NOW = Date.parse('2026-11-13T12:00:00Z');

test('seenAfterFirstRun: lo anterior al corte y sin fecha cuenta como visto', () => {
  const items = [
    { identifier: 'a', created: '2026-11-12T10:00:00Z' },
    { identifier: 'b', created: '2026-11-01T10:00:00Z' },
    { identifier: 'c', created: null },
  ];
  assert.deepEqual(ids(logic.seenAfterFirstRun(items, new Set(), NOW)), ['b', 'c']);
});

test('seenAfterFirstRun: sin nada reciente, los N más recientes quedan nuevos', () => {
  const items = [
    { identifier: 'old1', created: '2026-10-01T10:00:00Z' },
    { identifier: 'old3', created: '2026-10-03T10:00:00Z' },
    { identifier: 'old2', created: '2026-10-02T10:00:00Z' },
  ];
  const seen = logic.seenAfterFirstRun(items, new Set(), NOW, 2, 2);
  assert.deepEqual(ids(seen), ['old1']);
  assert.deepEqual(ids(logic.seenAfterFirstRun(items, new Set(), NOW, 2, 0)), ['old1', 'old2', 'old3']);
  // Lo ya visto antes nunca se "desve".
  assert.ok(logic.seenAfterFirstRun(items, new Set(['old3']), NOW, 2, 2).has('old3'));
});

test('hydrateSeen: une y quita lo pendiente de volver a enseñar', () => {
  assert.deepEqual(ids(logic.hydrateSeen(['a', 'b'], new Set(['c']), new Set(['b']))), ['a', 'c']);
});

test('mergeSeen / pruneSeen / unseenItems', () => {
  assert.deepEqual(ids(logic.mergeSeen(['a'], new Set(['b']))), ['a', 'b']);
  assert.deepEqual(logic.pruneSeen(new Set(['a', 'z']), [{ identifier: 'a' }, { identifier: 'b' }]), ['a']);
  assert.deepEqual(ids(logic.pruneSeen(new Set(['a', 'z']), [])), ['a', 'z']);
  assert.deepEqual(
    logic.unseenItems([{ identifier: 'a' }, { identifier: 'b' }], new Set(['a'])).map((o) => o.identifier),
    ['b'],
  );
});

test('orderFirst: los anunciados primero, en el orden de la lista', () => {
  const items = ['a', 'b', 'c', 'd'].map((identifier) => ({ identifier }));
  assert.deepEqual(logic.orderFirst(items, new Set(['c', 'a'])).map((o) => o.identifier), ['a', 'c', 'b', 'd']);
  assert.deepEqual(logic.orderFirst(items, new Set()).map((o) => o.identifier), ['a', 'b', 'c', 'd']);
});

test('savedToRecheck: guardados fuera de la lista y no cerrados', () => {
  const open = { status: 'open', application_deadline: '2099-01-01' };
  const closed = { status: 'closed', application_deadline: null };
  const list = new Set(['a']);
  assert.deepEqual(logic.savedToRecheck(['a', 'b', 'c'], list, { b: open }, format.isClosed), ['b', 'c']);
  assert.deepEqual(logic.savedToRecheck(['a', 'b', 'c'], list, { b: closed }, format.isClosed), ['c']);
  assert.deepEqual(logic.savedToRecheck(['a', 'b', 'c'], list, { b: open }, format.isClosed, new Set(['c'])), ['b']);
  assert.deepEqual(logic.savedToRecheck(['b', 'c', 'd'], new Set(), {}, format.isClosed, new Set(), 2), ['b', 'c']);
});

test('firstVisitExpired', () => {
  assert.equal(logic.firstVisitExpired(null, NOW), false);
  assert.equal(logic.firstVisitExpired(NOW - 1000, NOW), false);
  assert.equal(logic.firstVisitExpired(NOW - 86_400_000, NOW), true);
});

test('planReminder', () => {
  const now = new Date(2026, 10, 13, 9, 0, 0);
  const plan = (deadline, status = 'open') => logic.planReminder({ status, application_deadline: deadline }, now);
  let p = plan('2026-11-20');
  assert.ok(p.ok && p.daysBefore === 3 && p.fireAt.getDate() === 17 && p.fireAt.getHours() === 10);
  p = plan('2026-11-14');
  assert.ok(p.ok && p.daysBefore === 1);
  p = plan('2026-11-13');
  assert.ok(p.ok && p.daysBefore === 0);
  assert.equal(plan('2026-11-12').ok, false);
  assert.equal(plan('2026-11-30', 'closed').ok, false);
  assert.equal(plan(null).ok, false);
});

test('costShort', () => {
  assert.equal(format.costShort({ cost: 0, type: 'YOUTH_EXCHANGE', covered_costs: null }), 'Gratis');
  assert.equal(format.costShort({ cost: 300, type: 'TRAINING_COURSE', covered_costs: null }), 'Cuota 300 €');
  assert.equal(format.costShort({ cost: '12000', type: 'TRAINING_COURSE', covered_costs: null }), 'Cuota 12.000 €');
  assert.equal(format.costShort({ cost: null, type: 'VOLUNTEERING', covered_costs: null }), 'Gratis');
  assert.equal(format.costShort({ cost: null, type: 'YOUTH_EXCHANGE', covered_costs: 'Free of charge' }), 'Gratis');
  assert.equal(format.costShort({ cost: null, type: 'YOUTH_EXCHANGE', covered_costs: null }), null);
});

test('isFillerText', () => {
  for (const t of ['As per the infopack', 'Check the link above.', 'See the info-pack', 'No se especifican', 'Not specified', 'N/A', '', null, 'Ver web']) {
    assert.equal(format.isFillerText(t), true, String(t));
  }
  assert.equal(format.isFillerText('Alojamiento en albergue compartido'), false);
});

test('looksEnglish / looksEnglishShort', () => {
  assert.equal(
    format.looksEnglish('The project will bring together young people from five countries to work on climate and their communities.'),
    true,
  );
  assert.equal(format.looksEnglish('Un intercambio para jóvenes sobre sostenibilidad y participación en la comunidad local.'), false);
  assert.equal(format.looksEnglishShort('Youth exchange for the planet'), true);
  assert.equal(format.looksEnglishShort('Intercambio en Polonia'), false);
});

console.log(`✓ ${passed} pruebas de lógica pura`);
