'use client';

import { useCallback, useSyncExternalStore } from 'react';

export type Lang = 'en' | 'es';

const KEY = 'adk-console-lang';
const listeners = new Set<() => void>();

function read(): Lang {
  if (typeof window === 'undefined') return 'en';
  const q = new URLSearchParams(window.location.search).get('lang');
  if (q === 'es' || q === 'en') return q;
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === 'es' || v === 'en') return v;
  } catch {
    /* storage unavailable */
  }
  return navigator.language?.toLowerCase().startsWith('es') ? 'es' : 'en';
}

export function useLang(): [Lang, (l: Lang) => void] {
  const lang = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    read,
    () => 'en' as Lang,
  );
  const set = useCallback((l: Lang) => {
    try {
      window.localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
    const url = new URL(window.location.href);
    url.searchParams.set('lang', l);
    window.history.replaceState(null, '', url);
    document.documentElement.lang = l;
    listeners.forEach((f) => f());
  }, []);
  return [lang, set];
}

/** Appended to the orchestrator prompt so the agents write the report in Spanish. */
export const ES_PROMPT_SUFFIX =
  ' Write every free-text field of the report (summaries, findings, details and recommendations) in Spanish, but keep JSON keys, enum values such as risk ratings, IDs and numbers exactly as specified.';

export const STRINGS = {
  en: {
    titleA: 'Multi-Agent Risk',
    titleB: 'Compliance Console',
    bff: { ok: 'Connected', degraded: 'Degraded', checking: 'Checking' },
    auth: { oidc: 'OIDC Service Account', local: 'Local Dev Proxy', none: 'Unconfigured', checking: 'Checking…' },
    refresh: 'Refresh BFF and Cloud Run orchestrator health status',
    hidePosture: 'Hide Security Posture',
    showPosture: 'Architecture & Security Posture',
    source: 'Source',
    eyebrow: 'Google ADK 2.15 · A2A v1.0 · Stdio MCP 2.3.0 · Vertex AI gemini-3.8-flash',
    h1a: 'One orchestrator. Specialist agents.',
    h1b: 'Zero public endpoints.',
    lede: 'A Google ADK orchestrator on private Cloud Run delegates over A2A to a financial agent and a compliance agent. Each one reads evidence through its own MCP tools and the orchestrator returns a single, auditable report.',
    requestPath: 'Request path',
    postureTitle: 'Zero-Trust Architecture & Security Posture',
    reachable: 'Reachable via BFF',
    privateRun: 'Private Cloud Run',
    postureLede:
      'Every browser request hits a server-side BFF that mints a short-lived, Google-signed OIDC token scoped to the private orchestrator. Direct calls to any Cloud Run service fail closed with',
    hops: [
      ['Browser', 'Next.js App Router UI', 'Zero GCP credentials · zero client-side env vars'],
      ['Vercel OIDC BFF', '/api/analyze · Node.js', 'google-auth-library getIdTokenClient(aud)'],
      ['Private Cloud Run', 'adk-orchestrator · no allUsers', 'min 0 · max 2 instances · $0 idle'],
      ['A2A v1.0 + OIDC', 'financial & compliance agents', 'CloudRunOidcAuth per-agent audience check'],
      ['Stdio MCP servers', 'GCS · Secret Manager · Vertex AI', 'gemini-3.8-flash · adk-compliance-policy-rules'],
    ],
    casesEyebrow: 'Synthetic enterprise cases',
    casesTitle: '1-Click Synthetic Enterprise Scenarios',
    evidence: 'Evidence in GCS · policy in Secret Manager',
    selected: 'Selected',
    select: 'Select',
    run1: 'Run 1-Click',
    activeScenario: 'Active scenario',
    prompt: 'Orchestrator prompt',
    adhoc: 'Optional Ad-Hoc Document Text',
    persist: 'Persist report to GCS',
    runAll: 'Run Multi-Agent Analysis',
    running: 'Running A2A + MCP Agents…',
    adhocLabel: 'Custom document JSON / memo text (optional override)',
    adhocPh: 'Paste a financial statement JSON or a compliance memo for ad-hoc analysis…',
    execError: 'Execution Error',
    promptShort: 'Prompt must be at least 5 characters.',
    unreachable: 'Unable to reach BFF /api/analyze endpoint. Check /api/health and try again.',
    built: 'Built by Daniel Tafur · AI Agent Engineer',
    working: [
      'Orchestrator plans the task',
      'A2A → financial_analysis_agent',
      'A2A → audit_compliance_agent',
      'MCP tools read GCS + Secret Manager',
      'Gemini synthesises the report',
    ],
    workingEyebrow: 'Agents at work · cold start can take ~1 min',
    liveDelegation: 'Live delegation',
    traceTitle: 'Multi-Agent A2A & MCP Execution Trace',
    executing: 'Executing A2A delegation…',
    hopsRecorded: 'A2A hops recorded',
    mcpTools: 'MCP tools',
    traceEmpty:
      'Pick a scenario and run it to watch the orchestrator delegate over A2A, the OIDC audience checks on each hop, and the MCP tools every agent calls.',
    prov: ['Vertex AI model', 'GCS bucket', 'Secret Manager policy', 'Persisted report'],
    notPersisted: 'Not persisted (dry run)',
    reportEyebrow: 'Synthesised by the orchestrator',
    reportTitle: 'Executive Risk & Compliance Report',
    showJson: 'Show Raw JSON',
    hideJson: 'Hide Raw JSON',
    copyJson: 'Copy JSON',
    copied: 'Copied JSON',
    copyAria: 'Copy full analysis JSON report to clipboard',
    risk: { LOW: 'LOW RISK', MEDIUM: 'MEDIUM RISK', HIGH: 'HIGH RISK', CRITICAL: 'CRITICAL RISK' },
    low: 'low',
    critical: 'critical',
    summary: 'Executive summary',
    finTitle: 'Financial Analysis',
    anomalies: 'Financial anomalies',
    noAnomalies: 'No material financial anomalies flagged.',
    sources: 'Sources',
    compTitle: 'Compliance & Controls Audit',
    compliant: 'COMPLIANT',
    nonCompliant: 'NON-COMPLIANT',
    policyId: 'Policy ID',
    controls: 'Controls evaluated',
    noControls: 'No individual controls listed.',
    violations: 'Control violations',
    noViolations: 'Zero compliance violations detected.',
    recs: 'Actionable recommendations',
    noRecs: 'No remediation actions required.',
    rawJson: 'Raw orchestrator JSON response',
  },
  es: {
    titleA: 'Consola multiagente de riesgo',
    titleB: 'cumplimiento',
    bff: { ok: 'Conectado', degraded: 'Degradado', checking: 'Verificando' },
    auth: { oidc: 'Service Account OIDC', local: 'Proxy local', none: 'Sin configurar', checking: 'Verificando…' },
    refresh: 'Actualizar el estado del BFF y del orquestador en Cloud Run',
    hidePosture: 'Ocultar postura de seguridad',
    showPosture: 'Arquitectura y postura de seguridad',
    source: 'Código',
    eyebrow: 'Google ADK 2.15 · A2A v1.0 · Stdio MCP 2.3.0 · Vertex AI gemini-3.8-flash',
    h1a: 'Un orquestador. Agentes especialistas.',
    h1b: 'Cero endpoints públicos.',
    lede: 'Un orquestador con Google ADK en Cloud Run privado delega vía A2A a un agente financiero y a uno de cumplimiento. Cada uno lee la evidencia con sus propias herramientas MCP y el orquestador devuelve un único reporte auditable.',
    requestPath: 'Ruta de la petición',
    postureTitle: 'Arquitectura zero-trust y postura de seguridad',
    reachable: 'Accesible vía BFF',
    privateRun: 'Cloud Run privado',
    postureLede:
      'Cada petición del navegador llega a un BFF en servidor que genera un token OIDC de Google de corta duración, limitado al orquestador privado. Las llamadas directas a cualquier servicio de Cloud Run se rechazan con',
    hops: [
      ['Navegador', 'UI con Next.js App Router', 'Cero credenciales de GCP · cero variables en el cliente'],
      ['BFF OIDC en Vercel', '/api/analyze · Node.js', 'google-auth-library getIdTokenClient(aud)'],
      ['Cloud Run privado', 'adk-orchestrator · sin allUsers', 'mín. 0 · máx. 2 instancias · $0 en reposo'],
      ['A2A v1.0 + OIDC', 'agentes financiero y de cumplimiento', 'CloudRunOidcAuth verifica la audiencia por agente'],
      ['Servidores MCP stdio', 'GCS · Secret Manager · Vertex AI', 'gemini-3.8-flash · adk-compliance-policy-rules'],
    ],
    casesEyebrow: 'Casos empresariales sintéticos',
    casesTitle: 'Escenarios empresariales en 1 clic',
    evidence: 'Evidencia en GCS · política en Secret Manager',
    selected: 'Seleccionado',
    select: 'Seleccionar',
    run1: 'Ejecutar',
    activeScenario: 'Escenario activo',
    prompt: 'Prompt del orquestador',
    adhoc: 'Documento ad hoc opcional',
    persist: 'Guardar reporte en GCS',
    runAll: 'Ejecutar análisis multiagente',
    running: 'Ejecutando agentes A2A + MCP…',
    adhocLabel: 'JSON de documento o texto de memo (reemplazo opcional)',
    adhocPh: 'Pega un JSON de estados financieros o un memo de cumplimiento para un análisis ad hoc…',
    execError: 'Error de ejecución',
    promptShort: 'El prompt debe tener al menos 5 caracteres.',
    unreachable: 'No se pudo contactar /api/analyze en el BFF. Revisa /api/health e inténtalo de nuevo.',
    built: 'Hecho por Daniel Tafur · AI Agent Engineer',
    working: [
      'El orquestador planifica la tarea',
      'A2A → agente de análisis financiero',
      'A2A → agente de auditoría de cumplimiento',
      'Las herramientas MCP leen GCS + Secret Manager',
      'Gemini sintetiza el reporte',
    ],
    workingEyebrow: 'Agentes trabajando · el arranque en frío puede tardar ~1 min',
    liveDelegation: 'Delegación en vivo',
    traceTitle: 'Traza de ejecución multiagente A2A y MCP',
    executing: 'Ejecutando delegación A2A…',
    hopsRecorded: 'saltos A2A registrados',
    mcpTools: 'Herramientas MCP',
    traceEmpty:
      'Elige un escenario y ejecútalo para ver cómo el orquestador delega vía A2A, la verificación OIDC en cada salto y las herramientas MCP que usa cada agente.',
    prov: ['Modelo de Vertex AI', 'Bucket de GCS', 'Política en Secret Manager', 'Reporte guardado'],
    notPersisted: 'No guardado (ejecución de prueba)',
    reportEyebrow: 'Sintetizado por el orquestador',
    reportTitle: 'Reporte ejecutivo de riesgo y cumplimiento',
    showJson: 'Ver JSON',
    hideJson: 'Ocultar JSON',
    copyJson: 'Copiar JSON',
    copied: 'JSON copiado',
    copyAria: 'Copiar el reporte JSON completo al portapapeles',
    risk: { LOW: 'RIESGO BAJO', MEDIUM: 'RIESGO MEDIO', HIGH: 'RIESGO ALTO', CRITICAL: 'RIESGO CRÍTICO' },
    low: 'bajo',
    critical: 'crítico',
    summary: 'Resumen ejecutivo',
    finTitle: 'Análisis financiero',
    anomalies: 'Anomalías financieras',
    noAnomalies: 'No se detectaron anomalías financieras materiales.',
    sources: 'Fuentes',
    compTitle: 'Auditoría de cumplimiento y controles',
    compliant: 'CUMPLE',
    nonCompliant: 'NO CUMPLE',
    policyId: 'ID de política',
    controls: 'Controles evaluados',
    noControls: 'No se listaron controles individuales.',
    violations: 'Violaciones de control',
    noViolations: 'Cero violaciones de cumplimiento.',
    recs: 'Recomendaciones accionables',
    noRecs: 'No se requieren acciones de remediación.',
    rawJson: 'Respuesta JSON del orquestador',
  },
} as const;

export const SCENARIO_ES: Record<string, { title: string; description: string; signal: string }> = {
  q3_cloud_vendor_review: {
    title: 'Revisión de gasto en proveedores de nube e IA (Q3)',
    description:
      'Revisión del gasto en infraestructura de nube y proveedores de IA del Q3 FY2026 de Meridian Retail Analytics Corp.: sobrecosto del +28% frente al presupuesto y falta de doble aprobación de Finanzas en una ampliación de GPU de $660k.',
    signal: 'RIESGO ALTO · Variación +28% / falta doble aprobación',
  },
  series_b_revenue_audit: {
    title: 'Reconocimiento de ingresos Serie B y preparación de auditoría (Q3)',
    description:
      'Paquete de auditoría ASC 606 del Q3 FY2026 de Northwind Cloud Robotics Inc.: línea base limpia con +1.43% de variación, dobles aprobaciones completas, reportes SOC2 de proveedores verificados y segregación de funciones intacta.',
    signal: 'RIESGO BAJO · ASC 606 / SOC2 en regla',
  },
  treasury_controls_memo: {
    title: 'Controles de transferencias de tesorería y excepciones de proveedores',
    description:
      'Revisión de desembolsos de tesorería y alta de proveedores del Q3 FY2026 de Helios FinTech Payments Inc.: autoaprobación que rompe la segregación de funciones, reportes SOC2 vencidos o sin verificar, dobles aprobaciones faltantes, sobrecosto del +22% y partidas en suspenso sin conciliar.',
    signal: 'RIESGO CRÍTICO · Autoaprobación y proveedor sin validar',
  },
};
