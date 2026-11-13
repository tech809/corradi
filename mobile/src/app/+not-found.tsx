import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { EmptyState } from '@/components/screen-states';
import { Colors, Spacing } from '@/constants/theme';

/** Enlace a una ruta que no existe (enlace viejo o mal copiado): salida clara a Nuevos. */
export default function NotFoundScreen() {
  return (
    <View style={styles.root}>
      <EmptyState
        title="No encontramos esa página"
        text="Puede que el enlace esté mal copiado o que ya no exista."
        action={{ label: 'Ir a Nuevos', onPress: () => router.dismissTo('/') }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'center', paddingHorizontal: Spacing.md, backgroundColor: Colors.paper },
});
