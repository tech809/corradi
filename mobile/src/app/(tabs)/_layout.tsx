import { NativeTabs } from 'expo-router/native-tabs';

import { Colors } from '@/constants/theme';
import { useInterestingNewItems } from '@/state/opportunities';

export default function TabsLayout() {
  // Solo cuenta los tipos que interesan al usuario (como la pestaña Nuevos).
  const newCount = useInterestingNewItems().length;
  const badge = newCount > 99 ? '99+' : newCount > 0 ? String(newCount) : undefined;

  return (
    <NativeTabs
      backgroundColor={Colors.surface}
      indicatorColor={Colors.paper2}
      tintColor={Colors.clay}
      labelStyle={{ selected: { color: Colors.ink } }}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Nuevos</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="sparkles" md="auto_awesome" />
        {badge ? <NativeTabs.Trigger.Badge>{badge}</NativeTabs.Trigger.Badge> : null}
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="explorar">
        <NativeTabs.Trigger.Label>Explorar</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="magnifyingglass" md="search" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="mapa">
        <NativeTabs.Trigger.Label>Mapa</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'map', selected: 'map.fill' }} md="map" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="guardados">
        <NativeTabs.Trigger.Label>Guardados</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'bookmark', selected: 'bookmark.fill' }} md="bookmark" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="ajustes">
        <NativeTabs.Trigger.Label>Ajustes</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'gearshape', selected: 'gearshape.fill' }} md="settings" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
