/**
 * "Cómo apuntarte": pasos fijos para los voluntariados que se solicitan en el Portal Europeo de
 * la Juventud (youth.europa.eu). Mismo aspecto que las demás secciones de texto.
 */
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/text';
import { Colors, Spacing } from '@/constants/theme';

const STEPS = [
  'Regístrate gratis en el Portal Europeo de la Juventud (Cuerpo Europeo de Solidaridad).',
  'Vuelve a esta oferta con «Quiero apuntarme».',
  'Pulsa «Apply» y envía tu perfil.',
];

export function HowToApply() {
  return (
    <View style={styles.section}>
      <AppText variant="title3" accessibilityRole="header">
        Cómo apuntarte
      </AppText>
      <View style={styles.steps}>
        {STEPS.map((step, i) => (
          <View key={step} style={styles.step} accessible accessibilityLabel={`Paso ${i + 1}: ${step}`}>
            <AppText variant="body" color={Colors.ink2} style={styles.num}>
              {i + 1}.
            </AppText>
            <AppText variant="body" color={Colors.ink2} style={styles.text}>
              {step}
            </AppText>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    paddingVertical: Spacing.ml,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.rule,
    gap: Spacing.sm,
  },
  steps: { gap: Spacing.xs },
  step: { flexDirection: 'row', gap: Spacing.sm },
  num: { minWidth: 18 },
  text: { flex: 1 },
});
