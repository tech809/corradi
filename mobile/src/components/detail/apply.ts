/**
 * Lógica del botón principal de la ficha: qué enlace abrir, cómo abrirlo y si el enlace lleva
 * directamente a la inscripción (formulario o Portal Europeo de la Juventud) o solo a la
 * información para apuntarse (Instagram, Facebook, Telegram, un PDF…).
 */
import * as WebBrowser from 'expo-web-browser';
import { Alert, Linking } from 'react-native';

import { Colors } from '@/constants/theme';
import type { Opportunity } from '@/lib/types';

/** `channel_url` (mensaje original de la convocatoria) llega de la API aunque no esté en el tipo. */
type Links = Pick<Opportunity, 'application_url' | 'infopack_url' | 'source_url' | 'type'> & { channel_url?: unknown };

function clean(url: unknown): string | null {
  return typeof url === 'string' && /^https?:\/\//i.test(url.trim()) ? url.trim() : null;
}

function host(url: string): string {
  const m = /^https?:\/\/([^/?#]+)/i.exec(url);
  return (m?.[1] ?? '').toLowerCase().replace(/^www\./, '');
}

function hostIs(h: string, domain: string): boolean {
  return h === domain || h.endsWith(`.${domain}`);
}

/** application_url → infopack_url → source_url → mensaje original (canal). */
export function applyUrl(o: Links): string | null {
  return clean(o.application_url) ?? clean(o.infopack_url) ?? clean(o.source_url) ?? clean(o.channel_url);
}

/** Infopack solo si no es el mismo enlace que el botón principal. */
export function infopackUrl(o: Links): string | null {
  const info = clean(o.infopack_url);
  return info && info !== applyUrl(o) ? info : null;
}

/** Servicios de formularios conocidos (el enlace abre directamente la inscripción). */
const FORM_HOSTS = ['forms.gle', 'forms.office.com', 'forms.microsoft.com', 'typeform.com', 'jotform.com', 'tally.so'];

/** Formulario de inscripción (Google Forms, Microsoft Forms, Typeform, Jotform, Tally). */
export function isFormUrl(url: string | null): boolean {
  if (!url) return false;
  const h = host(url);
  if (hostIs(h, 'docs.google.com')) return /\/forms\//.test(url);
  return FORM_HOSTS.some((d) => hostIs(h, d));
}

/** Portal Europeo de la Juventud (voluntariados del Cuerpo Europeo de Solidaridad). */
export function isPortalUrl(url: string | null): boolean {
  return !!url && hostIs(host(url), 'youth.europa.eu');
}

/**
 * ¿El enlace lleva directamente a la inscripción? Solo un formulario o el Portal Europeo; el
 * resto (redes sociales, Telegram, PDF del infopack, webs) solo explica cómo apuntarse.
 */
export function isDirectApplyUrl(url: string | null): boolean {
  return isFormUrl(url) || isPortalUrl(url);
}

/** Voluntariado que se solicita en el Portal Europeo de la Juventud (pasos "Cómo apuntarte"). */
export function needsEscNotice(o: Links, url: string | null): boolean {
  return o.type === 'VOLUNTEERING' && isPortalUrl(url);
}

export async function openUrl(url: string): Promise<void> {
  try {
    await WebBrowser.openBrowserAsync(url, {
      toolbarColor: Colors.paper,
      controlsColor: Colors.clay,
      dismissButtonStyle: 'close',
    });
  } catch {
    Linking.openURL(url).catch(() => Alert.alert('No se ha podido abrir el enlace', url));
  }
}
