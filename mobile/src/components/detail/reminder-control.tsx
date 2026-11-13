/**
 * Aviso del plazo, en línea dentro de la fila "Plazo". Un solo modelo: guardado = te avisamos
 * (quitar de guardados cancela el aviso). Aquí solo se enseña el estado:
 * - guardado y con aviso → "Te avisaremos el 9 dic" (texto, no botón)
 * - sin guardar → botón "Guárdalo y te avisamos" (guarda, y guardar programa el aviso)
 * - guardado sin aviso (p. ej. sin permiso cuando se guardó) → botón para poner el aviso
 * - permiso denegado → mensaje (se anuncia) y "Abrir ajustes" (recibe el foco del lector)
 * - sin fecha / ya tarde → el motivo en texto
 */
import { useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, View, type HostInstance } from 'react-native';

import { Button } from '@/components/button';
import { Icon } from '@/components/icon';
import { AppText } from '@/components/text';
import { showToast } from '@/components/toast';
import { Colors, MIN_TOUCH, Radius, Spacing } from '@/constants/theme';
import { announce, focusOn } from '@/lib/a11y';
import { tapSuccess, tapWarning } from '@/lib/haptics';
import type { Opportunity } from '@/lib/types';
import { useReminder, useSavedState, type ToggleResult } from '@/state/opportunities';

import { reminderUnavailableReason, reminderWhen } from './reminder-text';

export interface ReminderControlProps {
  /** Ficha completa: hace falta para guardarla. */
  o: Opportunity;
  /** Distancia del toast sobre el borde inferior seguro (para no tapar la barra de abajo). */
  toastOffset: number;
}

const DENIED_TEXT = 'Las notificaciones de Corradi están desactivadas. Actívalas para que te avisemos.';

export function ReminderControl({ o, toastOffset }: ReminderControlProps) {
  const { on, toggle } = useReminder(o.identifier);
  const { savedIds, toggleSaved } = useSavedState();
  const saved = savedIds.has(o.identifier);
  const [busy, setBusy] = useState(false);
  const [denied, setDenied] = useState(false);
  // Guarda contra el doble toque: el ref cambia al instante, el estado no hasta el render.
  const pending = useRef(false);
  const settingsRef = useRef<HostInstance>(null);
  const when = reminderWhen(o);
  const reason = reminderUnavailableReason(o);

  // Al pasar a "denegado": se lee el mensaje y el foco del lector va a "Abrir ajustes".
  useEffect(() => {
    if (!denied) return;
    announce(DENIED_TEXT);
    return focusOn(settingsRef, 600);
  }, [denied]);

  function reminderSetText() {
    setDenied(false);
    tapSuccess();
    const w = reminderWhen(o);
    return w ? `Te avisaremos el ${w.short} (${w.relative}).` : 'Aviso puesto.';
  }

  /** Pone el aviso de un proyecto ya guardado (aquí el toque es explícito: puede pedir permiso). */
  async function remind(prefix: string): Promise<void> {
    const r = await toggle().catch((): ToggleResult => ({ status: 'error' }));
    switch (r.status) {
      case 'set':
        showToast(`${prefix}${reminderSetText()}`, { icon: 'bellFill', offset: toastOffset });
        return;
      case 'denied':
        tapWarning();
        if (prefix) showToast(prefix.trim(), { icon: 'bookmarkFill', offset: toastOffset });
        setDenied(true);
        return;
      case 'unavailable':
        showToast(`${prefix}${r.reason || reason || 'No podemos avisarte de este plazo.'}`, { offset: toastOffset });
        return;
      default:
        // 'cancelled' no debería pasar (solo se llama sin aviso); por si acaso, se trata como error.
        tapWarning();
        showToast(`${prefix}No hemos podido programar el aviso. Inténtalo de nuevo.`, { offset: toastOffset });
    }
  }

  /** Sin guardar: guardar (programa el aviso). */
  async function saveAndRemind(): Promise<void> {
    const result = await toggleSaved(o.identifier, o);
    if (!result.saved) return;
    switch (result.reminder) {
      case 'set':
      case 'already':
        showToast(`Guardado. ${reminderSetText()}`, { icon: 'bookmarkFill', offset: toastOffset });
        return;
      case 'denied':
        // Guardar solo pide permiso la primera vez; aquí el toque pide el aviso: se pide otra vez
        // (el sistema no vuelve a preguntar si ya se denegó del todo).
        await remind('Guardado. ');
        return;
      default:
        showToast(`Guardado. ${reason ?? 'No podemos avisarte de este plazo.'}`, {
          icon: 'bookmarkFill',
          offset: toastOffset,
        });
    }
  }

  async function onPress() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      if (saved) await remind('');
      else await saveAndRemind();
    } catch {
      tapWarning();
      showToast('No hemos podido guardarlo. Inténtalo de nuevo.', { offset: toastOffset });
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  // Aún no sabemos si hay aviso: no enseñar algo que luego cambia.
  if (on === null) return null;

  if (saved && on) {
    const label = when ? `Te avisaremos el ${when.short}` : 'Te avisaremos antes de que cierre';
    return (
      <View
        style={styles.status}
        accessible
        accessibilityLabel={when ? `${label}, ${when.long}, ${when.relative}` : label}>
        <Icon name="bellFill" size={16} color={Colors.clayText} />
        <AppText variant="label" color={Colors.clayText} style={styles.statusText}>
          {label}
        </AppText>
      </View>
    );
  }

  if (!when) {
    return reason ? (
      <AppText variant="meta" color={Colors.muted}>
        {reason}
      </AppText>
    ) : null;
  }

  if (saved && denied) {
    return (
      <View style={styles.denied}>
        <AppText variant="meta" color={Colors.clayText}>
          {DENIED_TEXT}
        </AppText>
        <Pressable
          ref={settingsRef}
          onPress={() => {
            Linking.openSettings().catch(() => {});
          }}
          accessibilityRole="button"
          accessibilityLabel="Abrir ajustes"
          accessibilityHint="Abre los ajustes del móvil para permitir las notificaciones"
          style={({ pressed }) => [styles.settings, pressed && styles.settingsPressed]}>
          <Icon name="bell" size={18} color={Colors.ink} />
          <AppText variant="button">Abrir ajustes</AppText>
        </Pressable>
      </View>
    );
  }

  // Guardado pero sin aviso (se guardó sin permiso, o el aviso se perdió): se puede poner.
  if (saved) {
    return (
      <Button
        label={when.action}
        icon="bell"
        variant="secondary"
        loading={busy}
        onPress={() => void onPress()}
        accessibilityLabel={when.action.endsWith('del cierre') ? when.action : `${when.action} del cierre`}
        accessibilityHint={`Programa un aviso en este móvil para el ${when.long}`}
        style={styles.btn}
      />
    );
  }

  return (
    <Button
      label="Guárdalo y te avisamos"
      icon="bookmark"
      variant="secondary"
      loading={busy}
      onPress={() => void onPress()}
      accessibilityHint={`Guarda el proyecto y te avisa en este móvil el ${when.long}`}
      style={styles.btn}
    />
  );
}

const styles = StyleSheet.create({
  btn: { alignSelf: 'flex-start', paddingHorizontal: Spacing.md },
  status: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs2 },
  statusText: { flexShrink: 1 },
  denied: { gap: Spacing.sm },
  // Mismo aspecto que <Button variant="secondary">, pero con ref para llevar ahí el foco.
  settings: {
    alignSelf: 'flex-start',
    minHeight: MIN_TOUCH + Spacing.xs, // 48, el alto mínimo de <Button>
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.ms,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.controlBorder,
    backgroundColor: Colors.surface,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  settingsPressed: { backgroundColor: Colors.paper2 },
});
