/*
 * Italian console copy. Typed against the English catalogue in
 * `lib/strings.ts`, which stays the source of truth: every key and every
 * template function must exist here with the same signature, or typecheck
 * fails.
 *
 * Register: formal and impersonal, for operators of enterprise and
 * public-sector deployments. Instructions use the "Lei" form; buttons and
 * menu items use the infinitive. Terms that Italian IT practice keeps in
 * English stay in English (workflow, tenant, audit, policy, SSO, API, egress,
 * dashboard, runtime, provider); "connector" is "connettore". Product names
 * are never translated. `{placeholder}` tokens and template parameters must
 * survive translation unchanged.
 */
import type { ConsoleGlossary, ConsoleStrings } from "@/lib/i18n";

const count = (value: number) => value.toLocaleString("it");

export const glossaryIt: ConsoleGlossary = {
  ontology: {
    label: "Ontologia",
    definition:
      "Il vocabolario condiviso degli oggetti di business (macchinari, ordini, materiali) che collega dati, agenti e policy, così che ogni sistema faccia riferimento alle stesse entità.",
  },
  autonomy_level: {
    label: "Livello di autonomia",
    definition:
      "Quanto un agente può fare in autonomia. Ai livelli più bassi si limita a suggerire azioni che vengono eseguite da persone; ai livelli più alti può agire direttamente, sempre nel rispetto di policy e approvazioni.",
  },
  egress: {
    label: "Egress",
    definition:
      "L'uscita di dati dalla piattaforma verso un sistema o un fornitore esterno. L'egress è bloccato per impostazione predefinita e viene consentito solo da una policy esplicita.",
  },
  evidence: {
    label: "Evidenza",
    definition:
      "La prova registrata alla base di una decisione o di un'azione: chi ha agito, quali informazioni aveva e quali regole sono state applicate. Le evidenze vengono scritte nel registro di audit e non possono essere modificate in seguito.",
  },
  dry_run: {
    label: "Esecuzione di prova",
    definition:
      "Una prova di un'azione che ne calcola l'esito senza modificare nulla. Serve a verificare cosa accadrebbe prima di procedere.",
  },
  replay: {
    label: "Replay",
    definition:
      "La rielaborazione di decisioni passate con un diverso insieme di policy, per confrontarne gli esiti. Durante un replay nulla cambia in produzione.",
  },
  idempotency: {
    label: "Idempotenza",
    definition:
      "La garanzia che ripetere la stessa richiesta non produca effetti aggiuntivi. Rende sicuri i nuovi tentativi dopo un timeout o un errore di rete.",
  },
  connector_manifest: {
    label: "Manifest del connettore",
    definition:
      "La descrizione verificata di un connettore: da dove provengono i dati, come i campi corrispondono all'ontologia e quali regole governano ogni sincronizzazione.",
  },
  policy_scope: {
    label: "Ambito della policy",
    definition:
      "La parte della piattaforma a cui si applica una policy: un intero tenant, un dominio o un tipo specifico di azione.",
  },
};

const nav = {
  operate: "Operatività",
  dataAndModels: "Dati e modelli",
  governance: "Governance",
  platform: "Piattaforma",
  help: "Assistenza",
  signedOut: "Accesso non effettuato",
  noTenant: "Nessun tenant selezionato",
} as const;

const scopeDenial = {
  title: "I Suoi ruoli non includono questa autorizzazione",
  bodyPrefix: "Axis ha verificato la Sua sessione, ma la sezione",
  bodySuffix:
    "richiede un'autorizzazione che i ruoli assegnati non concedono. Chieda a un amministratore delle identità di assegnarla, quindi ricarichi la pagina.",
  permissionLabel: "Autorizzazione richiesta",
} as const;

const identityGate = {
  eyebrow: "Accesso aziendale",
  title: "Accesso a Limes Axis",
  description:
    "Questa installazione richiede una sessione operatore autenticata tramite il provider di identità della Sua organizzazione.",
  signIn: "Accedere con SSO",
  returnHint: "Al termine tornerà alla pagina che aveva aperto.",
  ssoNotConfigured: {
    title: "Il single sign-on non è ancora configurato.",
    detail:
      "Per questa installazione non è configurato l'accesso dal browser. Un amministratore deve impostare sull'API di Axis il client ID OIDC e il segreto di firma del cookie di sessione.",
  },
  reasons: {
    missing_authorization: "Non è stata trovata alcuna sessione attiva per questo browser.",
    invalid_session_cookie: "La sessione non è più valida. Acceda di nuovo per continuare.",
    revoked_session_cookie: "La sessione è stata revocata. Acceda di nuovo per continuare.",
    expired_session_cookie: "La sessione è scaduta. Acceda di nuovo per continuare.",
    idle_session_timeout:
      "La sessione è stata chiusa per inattività. Acceda di nuovo per continuare.",
    fallback: "Non è stato possibile verificare le credenziali. Acceda di nuovo per continuare.",
  },
} as const;

const pages = {
  overview: {
    eyebrow: nav.operate,
    title: "Panoramica",
    description:
      "Trasformi i dati aziendali collegati in azioni che il team può esaminare e monitorare.",
  },
  approvals: {
    eyebrow: nav.operate,
    title: "Approvazioni",
    description: "Esamini le azioni proposte e ne segua gli esiti segnalati.",
  },
  workflows: {
    eyebrow: nav.operate,
    title: "Workflow",
    description: "Monitori l'avanzamento dei workflow e risolva i blocchi.",
  },
  agents: {
    eyebrow: nav.operate,
    title: "Agenti",
    description: "Verifichi cosa può fare ciascun agente ed esamini le sue esecuzioni.",
  },
  ontology: {
    eyebrow: nav.dataAndModels,
    title: "Ontologia",
    description:
      "Esplori gli oggetti di business, come ordini e macchinari, e le loro relazioni.",
  },
  connectors: {
    eyebrow: nav.dataAndModels,
    title: "Connettori",
    description: "Colleghi le fonti dati e ne monitori le importazioni.",
  },
  data: {
    eyebrow: nav.dataAndModels,
    title: "Dati",
    description:
      "Trovi gli asset di dati, ne verifichi le evidenze e ne assegni la responsabilità.",
  },
  "model-routing": {
    eyebrow: nav.dataAndModels,
    title: "Modelli",
    description: "Esamini le regole di selezione dei modelli e le chiamate AI registrate.",
  },
  policies: {
    eyebrow: nav.governance,
    title: "Policy",
    description: "Definisca le regole per azioni, accesso ai dati e approvazione umana.",
  },
  audit: {
    eyebrow: nav.governance,
    title: "Audit",
    description: "Ricostruisca azioni e decisioni registrate e le evidenze che le motivano.",
  },
  simulation: {
    eyebrow: nav.governance,
    title: "Simulazione",
    description: "Confronti gli esiti delle policy prima di applicare le modifiche.",
  },
  tenants: {
    eyebrow: nav.platform,
    title: "Tenant",
    description: "Gestisca le organizzazioni e i relativi limiti di risorse.",
  },
  settings: {
    eyebrow: nav.platform,
    title: "Impostazioni",
    description:
      "Verifichi che la piattaforma sia integra, connessa e pronta per il team.",
  },
} as const;

const routeError = {
  eyebrow: "Console",
  title: "Si è verificato un errore",
  subtitle: "Questa schermata ha smesso di rispondere. Il resto della console funziona regolarmente.",
  panelTitle: "Impossibile visualizzare questa schermata",
  detail:
    "Axis ha interrotto la visualizzazione della pagina per non mostrare una vista incompleta o fuorviante. Riprovando verrà ricaricata solo questa schermata.",
} as const;

const notFound = {
  eyebrow: "Console",
  title: "Pagina non trovata",
  subtitle: "Questo indirizzo non corrisponde ad alcuna risorsa di questa installazione.",
  panelTitle: "A questo indirizzo non c'è nulla",
  detail:
    "Il link potrebbe non essere aggiornato oppure il record potrebbe appartenere a un altro tenant. Ricominci dalla panoramica.",
  action: "Andare alla panoramica",
} as const;

const globalError = {
  title: "Impossibile avviare Axis Console",
  detail:
    "La console si è interrotta prima del caricamento. Ricarichi la pagina; se il problema persiste, comunichi al team di piattaforma il riferimento riportato di seguito.",
  action: "Ricaricare la console",
} as const;

const shell = {
  brand: "Limes Axis",
  controlPlane: "Piano di controllo",
  homeLink: "Limes Axis Piano di controllo, pagina iniziale",
  menu: "Menu",
  menuLabel: (section: string) => `Menu, sezione corrente: ${section}`,
  notifications: "Aprire le notifiche",
  notificationsLabel: (badge: string) => `Aprire le notifiche, ${badge} non lette`,
  account: "Aprire l'account operatore",
  accountLabel: (visible: string) => `${visible}, aprire l'account operatore`,
  theme: {
    trigger: "Tema colori",
    triggerLabel: (current: string) => `Tema colori: ${current}`,
    options: { system: "Sistema", light: "Chiaro", dark: "Scuro" },
  },
  locale: {
    label: "Lingua",
    detail: "La modifica della lingua ricarica la console.",
  },
} as const;

const commandMenu = {
  trigger: "Andare a…",
  dialogTitle: "Andare a…",
  inputLabel: "Andare a una pagina, un'entità o un'azione",
  placeholder: "Andare a una pagina, un'entità o un'azione…",
  empty: "Nessun comando corrispondente.",
  apiStatus: "Stato dell'API",
  actionsHeading: "Azioni",
  entitiesHeading: "Entità",
  refresh: {
    label: "Aggiornare lo stato in tempo reale",
    detail: "Ricarica tutte le console basate sull'API.",
  },
  toggleTheme: {
    label: "Cambiare il tema colori",
    detail: "Alterna tra tema chiaro e scuro.",
  },
  docs: {
    label: "Aprire la documentazione del prodotto",
    detail: "Documentazione di architettura, piattaforma e collaudo.",
    href: "https://github.com/Limes-Labs/limes-axis/tree/main/docs",
  },
} as const;

const approvals = {
  queue: {
    eyebrow: "Coda",
    title: "Approvazioni in attesa",
    filters: "Filtri della coda di approvazione",
    search: "Cercare nelle approvazioni",
    searchPlaceholder: "Azione, responsabile o workflow…",
    risk: "Rischio",
    allRisks: "Tutti i livelli di rischio",
    domain: "Dominio",
    allDomains: "Tutti i domini",
    clear: "Cancellare i filtri",
    noMatches:
      "Nessuna approvazione in attesa corrisponde a questi filtri. Provi un'altra ricerca o cancelli i filtri.",
    review: "Esame dell'approvazione",
    back: "Torna alle approvazioni in attesa",
    select: "Selezioni un'approvazione da esaminare",
    selectDetail:
      "Scelga un'azione corrispondente nella coda per visualizzarne le evidenze e le opzioni di decisione.",
  },
  history: {
    eyebrow: "Cronologia",
    title: "Cronologia delle decisioni",
    description:
      "Decisioni definitive registrate nel registro di audit. Le approvazioni decise non compaiono più nella coda.",
    empty: "Non è ancora stata registrata alcuna decisione definitiva.",
    followThrough: "Seguito:",
    actorUnknown: "attore sconosciuto",
  },
  decision: {
    eyebrow: "Decisione",
    pending: "In attesa di esame",
    confirmTitle: "Conferma della decisione",
    rationaleLabel: "Motivazione (facoltativa)",
    rationalePlaceholder:
      "Perché ha preso questa decisione: verrà registrato insieme alle evidenze di audit.",
    confirm: "Confermare la decisione",
    cancel: "Annullare",
    persisting: "Registrazione della decisione…",
    persisted: "Registrata come evidenza",
    auditLink: "Visualizzare l'evento di audit",
    toastTitle: "Decisione registrata",
    ssoGate: "Acceda con SSO per registrare le decisioni di approvazione.",
    alreadyRecorded: "Per questa approvazione è già stata registrata una decisione definitiva.",
  },
  sections: {
    evidence: "Evidenze",
    risksAlternatives: "Rischi e alternative",
    dataAccessed: "Dati consultati",
    inspect: "Esaminare il record originale",
  },
  metrics: {
    pending: "In attesa",
    pendingDetail: "In attesa di una decisione umana",
    highRisk: "Rischio elevato",
    highRiskDetail: "Non eseguibile senza l'approvazione del responsabile",
    decided: "Decise",
    decidedDetail: "Registrate come evidenze di audit",
  },
  error: {
    title: "API delle approvazioni non disponibile",
    detail:
      "Axis non ha ricevuto record di approvazione dall'API. I record di approvazione locali di riserva sono disattivati.",
  },
  empty: {
    title: "Nessuna approvazione in attesa",
    detail:
      "Quando un agente propone un'azione che richiede una decisione umana, questa comparirà qui per l'esame.",
  },
  requestedMissing: {
    title: "L'approvazione richiesta non è in questa coda",
    detail:
      "L'esecuzione dell'azione collegata non ha un'approvazione nella coda corrente. Potrebbe essere già stata decisa o appartenere a un altro tenant.",
  },
  lookupError: {
    title: "Impossibile verificare l'approvazione collegata",
    detail:
      "Axis non è riuscito a risalire all'esecuzione dell'azione tramite il registro di audit, pertanto la console non mostrerà un'approvazione diversa.",
  },
  followThrough: {
    eyebrow: "Seguito",
    title: "Dopo la decisione",
    detail:
      "Axis registra la decisione e mostra quanto segnalato dagli esecutori esterni. Axis non esegue né ritenta le azioni approvate.",
    sourceSubject: "seguito delle azioni",
    awaiting: {
      title: "In attesa di esecuzione esterna",
      detail:
        "Azioni approvate senza esito segnalato, a partire dall'attesa più lunga. Ciascuna resta qui finché un esecutore esterno non ne comunica l'esito.",
      status: "In attesa dell'esecutore esterno",
      waited: (duration: string) => `In attesa da ${duration}`,
      emptyTitle: "Nessuna azione in attesa di esecuzione esterna",
      emptyDetail:
        "Al momento nessuna azione approvata è in attesa dell'esito da parte di un esecutore esterno.",
    },
    reported: {
      title: "Esiti segnalati",
      detail: "Quanto comunicato ad Axis dagli esecutori esterni dopo un'approvazione.",
      emptyTitle: "Nessun esito segnalato",
      emptyDetail:
        "Nessun esecutore esterno ha ancora segnalato l'esito di un'azione approvata.",
    },
    empty: {
      title: "Nessuna azione ancora approvata",
      detail:
        "Le esecuzioni delle azioni approvate e gli esiti segnalati dagli esecutori compariranno qui dopo la registrazione di una decisione.",
    },
    error: {
      title: "API delle esecuzioni delle azioni non disponibile",
      detail:
        "Axis non è riuscito a caricare le esecuzioni delle azioni approvate o gli esiti segnalati dagli esecutori. Non viene dedotto alcuno stato.",
    },
    stale:
      "Aggiornamento non riuscito. Vengono mostrati gli ultimi dati convalidati sul seguito delle azioni.",
    links: {
      approval: "Aprire l'approvazione di autorizzazione",
      auditEvidence: "Aprire le evidenze di audit",
    },
    fields: {
      approved: "Approvata",
      reported: "Segnalata",
      workflow: "Workflow",
      run: "Esecuzione",
      noWorkflow: "Nessun workflow registrato",
      noApproval: "Nessuna approvazione di autorizzazione registrata",
      noAuditEvidence: "Nessun riferimento a evidenze di audit segnalato",
    },
  },
} as const;

const agents = {
  list: {
    eyebrow: "Registro",
    title: "Agenti",
  },
  tabs: {
    overview: "Panoramica",
    permissions: "Autorizzazioni e limiti",
    runs: "Esecuzioni",
    evidence: "Evidenze",
  },
  overview: {
    owner: "Responsabile",
    boundary: "Perimetro operativo",
    modelPolicy: "Policy del modello",
    connectedSystems: "Sistemi collegati",
    dataAccess: "Accesso ai dati",
  },
  permissions: {
    required: "Autorizzazioni richieste",
    guardrails: "Limiti di sicurezza",
    allowed: "Azioni consentite",
    blocked: "Azioni bloccate",
  },
  evidence: {
    proposals: "Proposte di azione",
    proposalsDetail:
      "Proposte in sola lettura registrate da questo agente; l'esecuzione richiede un'approvazione.",
    workflows: "Collegamenti ai workflow",
    approvals: "Riferimenti alle approvazioni",
    audit: "Collegamenti di audit",
    lastAudit: "Ultimo evento di audit",
    approvalRequired: "Richiede approvazione",
    noApproval: "Nessuna approvazione necessaria",
    empty:
      "Per questo agente non sono registrati proposte, collegamenti ai workflow o riferimenti alle approvazioni.",
  },
  runs: {
    title: "Esecuzioni effettive",
    detail:
      "Record di esecuzione persistiti; passaggi, collegamenti ai modelli e proposte sono valori registrati.",
    liveBadge: "Eseguita",
    dryRun: "Esecuzione di prova",
    linkedInvocations: "Invocazioni di modelli collegate",
    noInvocations: "A questa esecuzione non è collegata alcuna invocazione di modelli.",
    openActionRun: "Aprire nelle approvazioni l'esecuzione dell'azione proposta",
    noActionRun: "Questa esecuzione non ha creato alcuna esecuzione di azione.",
    openRunAudit: "Aprire l'evento di audit dell'esecuzione",
    openAudit: "Aprire l'audit",
    auditPending: "audit in attesa",
    empty: {
      title: "Nessuna esecuzione registrata",
      detail:
        "Per questo agente non sono registrate esecuzioni. L'esecuzione degli agenti è rinviata per impostazione predefinita finché il relativo flag non viene attivato sull'API; le righe di esecuzione non vengono mai inventate.",
    },
    error: {
      title: "API delle esecuzioni degli agenti non disponibile",
      detail:
        "Axis non ha ricevuto i record di esecuzione persistiti per questo agente. Le cronologie delle esecuzioni non vengono mai inventate.",
    },
    detailError: {
      title: "Dettaglio dell'esecuzione non disponibile",
      detail:
        "Axis non ha ricevuto i record persistiti dei passaggi di questa esecuzione. Le cronologie dei passaggi non vengono mai inventate.",
    },
  },
  inspect: "Esaminare il record originale",
  error: {
    title: "API degli agenti non disponibile",
    detail:
      "Axis non ha ricevuto record degli agenti dall'API. I record degli agenti locali di riserva sono disattivati.",
  },
  empty: {
    title: "Nessun agente registrato",
    detail:
      "Registri un agente tramite l'API della piattaforma: comparirà qui con il proprio perimetro di policy e la cronologia delle esecuzioni.",
  },
  noMatch: {
    title: "Nessun agente corrisponde ai filtri correnti",
    detail:
      "Modifichi o reimposti i filtri per dominio, autonomia e stato per visualizzare gli agenti registrati.",
    reset: "Reimpostare i filtri",
  },
} as const;

const workflows = {
  list: {
    eyebrow: "Esecuzioni",
  },
  filters: {
    state: "Stato",
    allStates: "Tutti gli stati",
    domain: "Dominio",
    allDomains: "Tutti i domini",
  },
  blocker: {
    title: "In attesa di una decisione umana",
    linkNamed: "Esaminare l'approvazione bloccante",
    linkGeneric: "Aprire le approvazioni",
  },
  timeline: {
    eyebrow: "Cronologia",
    title: "Cronologia di esecuzione",
    waiting: "in attesa",
    columns: {
      step: "Passaggio",
      result: "Risultato",
      when: "Quando",
      summary: "Riepilogo",
    },
  },
  sections: {
    inputs: "Input",
    outputs: "Output proposti",
    context: "Contesto correlato",
  },
  detail: {
    runtime: "Runtime",
    owner: "Responsabile",
    autonomy: "Autonomia",
    started: "Avviato",
    expected: "Previsto",
    auditScope: "Ambito di audit",
    replay: "Replay",
    replayReady: "Pronto per il replay",
    replayNotReady: "Non ancora pronto per il replay",
    signals: "Segnali in attesa",
    noSignals: "Nessun elemento è in attesa di questo workflow.",
    controls: "Controlli",
  },
  inspect: "Esaminare il record originale",
  error: {
    title: "API dei workflow non disponibile",
    detail:
      "Axis non ha ricevuto record dei workflow dall'API. I record dei workflow locali di riserva sono disattivati.",
  },
  empty: {
    title: "Nessuna esecuzione di workflow",
    detail:
      "Un workflow governato si avvia quando viene decisa un'approvazione. L'esecuzione comparirà quindi qui con una cronologia passo per passo.",
    action: "Esaminare le approvazioni in attesa",
  },
  noMatch: {
    title: "Nessun workflow corrisponde ai filtri correnti",
    detail:
      "Modifichi o reimposti i filtri per stato e dominio per visualizzare le esecuzioni dei workflow.",
    reset: "Reimpostare i filtri",
  },
} as const;

const connectors = {
  partialCsvPreview: (included: number, total: number) =>
    `L'anteprima include ${count(included)} record su ${count(total)}. ${count(total - included)} record non sono inclusi.`,
  list: {
    eyebrow: "Registro",
    neverSampled: "Mai campionato",
    previewSample: "Campione di anteprima",
    observedRecords: (value: number) => `${count(value)} record osservati`,
    successfulSync: (completedAt: string, runId: string) =>
      `Sincronizzazione riuscita · ${completedAt} · esecuzione ${runId}`,
  },
  header: {
    addConnector: "Aggiungere un connettore",
    updated: "Aggiornato",
  },
  manifestImport: {
    eyebrow: "Portabilità dei manifest",
    title: "Importazione dei manifest dei connettori",
    description:
      "Incolli un documento di registrazione o un array, oppure carichi un file JSON. L'intero lotto viene verificato prima di qualsiasi scrittura.",
    access:
      "Ambito richiesto: nessuno. L'API richiede invece che tenant e attore registrato corrispondano alla sessione con cui ha effettuato l'accesso.",
    validationEndpoint: "Endpoint dell'esecuzione di prova",
    applyEndpoint: "Endpoint di applicazione",
    applyEndpointPaths: (endpoint: string) =>
      `POST ${endpoint}; PUT ${endpoint}/{connector_id}`,
    inputLabel: "JSON del documento di registrazione",
    inputPlaceholder: "Incolli un documento di registrazione o un array di documenti",
    fileLabel: "Caricare un file JSON",
    fileReadError: "Impossibile leggere il file JSON selezionato.",
    check: "Verificare",
    checking: "Verifica in corso…",
    reviewApply: "Esaminare l'applicazione",
    apply: "Applicare i manifest",
    applying: "Applicazione in corso…",
    cancel: "Annullare",
    confirmation: (value: number) =>
      `Applicare in sequenza ${value === 1 ? "il manifest verificato" : `i ${value} manifest verificati`}? Le scritture non possono essere annullate come lotto unico.`,
    ssoGate: "Acceda con SSO per verificare o applicare i manifest dei connettori.",
    errors: {
      malformed: "Il contenuto non è un JSON valido. Corregga la sintassi prima della verifica.",
      shape: "Fornisca un oggetto JSON o un array non vuoto di oggetti JSON.",
      tooMany: (value: number, maximum: number) =>
        `Sono stati forniti ${value} documenti. È possibile verificarne al massimo ${maximum} alla volta.`,
      validationRequest: "Impossibile completare l'esecuzione di prova dei manifest.",
      replacementRevisionRequest:
        "Impossibile verificare la revisione corrente del connettore: la sostituzione resta disattivata.",
      tenantMismatch: "La risposta dell'esecuzione di prova appartiene a un altro tenant.",
      resultCountMismatch:
        "La risposta dell'esecuzione di prova non contiene un risultato per ogni documento.",
    },
    summary: {
      title: "Riepilogo dell'esecuzione di prova",
      wouldRegister: "Da registrare",
      wouldReplace: "Da sostituire",
      invalid: "Non validi",
    },
    table: {
      document: "Documento",
      connector: "ID connettore",
      outcome: "Esito",
      applyResult: "Risultato dell'applicazione",
      unknownConnector: "Non disponibile",
      replacesRevision: (revision: number) => `Sostituisce la revisione ${revision}`,
    },
    outcomes: {
      would_register: "Da registrare",
      would_replace: "Da sostituire",
      invalid: "Non valido",
    },
    applyResults: {
      landed: "Applicato",
      failed: "Non riuscito",
      conflict: "Modifica concorrente",
      notAttempted: "Non applicato",
      pending: "In attesa",
    },
    applyability: (invalid: number, total: number) => invalid === 0
      ? `0 su ${total} verranno rifiutati. Tutti i documenti verificati possono essere applicati.`
      : `${invalid} su ${total} verranno rifiutati perché non validi. L'applicazione resta disattivata finché tutti i documenti non sono validi.`,
    applySuccess: (value: number) =>
      `Sono stati applicati ${value} manifest su ${value}.`,
    applyFailure: (landed: number, total: number) =>
      `Sono stati applicati ${landed} manifest su ${total}. I documenti rimanenti non sono stati applicati.`,
    concurrentConflict: (connectorId: string) =>
      `Applicazione interrotta perché un altro utente ha modificato ${connectorId}. Verifichi di nuovo il lotto prima di sostituirlo.`,
    toast: {
      success: "Manifest dei connettori applicati",
      partial: "Applicazione dei manifest interrotta",
    },
  },
  manifestExport: {
    action: "Esportare il manifest",
    title: "Documento di registrazione",
    description:
      "Questo JSON formattato include manifest, policy di runtime, eventuale campione di anteprima e note necessarie per il replay.",
    jsonLabel: "JSON del documento di registrazione",
    copy: "Copiare il JSON",
    copied: "Documento di registrazione copiato",
    copyFailed: "Impossibile copiare il documento di registrazione.",
    download: "Scaricare il JSON",
    close: "Chiudere l'esportazione",
  },
  lifecycle: {
    eyebrow: "Ciclo di vita",
    title: "Stato di attivazione",
    ssoGate: "Acceda con SSO per modificare l'attivazione del connettore.",
    stateDetail: {
      registered_preview_only:
        "Registrato solo per le anteprime. Convalidi le corrispondenze ed esamini lo schema; sincronizzazioni governate e proposte di ontologia restano bloccate finché il connettore non viene attivato.",
      active_preview:
        "Attivato per le operazioni di anteprima. Sono disponibili esecuzioni governate, lease delle credenziali e proposte di ontologia; i sistemi esterni non vengono ancora interessati.",
      active_live:
        "Operatività live abilitata entro il perimetro di egress verificato. Le sincronizzazioni pianificate e live possono raggiungere il sistema collegato nei limiti della policy.",
      deprecated:
        "Dismesso. Il connettore conserva cronologia ed evidenze, ma non sono possibili ulteriori transizioni o esecuzioni.",
    },
    unknownState:
      "Non è stato possibile determinare lo stato di attivazione del connettore dal record del registro.",
    activateAction: "Attivare per le anteprime",
    activating: "Attivazione in corso…",
    activateReason: "Attivato dalla console dei connettori.",
    enableLiveAction: "Abilitare la sincronizzazione live…",
    enablingLive: "Abilitazione della sincronizzazione live…",
    enableLiveReason: "Operatività live abilitata dalla console dei connettori.",
    deprecateAction: "Dismettere il connettore",
    confirmDeprecate: "Confermare la dismissione",
    deprecating: "Dismissione in corso…",
    deprecateReason: "Dismesso dalla console dei connettori.",
    deprecatedHint: "I connettori dismessi non possono essere riattivati.",
    enableLiveTitle: "Abilitazione dell'operatività live",
    enableLiveDetail:
      "L'operatività live consente alle sincronizzazioni governate di raggiungere il sistema collegato entro il perimetro approvato. Al momento dell'invio l'API verifica di nuovo ciascuno dei requisiti seguenti.",
    requirements: {
      title: "Requisiti per l'abilitazione live",
      liveSyncMode: "Il manifest dichiara una modalità di sincronizzazione live",
      liveOperationsAllowed: "La policy di runtime consente query live ed egress esterno",
      egressBoundaryNamed: "È indicato un perimetro di egress verificato",
    },
    requirementMet: "Soddisfatto",
    requirementUnmet: "Mancante",
    history: {
      title: "Cronologia delle revisioni",
      events: {
        registered: "Registrazione effettuata",
        replaced: "Manifest aggiornato",
      },
      unknownEvent: "Revisione registrata",
    },
    transitions: {
      title: "Cronologia delle transizioni",
      events: {
        active_preview: "Attivato per le anteprime",
        active_live: "Operatività live abilitata",
        deprecated: "Connettore dismesso",
      },
      unknownEvent: "Transizione registrata",
    },
    evidenceLabel: "Riferimenti alle evidenze",
    evidencePlaceholder: "approval: …, policy: …, credential: … (uno per riga)",
    evidenceDetail:
      "L'abilitazione live richiede un riferimento a un'approvazione, uno a una policy e uno a una credenziale o a un segreto.",
    evidenceMissing: (categories: string[]) =>
      `Per l'abilitazione live mancano ancora evidenze di tipo: ${categories.join(", ")}.`,
    conflict:
      "Il connettore è stato modificato mentre stava lavorando. Esamini lo stato corrente e riprovi.",
    deniedLifecycleScope:
      "Alla Sua sessione manca l'ambito del ciclo di vita dei connettori (connectors:manifest:lifecycle) per questo tenant. Può concederlo un amministratore del tenant.",
    deniedLiveScope:
      "L'abilitazione dell'operatività live richiede inoltre l'ambito enable-live (connectors:manifest:enable_live), di cui la Sua sessione non dispone per questo tenant. Può concederlo un amministratore del tenant.",
    forbidden: "La Sua sessione non dispone dell'ambito del ciclo di vita dei connettori per questo tenant.",
    validationFailed: "L'API ha rifiutato questa transizione. Completi prima i requisiti mancanti.",
    genericError: "Impossibile registrare la transizione del ciclo di vita.",
    successToast: {
      title: "Ciclo di vita aggiornato",
      detail: "La transizione è stata registrata con le evidenze di audit.",
    },
  },
  sourceDiscovery: {
    eyebrow: "Fonte",
    title: "Verifica e rilevamento",
    detail:
      "Verifichi la connettività con la fonte Postgres esterna, quindi ne elenchi le tabelle di base come evidenza di catalogo. Il rilevamento legge solo i nomi di tabelle e colonne, mai i dati delle righe.",
    ssoGate: "Acceda con SSO per verificare la fonte o eseguirne il rilevamento.",
    prerequisites: {
      title: "Prerequisiti",
      lease: "Un lease delle credenziali attivo per questo connettore",
      policy: "Una policy di egress attiva che approvi l'endpoint della fonte",
      scope: "L'ambito di rilevamento delle fonti (connectors:source:discover) per questo tenant",
    },
    prerequisiteMet: "Pronto",
    prerequisiteMissing: "Mancante",
    tableColumn: "Tabella",
    columnsColumn: "Colonne",
    driftColumn: "Variazioni rispetto al catalogo",
    profileLabel: "ID del profilo di connessione",
    schemaLabel: "Schema da rilevare",
    leaseLabel: "ID del lease delle credenziali",
    policyLabel: "ID della policy di egress",
    verifyAction: "Verificare la connessione",
    verifying: "Verifica in corso…",
    discoverAction: "Rilevare le tabelle",
    discovering: "Rilevamento in corso…",
    verifiedTitle: "Connessione verificata",
    verifiedDetail: (database: string) =>
      `Connessione in sola lettura al database «${database}» riuscita. L'hash dell'endpoint vincolato corrisponde alla policy di egress.`,
    discoveredTitle: (value: number) =>
      `${value === 1 ? "Rilevata" : "Rilevate"} ${value} ${value === 1 ? "tabella" : "tabelle"}`,
    truncatedDetail:
      "Il rilevamento si è fermato al limite previsto: esistono più tabelle o colonne di quelle elencate qui.",
    columnsTruncated: "elenco delle colonne troncato",
    drift: {
      added: "Nuova",
      changed: "Modificata",
      unchanged: "Invariata",
    },
    emptySource: {
      title: "Nessuna tabella di base trovata",
      detail:
        "Lo schema esiste ma non contiene tabelle di base. Le viste non vengono ancora rilevate.",
    },
    blocked: {
      title: "Verifica bloccata",
      source_unreachable:
        "La fonte non ha risposto entro il timeout. Verifichi che host e porta siano raggiungibili da Axis.",
      auth_denied:
        "La fonte ha rifiutato le credenziali associate al lease. Ruoti il segreto e richieda un nuovo lease.",
      permission_denied:
        "Il ruolo connesso non ha l'autorizzazione per esaminare questo schema. Conceda l'accesso in lettura allo schema e riprovi.",
      source_database_missing:
        "Il database indicato nel profilo di connessione non esiste sulla fonte.",
      schema_not_allowlisted:
        "Questo schema non è nell'elenco consentito per il rilevamento in questa installazione. Deve aggiungerlo un amministratore.",
      profile_not_configured:
        "In questa installazione non è ancora configurato alcun profilo della fonte. Imposti prima il DSN di rilevamento o il vincolo dell'endpoint.",
      runtime_egress_target_mismatch:
        "La destinazione di connessione risolta non corrisponde al perimetro di egress approvato. Nulla è stato inviato all'host errato.",
      generic:
        "Axis ha bloccato questa operazione al perimetro di runtime. Esamini le evidenze nel registro di audit.",
    },
    deniedScope:
      "Alla Sua sessione manca l'ambito di rilevamento delle fonti (connectors:source:discover) per questo tenant. Può concederlo un amministratore del tenant.",
    forbidden: "La Sua sessione non può operare sulla fonte di questo connettore per questo tenant.",
    validationFailed:
      "Uno dei record indicati non corrisponde a questo connettore. Verifichi gli ID inseriti.",
    notFound: "Un lease o una policy di egress indicati non esistono per questo tenant.",
    genericError: "Impossibile registrare l'operazione sulla fonte.",
    observationNote:
      "Ogni rilevamento completato registra le osservazioni di catalogo con le evidenze di audit; le esecuzioni successive tracciano automaticamente le tabelle aggiunte, modificate e invariate.",
  },
  sourceActivation: {
    eyebrow: "Attivazione",
    title: "Attivazione delle tabelle selezionate",
    detail:
      "Associa le tabelle rilevate selezionate come fonti governate durevoli per l'acquisizione. L'attivazione registra solo evidenze: dalla fonte non è ancora stato letto alcun dato.",
    selectColumn: "Attivare",
    selectHint: "Selezioni le tabelle rilevate da associare per l'acquisizione.",
    selectedCount: (value: number) =>
      `${value} ${value === 1 ? "tabella selezionata" : "tabelle selezionate"}`,
    reasonLabel: "Motivo dell'attivazione",
    reasonPlaceholder: "Perché vengono attivate queste tabelle?",
    action: (value: number) => `Attivare ${value} ${value === 1 ? "tabella" : "tabelle"}`,
    activating: "Attivazione in corso…",
    successTitle: (value: number) =>
      `${value === 1 ? "Attivato" : "Attivati"} ${value} binding`,
    pendingIngestionPill: "In attesa di acquisizione",
    activePill: "Attivo",
    replayedNote:
      "Un'attivazione identica precedente copriva già queste tabelle; non è stato duplicato nulla.",
    honestNote:
      "Questi binding sono pronti per l'acquisizione. Axis non ha ancora letto alcuna riga: l'acquisizione avviene attraverso un perimetro governato, una volta abilitata.",
    blocked: {
      schema_fingerprint_stale:
        "Lo schema di una tabella selezionata è cambiato dopo il rilevamento. Esegua di nuovo il rilevamento, esamini il nuovo schema e poi proceda all'attivazione.",
      binding_already_active:
        "Una delle tabelle selezionate ha già un binding attivo. Ricarichi l'elenco dei binding per visualizzarlo.",
      binding_id_in_use:
        "Un ID di binding di questo invio identifica già un'altra tabella. Riprovi per generare nuovi ID.",
      resource_not_observed:
        "Una delle tabelle selezionate non è mai stata osservata dal rilevamento. Rilevi prima lo schema.",
      selection_too_large: "Sono state selezionate troppe tabelle. Ne attivi meno alla volta.",
      duplicate_resource_name: "Ogni tabella può essere selezionata una sola volta.",
      unsafe_resource_name: "Un nome selezionato non è un nome qualificato di tabella sicuro.",
      credential_lease_not_found: "Il lease delle credenziali indicato non esiste per questo tenant.",
      egress_policy_not_found: "La policy di egress indicata non esiste per questo tenant.",
      credential_lease_not_executed:
        "Il lease indicato non è mai stato eseguito da un broker delle credenziali. Richieda ed esegua un nuovo lease.",
      generic:
        "Axis non è riuscito a registrare l'attivazione. Esamini il registro di audit e riprovi.",
    },
    reasonRequired: "Per la traccia di audit è necessario indicare il motivo dell'attivazione.",
    deniedScope:
      "Alla Sua sessione manca l'ambito di attivazione delle fonti (connectors:source:activate) per questo tenant. Può concederlo un amministratore del tenant.",
    forbidden: "La Sua sessione non può attivare fonti per questo tenant.",
    notFound: "Un lease o una policy di egress indicati non esistono per questo tenant.",
    genericError: "Impossibile registrare l'attivazione.",
  },
  sourceJourney: {
    title: "Dalla connessione ai dati convalidati",
    detail:
      "Quattro passaggi portano una tabella da una fonte verificata all'acquisizione governata. Axis registra evidenze durevoli a ogni passaggio; questa guida riporta solo quanto confermato dall'API.",
    steps: {
      verifyDiscover: {
        label: "Verifica e rilevamento",
        done: "Fonte verificata e schema osservato.",
        todo: "Verifichi la connessione e rilevi lo schema nella sezione Verifica e rilevamento qui sotto. Il rilevamento è in sola lettura: Axis registra ciò che osserva senza toccare i dati.",
        consequence:
          "Senza rilevamento non esiste un fingerprint, quindi nulla può essere attivato o acquisito.",
      },
      activate: {
        label: "Attivazione delle tabelle",
        done: "Tabelle associate pronte per l'acquisizione: {count}.",
        todo: "Attivi le tabelle rilevate che desidera governare. L'attivazione fissa il fingerprint dello schema osservato come riferimento per la convalida.",
        consequence:
          "Solo le tabelle attivate possono essere incluse in una richiesta di acquisizione governata.",
      },
      requestIngestion: {
        label: "Richiesta di acquisizione",
        done: "Richieste governate inoltrate: {count}.",
        todo: "Inoltri una richiesta di acquisizione governata per i binding in attesa. Ogni richiesta registra un motivo di governance obbligatorio.",
        consequence:
          "Le richieste vengono smistate dal worker; finché l'acquisizione resta disattivata per impostazione predefinita in questa installazione, non viene eseguito nulla.",
      },
      validate: {
        label: "Convalida ed esame delle evidenze",
        done: "{completed} completate · {failed} richiedono attenzione.",
        doneClean:
          "{completed} completate: fingerprint ricontrollati rispetto a osservazioni aggiornate.",
        todo: "Attenda che lo smistamento convalidi i fingerprint fissati, quindi apra una richiesta per esaminarne le evidenze dei lotti e lo stato di archiviazione.",
        remediation:
          "Le richieste in dead letter restano non riuscite finché non interviene: esegua di nuovo rilevamento e attivazione, quindi usi «Smistare di nuovo dopo l'intervento» all'interno della richiesta.",
        consequence:
          "La convalida non legge mai le righe; l'estrazione avviene solo se abilitata esplicitamente ed entro limiti definiti.",
      },
    },
    unavailable:
      "Il percorso richiede binding e dati delle richieste forniti dall'API. Nulla di quanto mostrato è inventato; riprovi dopo aver verificato lo stato dell'API.",
    nextActionLabel: "Prossimo passo",
    nextActions: {
      verifyDiscover: "Usi la sezione Verifica e rilevamento qui sotto.",
      activate: "Selezioni qui sotto le tabelle da attivare.",
      requestIngestion: "Inoltri qui sotto una richiesta di acquisizione governata.",
      validate: "Apra una richiesta per esaminarne le evidenze.",
    },
  },
  sourceBindings: {
    eyebrow: "Binding",
    title: "Binding delle fonti attivi",
    emptyDetail:
      "Nessuna tabella rilevata è ancora associata per l'acquisizione. Verifichi la fonte, ne rilevi le tabelle e attivi quelle necessarie.",
    tableColumn: "Tabella",
    fingerprintColumn: "Fingerprint dello schema",
    stateColumn: "Stato",
    ingestionPendingPill: "In attesa di acquisizione",
    activePill: "Attivo",
    activatedByLabel: "Attivato da",
    unavailableTitle: "Binding non disponibili",
    unavailableDetail:
      "Axis non è riuscito a caricare i binding attivi. Nulla di quanto mostrato è inventato; riprovi dopo aver verificato lo stato dell'API.",
  },
  sourceIngestion: {
    eyebrow: "Richieste di acquisizione",
    title: "Richieste di acquisizione governate",
    validationOnlyNote:
      "Solo fase di convalida. Axis ricontrolla il fingerprint dello schema di ogni tabella associata rispetto alle proprie osservazioni. Nessuna fonte viene contattata e nessuna riga viene letta o archiviata.",
    overviewTitle: "Riepilogo operativo",
    overviewUnavailable: "Riepilogo non disponibile: riprovi dopo aver verificato lo stato dell'API.",
    overviewNeedsAttention: "Richieste in dead letter che richiedono una decisione: {count}",
    overviewWorking: "In lavorazione in questo momento: {count}",
    overviewPending: "In attesa di smistamento: {count}",
    overviewQuiet: "Nessuna attività di acquisizione richiede attenzione.",
    overviewTotals:
      "Richieste complessive: {total} · estrazione: {extract} · ultima attività: {activity}",
    overviewNever: "Nessuna attività registrata.",
    attemptsLabel: "Cronologia dei tentativi di smistamento (solo metadati)",
    attemptsTruncatedNotice:
      "Sono mostrati gli ultimi 50 tentativi di smistamento registrati. I tentativi precedenti restano nelle evidenze durevoli ma non sono elencati qui.",
    attemptOutcome: {
      completed: "Completato",
      retried: "Ritentato dopo un errore operativo",
      dead_lettered: "In dead letter",
    },
    attemptSelectionValidated: "convalidata",
    attemptSelectionFailed: "non riuscita",
    emptyDetail:
      "Non esiste ancora alcuna richiesta di acquisizione governata. Richieda l'acquisizione per i binding in attesa per eseguire la convalida dello schema rispetto alle osservazioni di Axis.",
    eligibilityTitle: "Idoneità all'acquisizione",
    selectColumn: "Selezionare",
    tableColumn: "Tabella",
    fingerprintColumn: "Fingerprint",
    stateColumn: "Stato",
    requestColumn: "Richiesta",
    attemptsColumn: "Tentativi",
    stageHeader: "Fase",
    reasonHeader: "Motivo",
    lastErrorLabel: "Ultimo codice di errore",
    selectionsLabel: "Tabelle associate in questa richiesta",
    eligiblePill: "Idonea",
    blockedPill: "Bloccata",
    blockedReasons: {
      stale_fingerprint: "Fingerprint non aggiornato",
      binding_not_pending_ingestion: "Non in attesa di acquisizione",
    },
    requestIdLabel: "ID richiesta",
    reasonLabel: "Motivo di governance",
    reasonPlaceholder:
      "Perché viene inoltrata questa richiesta di acquisizione (archiviato come evidenza).",
    formHint:
      "I fingerprint dello schema vengono fissati da Axis a partire dai binding attivi; non deve mai fornirli. Inviando di nuovo lo stesso ID richiesta viene riproposta la richiesta esistente.",
    createAction: "Richiedere l'acquisizione",
    creatingAction: "Richiesta di acquisizione in corso…",
    createdStatus: {
      created: "Richiesta di acquisizione accettata e messa in coda per la convalida.",
      replayed: "Questo ID richiesta esiste già; è stata restituita la richiesta esistente senza modifiche.",
    },
    ssoGate:
      "Acceda per inoltrare richieste di acquisizione governate. L'idoneità resta comunque visibile.",
    statusPills: {
      pending: "In attesa di smistamento",
      dispatching: "In lavorazione",
      completed: "Completata",
      failed: "Non riuscita",
      cancelled: "Annullata",
    },
    stageLabels: {
      validate: "Solo convalida",
      extract: "Convalida ed estrazione",
    },
    extractionAvailableNote:
      "Qui l'estrazione è abilitata: le richieste possono eseguire una lettura limitata in sola lettura per ogni tabella associata. Le righe vengono inviate all'object store governato; Axis archivia solo conteggi, digest e watermark.",
    plannedLimitsLabel: "Limiti previsti",
    cancelAction: "Annullare la richiesta",
    redispatchAction: "Smistare di nuovo dopo l'intervento",
    redispatchingAction: "Nuovo smistamento in corso…",
    redispatchReasonLabel: "Motivo dell'intervento",
    requeuedStatus: "Richiesta rimessa in coda per lo smistamento.",
    redispatchHint:
      "Possono essere smistate di nuovo solo le richieste in dead letter. Intervenga prima (nuovo rilevamento e nuova attivazione); l'esecuzione riconvalida comunque i fingerprint.",
    cancellingAction: "Annullamento in corso…",
    cancelledStatus: "Richiesta annullata prima dello smistamento.",
    conflictMessage:
      "Axis ha rifiutato questa modifica perché la richiesta non è più in attesa.",
    batchesLabel: "Lotti di estrazione (solo metadati, nessun contenuto delle righe)",
    batchRowsLabel: "Righe",
    batchDigestLabel: "Digest",
    batchTruncatedLabel: "Troncato",
    yesPill: "Sì",
    noPill: "No",
    batchesTitle: "Evidenze dei lotti di estrazione",
    batchColumn: "Lotto",
    rowsLabel: "Righe",
    truncatedLabel: "Troncato",
    orderingLabel: "Ordinamento",
    watermarkPresent: "Watermark presente",
    noWatermark: "Nessun watermark (passaggio singolo)",
    digestLabel: "Digest",
    classificationLabel: "Classificazione",
    provenanceLabel: "Eseguito da",
    checkStorageAction: "Verificare l'archiviazione",
    checkingStorageAction: "Verifica in corso…",
    reconciliationTitle: "Archiviazione e metadati a confronto (esecuzione di prova)",
    reconLabels: {
      clean_match: "Corrispondenze esatte",
      digest_mismatch: "Digest non corrispondenti",
      missing_object: "Oggetti mancanti",
      orphaned_object: "Oggetti orfani",
    },
    reconUnsupported:
      "La riconciliazione supporta attualmente solo l'adattatore object store su file system locale.",
    preflightTitle: "Predisposizione all'estrazione",
    preflightExtractOn: "Estrazione limitata disponibile per le nuove richieste",
    preflightExtractOff:
      "Solo convalida: qui l'estrazione è disattivata per impostazione predefinita",
    preflightReasonReady: "Ogni richiesta richiede un motivo di governance",
    deadLetteredPill: "In dead letter",
    deniedScope:
      "Al Suo attore manca l'ambito connectors:source:ingest necessario per inoltrare richieste di acquisizione governate.",
    forbidden: "Axis ha rifiutato questa azione per il Suo attore.",
    conflict:
      "Questo ID richiesta identifica già un'altra richiesta di acquisizione. Scelga un nuovo ID anziché sovrascrivere evidenze durevoli.",
    validationFailed:
      "Axis ha rifiutato la richiesta: ogni binding selezionato deve esistere, essere attivo, essere in attesa di acquisizione e avere un fingerprint dello schema ancora valido.",
    notFound: "Questa richiesta di acquisizione non esiste.",
    genericError:
      "Axis non è riuscito a registrare questa richiesta di acquisizione. Nulla è stato inventato; riprovi dopo aver verificato lo stato dell'API.",
    unavailableTitle: "Richieste di acquisizione non disponibili",
    unavailableDetail:
      "Axis non è riuscito a caricare le richieste di acquisizione. Nulla di quanto mostrato è inventato; riprovi dopo aver verificato lo stato dell'API.",
  },
  requestedMissing: {
    title: "Il connettore richiesto non è in questo registro",
    detail:
      "Il connettore indicato nell'URL non è presente nel registro del tenant corrente.",
  },
  snapshot: {
    eyebrow: "Snapshot delle evidenze",
    title: "Snapshot delle evidenze richiesto",
    id: "Snapshot",
    connector: "Connettore",
    findings: "Rilievi sugli invarianti",
    reason: "Motivo",
    digest: "Digest del report",
    inspect: "Esaminare il record dello snapshot",
    missingTitle: "Lo snapshot richiesto non è disponibile",
    missingDetail:
      "Lo snapshot indicato nell'URL non è presente nei risultati di questo tenant e connettore. Potrebbe essere stato rimosso oppure il link potrebbe riferirsi a un altro tenant.",
    errorTitle: "Cronologia degli snapshot non disponibile",
    errorDetail:
      "Axis non è riuscito a verificare lo snapshot delle evidenze indicato nell'URL, pertanto la console non mostrerà un record diverso.",
  },
  metrics: {
    stripLabel: "Metriche dei connettori",
    connectors: { label: "Connettori", detail: "Fonti dati registrate" },
    runs: { label: "Esecuzioni", detail: "Fino a 100 sincronizzazioni recenti" },
    pendingProposals: {
      label: "Proposte in attesa",
      detail: "Non promosse tra le 100 proposte più recenti",
    },
    egressPolicies: {
      label: "Policy di egress",
      detail: "Fino a 100 record di policy recenti",
    },
    evidenceIssues: {
      label: "Anomalie nelle evidenze",
      detail: "Rilievi sugli ultimi 100 record per tipo di evidenza",
    },
    unavailable: "—",
  },
  tabs: {
    overview: "Panoramica",
    dataSchema: "Dati e schema",
    runs: "Esecuzioni",
    governance: "Governance ed evidenze",
  },
  overview: {
    type: "Tipo",
    version: "Versione",
    source: "Fonte",
    syncModes: "Modalità di sincronizzazione",
    boundary: "Perimetro di runtime",
    credentials: "Credenziali",
    payloadPolicy: "Policy sui contenuti",
    egressPolicy: "Perimetro di egress",
    permissions: "Autorizzazioni richieste",
    blocked: "Operazioni bloccate",
    manifest: "Manifest registrato",
    manifestMissing:
      "Nessun manifest ancora registrato: la registrazione di un manifest produce evidenze di audit.",
    manifestRegisteredBy: "Registrato da",
    manifestStatus: "Stato",
    currentRevision: "Revisione corrente",
    revisionHistory: "Cronologia delle revisioni",
    revisionHistoryDetail:
      "Elenco ordinato di tutte le versioni del manifest registrate per questo connettore.",
    revisionHistoryUnavailable: "Cronologia delle revisioni non disponibile",
    revisionHistoryUnavailableDetail:
      "Axis non è riuscito a verificare quale revisione del manifest sia in uso per questo connettore.",
    revisionColumns: {
      revision: "Revisione",
      version: "Versione del manifest",
      status: "Stato",
      registeredBy: "Registrato da",
      createdAt: "Registrato il",
    },
  },
  schema: {
    mappingTitle: "Corrispondenza dei campi",
    mappingDetail: "Come le colonne della fonte corrispondono all'ontologia condivisa.",
    columns: {
      source: "Colonna della fonte",
      target: "Campo di destinazione",
      ontology: "Destinazione nell'ontologia",
      type: "Tipo",
      required: "Obbligatorio",
    },
    requiredYes: "Obbligatorio",
    requiredNo: "Facoltativo",
    sampleTitle: "Righe di esempio",
    sampleDetail: "Campione di riferimento usato per anteprima e convalida.",
    neverSampled: "Questo connettore non è mai stato campionato.",
    sampleEmpty: "Per questo connettore non sono registrate righe di esempio.",
  },
  governance: {
    handles: {
      title: "Riferimenti alle credenziali",
      detail: "Riferimenti a segreti custoditi nel vault, mai valori in chiaro.",
      empty: "Per questo connettore non sono registrati riferimenti alle credenziali.",
      error: "Impossibile caricare i riferimenti alle credenziali.",
    },
    leases: {
      title: "Lease delle credenziali",
      detail:
        "Concessioni a tempo che consentono a un'esecuzione governata di usare un riferimento alle credenziali.",
      empty: "Per questo connettore non sono registrati lease delle credenziali.",
      error: "Impossibile caricare i lease delle credenziali.",
    },
    egress: {
      title: "Policy di egress",
      detail: "Perimetri di uscita dei dati approvati per questo connettore.",
      empty: "Per questo connettore non sono registrate policy di egress.",
      error: "Impossibile caricare le policy di egress.",
    },
    invariants: {
      title: "Invarianti sulle evidenze",
      detail: "Rilievi relativi a record governati privi di evidenze di audit.",
      allClear:
        "Tutti gli invarianti sono rispettati: ogni record governato dispone di evidenze di audit.",
      error: "Impossibile caricare i rilievi sugli invarianti.",
    },
  },
  runs: {
    title: "Esecuzioni governate",
    detail:
      "Sincronizzazioni registrate per questo connettore; ogni fase scrive evidenze di audit.",
    empty: "Per questo connettore non sono ancora registrate esecuzioni.",
    error: "Impossibile caricare le esecuzioni del connettore.",
    columns: {
      run: "Esecuzione",
      status: "Stato",
      mode: "Modalità",
      when: "Quando",
      evidence: "Evidenze",
    },
    openAudit: "Aprire l'audit",
    auditPending: "audit in attesa",
    validate: {
      action: "Convalidare",
      running: "Convalida in corso…",
      readyTitle: "Convalida superata",
      blockedTitle: "La convalida ha rilevato problemi",
      rows: "righe controllate",
      accepted: "accettate",
      rejected: "rifiutate",
      columnsChecked: "colonne controllate",
      error: "L'endpoint di anteprima non è riuscito a convalidare questo connettore.",
    },
    sync: {
      action: "Eseguire la sincronizzazione (anteprima)",
      running: "Esecuzione in corso…",
      ssoGate: "Acceda con SSO per eseguire sincronizzazioni governate.",
      leaseMissing:
        "Per eseguire la sincronizzazione di anteprima serve un lease delle credenziali attivo per questo connettore.",
      manifestMissing:
        "Per eseguire la sincronizzazione di anteprima serve un manifest registrato nello stato di anteprima attiva.",
      activateFirst:
        "Questo connettore è registrato ma non ancora attivato. Lo attivi dalla scheda Panoramica: le sincronizzazioni governate diventeranno disponibili.",
      stages: {
        create: {
          title: "Creazione del record di esecuzione",
          detail: "Registra l'esecuzione governata e le evidenze della pianificazione.",
        },
        dispatch: {
          title: "Smistamento della sincronizzazione",
          detail: "Affida l'esecuzione pianificata al dispatcher di sincronizzazione.",
        },
        execute: {
          title: "Esecuzione della sincronizzazione",
          detail: "Esegue la sincronizzazione governata entro il perimetro di anteprima.",
        },
      },
      pending: "In attesa",
      success: "Completata",
      failure: "Non riuscita",
      auditTrail: "Evidenze di audit",
    },
  },
  wizard: {
    title: "Aggiunta di un connettore",
    description:
      "Registri una fonte dati governata. La registrazione produce evidenze di audit e non avvia mai una sincronizzazione live.",
    back: "Indietro",
    next: "Avanti",
    cancel: "Annullare",
    submit: "Registrare il connettore",
    submitting: "Registrazione in corso…",
    ssoGate: "Acceda con SSO per registrare connettori.",
    typeStep: {
      title: "Che cosa desidera collegare?",
      csvTitle: "File CSV",
      csvDetail:
        "Carichi un file, ne visualizzi l'anteprima delle righe e faccia corrispondere le colonne all'ontologia.",
      dbTitle: "Database esterno",
      dbDetail:
        "Registri una fonte database in sola lettura tramite profilo di connessione: solo metadati.",
    },
    csvStep: {
      template: "Modello di corrispondenza",
      templateDetail:
        "L'anteprima convalida il file rispetto alla corrispondenza dei campi di questo connettore.",
      file: "File CSV",
      preview: "Visualizzare l'anteprima del file",
      previewing: "Anteprima in corso…",
      noTemplates:
        "Il registro dei connettori non fornisce modelli di corrispondenza CSV, quindi non è possibile visualizzare l'anteprima del file.",
      readyTitle: "Anteprima pronta",
      blockedTitle: "Anteprima bloccata",
      issuesTitle: "Problemi di convalida",
      rows: "righe",
      accepted: "accettate",
      rejected: "rifiutate",
      entitiesTitle: "Entità proposte",
      previewError: "L'endpoint di anteprima CSV non è disponibile.",
      fileReadError: "Impossibile leggere il file selezionato.",
    },
    dbStep: {
      profile: "Profilo di connessione",
      profileDetail: "Profilo denominato e preapprovato, mai una stringa di connessione in chiaro.",
      schema: "Schema",
      table: "Tabella",
      credentialHandle: "Riferimento alle credenziali",
      template: "Modello di connettore",
      preview: "Visualizzare l'anteprima dei metadati",
      previewing: "Anteprima in corso…",
      noTemplates:
        "Il registro dei connettori non fornisce modelli di connettore per database esterni.",
      readyTitle: "Anteprima dei metadati pronta",
      blockedTitle: "Anteprima dei metadati bloccata",
      columnsTitle: "Colonne mappate",
      previewError: "L'endpoint di anteprima per database esterni non è disponibile.",
    },
    reviewStep: {
      title: "Verifica e registrazione",
      connectorId: "ID connettore",
      displayName: "Nome visualizzato",
      type: "Tipo",
      records: "Record di esempio",
      conflict: "Esiste già un connettore con questo ID. Scelga un ID connettore diverso.",
      forbidden: "La Sua sessione non è autorizzata a registrare connettori per questo tenant.",
      validationFailed: "Il manifest è stato rifiutato dall'API.",
      genericError: "Impossibile registrare il manifest del connettore.",
      toastTitle: "Connettore registrato",
      toastDetail: "Il manifest è stato registrato con le evidenze di audit.",
    },
  },
  error: {
    title: "API dei connettori non disponibile",
    detail:
      "Axis non ha ricevuto record dei connettori dall'API. I record dei connettori locali di riserva sono disattivati.",
  },
  empty: {
    title: "Nessun connettore",
    detail:
      "Colleghi un file o un sistema esterno: le relative sincronizzazioni governate compariranno qui.",
    action: "Aggiungere il primo connettore",
  },
} as const;

const overview = {
  hero: {
    fallbackTitle: "Panoramica operativa",
    error: {
      title: "Impossibile caricare i dati operativi",
      detail:
        "Axis mostra solo i dati effettivamente registrati, quindi non viene visualizzato nulla finché la connessione con la piattaforma non viene ripristinata.",
    },
    facts: {
      openWorkflows: "Workflow aperti",
      pendingApprovals: "Approvazioni in attesa",
      operationRecords: "Record operativi",
      recentAudit: "Eventi di audit (più recenti)",
    },
  },
  needsAttention: {
    eyebrow: "Richiede attenzione",
    review: "Esaminare e decidere",
    openWorkflows: "Aprire i workflow",
    viewRecordedRuns: "Visualizzare le esecuzioni registrate",
    exampleWorkflow: "Workflow di esempio",
    openAudit: "Aprire l'audit",
    openApproval: "Aprire l'approvazione",
    approvalsUnavailable:
      "Impossibile caricare le approvazioni in attesa dall'API delle approvazioni.",
    overviewUnavailable:
      "Impossibile caricare i segnali di workflow e di rischio dall'API della panoramica.",
    actionRunsUnavailable:
      "Impossibile caricare dall'API delle esecuzioni le azioni approvate in attesa di un esecutore esterno.",
    stalledAction: {
      noOutcome: "Nessun esito segnalato da un esecutore esterno",
    },
    allClear: {
      title: "Nessun elemento in attesa di un Suo intervento",
      detail:
        "Al momento non ci sono approvazioni in attesa, workflow bloccati, segnali di rischio o azioni approvate in attesa di un esecutore esterno.",
    },
    error: {
      title: "Elementi da esaminare non disponibili",
      detail:
        "Axis non ha ricevuto dall'API record di approvazioni, workflow o rischi. I record locali di riserva sono disattivati.",
    },
  },
  posture: {
    agents: { label: "Agenti", link: "Gestire gli agenti" },
    workflows: {
      label: "Workflow aperti",
      link: "Visualizzare i workflow",
      detail: "Workflow persistiti non completati né annullati",
    },
    connectors: {
      label: "Attività dei connettori",
      link: "Gestire i connettori",
      detail: "Modifiche ai connettori nell'ultima finestra di audit (letture escluse)",
    },
    policies: { label: "Policy", link: "Esaminare le policy" },
    models: { label: "Modelli", link: "Visualizzare il routing" },
    unavailable: "Non disponibile",
  },
  evidenceFeed: {
    eyebrow: "Flusso delle evidenze",
    title: "Evidenze di audit recenti",
    openAudit: "Aprire l'audit",
    viewEvent: "Visualizzare l'evento",
    sparklineCaption: "Eventi di audit recenti per categoria",
    error: {
      title: "API delle evidenze di audit non disponibile",
      detail:
        "Axis non ha ricevuto eventi di audit dall'API. I record di audit locali di riserva sono disattivati.",
    },
    empty: {
      title: "Nessuna evidenza di audit",
      detail:
        "Le azioni governate scrivono evidenze in sola aggiunta, che compariranno qui.",
    },
  },
  sideRail: {
    health: "Stato del sistema",
    quickActions: "Azioni rapide",
    error: {
      title: "Stato del sistema non disponibile",
      detail:
        "Axis non ha ricevuto dall'API i record che alimentano il radar dello stato del sistema.",
    },
  },
  artifact: {
    eyebrow: "Runtime degli artefatti operativi",
    title: "Generazione di evidenze governate",
    description:
      "Ogni azione chiama l'API di Axis in tempo reale, rende persistente un artefatto limitato al tenant e scrive evidenze di audit.",
    ssoTitle: "Per generare artefatti è richiesto l'SSO dal browser",
    ssoDetail:
      "Acceda con la sessione OIDC gestita dall'API prima di creare brief giornalieri o scenari di rischio.",
    signIn: "Accedere con SSO",
    error: {
      title: "API dello snapshot operativo non disponibile",
      detail:
        "La generazione di artefatti richiede lo snapshot operativo persistito. I record operativi locali di riserva sono disattivati.",
    },
  },
} as const;

const audit = {
  integrity: {
    eyebrow: "Integrità ed esportazione",
    title: "Pacchetto di esportazione",
    download: "Scaricare il pacchetto di esportazione",
    inspect: "Esaminare le prove originali",
    ledger: {
      verified: "Registro verificato: catena di hash integra",
      unverified: "Verifica del registro non riuscita: catena di hash non confermata",
      detail:
        "Ogni evento viene sottoposto a hash e concatenato; qualsiasi manomissione interrompe la catena.",
    },
    retention: {
      enforced: "Conservazione applicata",
      notEnforced: "Conservazione non applicata per questa esportazione",
      legalHold: "Conservazione sospesa: blocco legale attivo",
      legalHoldDetail:
        "Finché il blocco legale è in vigore, i record sono esclusi dall'eliminazione.",
    },
    signature: {
      verified: "Firma del registro verificata",
      verifiedDetail: "Il manifest di esportazione e la catena di hash sono firmati.",
      notConfigured: "Firma: non configurata",
      notConfiguredDetail:
        "La prova della catena di hash è presente, ma non è configurata alcuna chiave di firma.",
    },
    error: {
      title: "API di esportazione dell'audit non disponibile",
      detail:
        "Axis non ha ricevuto dall'API un manifest di esportazione dell'audit. I manifest di esportazione locali sono disattivati.",
    },
  },
  error: {
    title: "API di audit non disponibile",
    detail:
      "Axis non ha ricevuto record di audit dall'API. I record di audit locali di riserva sono disattivati.",
  },
  noRecords: {
    title: "L'API di audit non ha restituito record",
    detail: "L'API di audit ha risposto senza record del registro per questo tenant.",
  },
  reads: {
    show: "Mostrare le letture",
    hidden: (value: number) =>
      `${value === 1 ? "Nascosto" : "Nascosti"} ${count(value)} ${value === 1 ? "evento" : "eventi"} di lettura`,
    onlyReadsTitle: "Nessun evento con modifica di stato in questa finestra",
    onlyReadsDetail:
      "In questa finestra sono stati registrati solo eventi di lettura. Attivi «Mostrare le letture» per visualizzarli.",
  },
} as const;

const models = {
  explainer:
    "Il routing di riferimento mostra la progettazione governata del routing; le invocazioni effettive sono le chiamate realmente eseguite dalla piattaforma.",
  tabs: {
    reference: "Routing di riferimento",
    live: "Invocazioni effettive",
  },
  reference: {
    error: {
      title: "API del routing non disponibile",
      detail:
        "Axis non ha ricevuto dall'API i record del routing dei modelli. I record di routing locali di riserva sono disattivati.",
    },
    noRecords: {
      title: "Nessuna route dei modelli",
      detail:
        "Le route governate dei modelli compariranno qui dopo essere state configurate per questo tenant.",
    },
    noMatch: {
      title: "Nessuna route corrisponde ai filtri correnti",
      detail:
        "Modifichi o reimposti i filtri per dominio, provider e decisione per visualizzare la telemetria del routing.",
      reset: "Reimpostare i filtri",
    },
    routeDetail: {
      provider: "Provider",
      model: "Modello",
      estimatedCost: "Costo stimato",
      latency: "Latenza",
      latencyValue: (milliseconds: string) => `${milliseconds} ms`,
      totalTokens: (tokens: string) => `${tokens} token`,
      policy: "Policy",
      egressRequested: (requested: boolean) =>
        `Egress esterno richiesto: ${requested ? "sì" : "no"}`,
      egressAllowed: (allowed: boolean) =>
        `Egress esterno consentito: ${allowed ? "sì" : "no"}`,
      boundary: (boundary: string) => `Perimetro: ${boundary}`,
      requiredPermissions: "Autorizzazioni richieste",
      observabilityEvents: "Eventi di osservabilità",
      evidence: "Evidenze",
      audit: "Audit",
      tokenSplit: (input: string, output: string) => `Input ${input} / output ${output}`,
    },
  },
  live: {
    invocationsError: {
      title: "API delle invocazioni dei modelli non disponibile",
      detail:
        "Axis non ha ricevuto i record persistiti delle invocazioni dei modelli. Le righe delle invocazioni non vengono mai inventate.",
    },
    endpointsError: {
      title: "API degli endpoint dei modelli non disponibile",
      detail:
        "Axis non ha ricevuto il registro degli endpoint dei modelli. Le schede degli endpoint non vengono mai inventate.",
    },
  },
} as const;

const policyDetail = {
  tabs: {
    conditions: "Condizioni",
    revisions: "Revisioni",
    evaluate: "Valutazione",
  },
  authorAccess: {
    summary: "Per creare policy è necessario l'accesso da autore di policy.",
    detail: "La creazione genera la revisione 1 e registra evidenze di audit.",
    ssoGate: "Acceda con SSO per creare policy di piattaforma.",
  },
  reviseAccess: {
    summary: "Per aggiungere revisioni è necessario l'accesso da autore di policy.",
    detail:
      "Le revisioni sono in sola aggiunta e possono essere ritentate in sicurezza; l'ambito della policy è fissato al momento della creazione.",
    ssoGate: "Acceda con SSO per aggiungere revisioni alle policy.",
  },
  error: {
    title: "API delle policy non disponibile",
    registryDetail:
      "Axis non ha ricevuto dall'API i record delle policy di piattaforma. I record di policy locali di riserva sono disattivati.",
    detailDetail:
      "Axis non ha ricevuto dall'API una policy di piattaforma. I record di policy locali di riserva sono disattivati.",
  },
} as const;

const simulation = {
  run: {
    eyebrow: "Replay",
    title: "Confronto degli esiti delle policy sulla cronologia registrata",
    description:
      "Rielabori le decisioni registrate con un insieme di policy e verifichi cosa cambierebbe. Durante un replay nulla cambia in produzione.",
    fields: {
      workflow: "ID workflow (facoltativo)",
      workflowPlaceholder: "Tutti i workflow registrati",
      limit: "Finestra della cronologia (eventi)",
      retentionDays: "Finestra di conservazione (giorni)",
      legalHold: "Applicare il blocco legale",
      baselineSet: "Insieme di policy di riferimento (facoltativo)",
      candidateSet: "Insieme di policy candidato (facoltativo)",
      connector: "ID connettore (facoltativo)",
      comparisonHint:
        "Lasci vuoti i campi degli insiemi di policy per eseguire il replay sulla cronologia delle policy registrata.",
    },
    submit: "Eseguire il replay",
    running: "Replay in corso…",
    error: {
      title: "Replay non riuscito",
      detail:
        "L'API di replay ha rifiutato questa esecuzione. Modifichi i parametri e riprovi.",
    },
    result: {
      eyebrow: "Risultato del replay",
      baseline: "Riferimento",
      simulated: "Simulato",
      changed: "Modificato",
      unchanged: "Invariato",
      decisionsTitle: "Confronto delle decisioni",
      policySetTitle: "Confronto degli insiemi di policy",
      inspect: "Esaminare il risultato originale",
      empty: {
        title: "Nessuna decisione da confrontare",
        detail:
          "La finestra di replay non ha restituito decisioni di policy. Ampli la finestra della cronologia o cancelli il filtro sul workflow.",
      },
    },
  },
  error: {
    title: "API di replay non disponibile",
    detail:
      "Axis non ha ricevuto artefatti di replay dall'API. I record di replay locali di riserva sono disattivati.",
  },
  noArtifacts: {
    title: "Nessuna cronologia di replay",
    detail:
      "I replay vengono costruiti dalla cronologia dei workflow governati. Le anteprime compariranno qui quando questo tenant avrà registrato esecuzioni di workflow.",
    action: "Aprire le esecuzioni dei workflow",
  },
  noPolicyResult: "Per questo replay non è registrato alcun risultato di policy.",
} as const;

const onboarding = {
  eyebrow: "Configurazione guidata",
  title: "Configurazione della piattaforma governata",
  description:
    "Cinque passaggi portano da un tenant vuoto a un workflow governato con evidenze di audit registrate.",
  progressLabel: "Avanzamento della configurazione",
  stepsComplete: "passaggi di configurazione completati",
  exploreDemo: {
    label: "Esplorare con dati dimostrativi",
    comingSoon: "Disponibile con il provisioning dimostrativo",
    pending: "Caricamento dei dati dimostrativi…",
    toastTitle: "Dati dimostrativi caricati",
    errorFallback:
      "Axis non è riuscito a caricare lo scenario dimostrativo. La richiesta all'API di bootstrap non è riuscita.",
  },
  compact: {
    show: "Mostrare i passaggi di configurazione",
    hide: "Nascondere i passaggi di configurazione",
  },
  stepDone: "Completato",
  steps: {
    connectors: {
      title: "Collegare un sistema",
      why: "Registri un file o una fonte esterna e lo attivi, così da poter eseguire sincronizzazioni governate.",
      cta: "Aprire i connettori",
    },
    ontology: {
      title: "Importare le entità dell'ontologia",
      why: "Fornisca ad agenti e policy un vocabolario condiviso per i Suoi oggetti di business.",
      cta: "Aprire l'ontologia",
    },
    policies: {
      title: "Definire una policy",
      why: "Stabilisca le regole che determinano cosa possono fare gli agenti e quando interviene una persona.",
      cta: "Aprire le policy",
    },
    agents: {
      title: "Registrare un agente",
      why: "Registri un agente con un livello di autonomia esplicito e un perimetro di autorizzazioni.",
      cta: "Aprire gli agenti",
    },
    workflows: {
      title: "Eseguire un workflow governato",
      why: "Osservi un workflow dall'inizio alla fine, con evidenze registrate a ogni passaggio.",
      cta: "Aprire i workflow",
    },
  },
} as const;

const settingsPanelUnavailable = "I record di impostazione locali di riserva sono disattivati.";

const settings = {
  source: {
    live: "Stato del sistema in tempo reale",
    loading: "Caricamento dello stato del sistema",
    stale: "Stato del sistema non aggiornato",
    required: "API necessaria",
  },
  stale:
    "Aggiornamento non riuscito. Viene mostrato l'ultimo stato del sistema convalidato per questo pannello.",
  tabs: {
    readiness: "Predisposizione",
    identity: "Identità",
    deployment: "Installazione",
    support: "Assistenza",
  },
  inspect: "Esaminare il report originale",
  ready: {
    eyebrow: "Dipendenze di runtime",
    title: "Perimetro dell'API di Axis",
    dependencyReachable: "raggiungibile",
    dependencyNotConfigured: "non configurato",
    egressTitle: "Egress verso modelli esterni",
    egressDetail:
      "Riportato in tempo reale dall'API della piattaforma; l'egress resta bloccato finché una policy non lo consente.",
    error: {
      title: "API di predisposizione non disponibile",
      detail: `Axis non ha ricevuto il report di predisposizione dell'API. ${settingsPanelUnavailable}`,
    },
  },
  gates: {
    eyebrow: "Predisposizione dell'installazione",
    title: "Requisiti per la produzione",
    demoSafe: "Sicuro per demo",
    productionReady: "Pronto per la produzione",
    blockersTitle: "Elementi bloccanti per la produzione",
    noBlockers: "Tutti i requisiti per la produzione sono soddisfatti.",
  },
  oidc: {
    eyebrow: "Identità e SSO",
    title: "Predisposizione OIDC",
    issuer: "Emittente",
    audience: "Audience",
    authRequired: "Autenticazione obbligatoria",
    actorClaim: "Claim dell'attore",
    error: {
      title: "API di predisposizione delle identità non disponibile",
      detail: `Axis non ha ricevuto il report di predisposizione OIDC. ${settingsPanelUnavailable}`,
    },
  },
  session: {
    eyebrow: "Sessione del browser",
    title: "La Sua sessione",
    actor: "Attore",
    tenant: "Tenant",
    mode: "Modalità",
    authenticated: "Autenticata",
    publicActor: "Valutazione pubblica",
    manageSessions: "Gestire le sessioni del browser",
    error: {
      title: "API delle sessioni non disponibile",
      detail: `Axis non ha ricevuto il modello di lettura della sessione di identità. ${settingsPanelUnavailable}`,
    },
  },
  deployment: {
    eyebrow: "Configurazione dell'installazione",
    environment: "Ambiente",
    demoSafe: "Sicuro per demo",
    productionReady: "Pronto per la produzione",
    objectStore: "Object store",
    wormRetention: "Conservazione WORM",
    retentionMode: "Modalità di conservazione",
    retentionDays: "Giorni di conservazione",
    error: {
      title: "API di predisposizione dell'installazione non disponibile",
      detail: `Axis non ha ricevuto il report di predisposizione dell'installazione. ${settingsPanelUnavailable}`,
    },
  },
  support: {
    eyebrow: "Diagnostica di assistenza",
    title: "Pacchetto di assistenza condivisibile",
    safeToShare: "Condivisibile in sicurezza",
    demoSupport: "Assistenza demo",
    productionSupport: "Assistenza in produzione",
    objectRetention: "Conservazione degli oggetti",
    retentionActionRequired: "Intervento necessario",
    error: {
      title: "API di diagnostica di assistenza non disponibile",
      detail: `Axis non ha ricevuto il report di diagnostica di assistenza. ${settingsPanelUnavailable}`,
    },
  },
  guidance: {
    auth_required:
      "Attivi la verifica OIDC obbligatoria per l'API prima di andare oltre le demo locali.",
    https_issuer:
      "Prima della produzione utilizzi un URL emittente HTTPS fornito dall'IdP aziendale.",
    explicit_jwks_url:
      "Configuri esplicitamente l'URL JWKS fornito dall'IdP anziché ricavarlo dall'emittente.",
    asymmetric_algorithms:
      "Consenta per la verifica dei token solo algoritmi di firma asimmetrici (ad esempio RS256).",
    openid_scope:
      "Aggiunga l'ambito openid alla configurazione del client OIDC, così da poter emettere ID token.",
    tenant_claim:
      "Imposti il claim del token che indica il tenant, così che le sessioni siano associate al tenant corretto.",
    actor_claim: "Imposti il claim del token che identifica l'utente che agisce.",
    authorization_code_client:
      "Registri presso l'IdP un client SSO per il browser e ne configuri il client ID.",
    authorization_endpoint:
      "Configuri l'endpoint di autorizzazione con un URL HTTPS fornito dall'IdP.",
    token_endpoint: "Configuri l'endpoint del token con un URL HTTPS fornito dall'IdP.",
    end_session_endpoint:
      "Configuri un endpoint HTTPS di fine sessione, così che l'uscita chiuda anche la sessione presso l'IdP.",
    post_logout_redirect:
      "Imposti un reindirizzamento HTTPS dopo l'uscita, così che gli utenti tornino alla console.",
    session_cookie_signing:
      "Fornisca un segreto di firma gestito dall'operatore per i cookie di sessione del browser.",
    secure_session_cookie:
      "Attivi l'attributo Secure, così che i cookie di sessione viaggino solo su HTTPS.",
    host_prefixed_session_cookie:
      "Attivi i cookie Secure con prefisso __Host-, così che le sessioni siano legate a questo host.",
    refresh_credential_encryption:
      "Fornisca una chiave di cifratura delle credenziali di aggiornamento di almeno 32 caratteri.",
    session_idle_timeout:
      "Imposti un timeout di inattività maggiore di zero, così che le sessioni non presidiate scadano.",
    session_absolute_timeout:
      "Imposti una durata massima della sessione maggiore di zero, così che le sessioni scadano sempre.",
    registered_tenant_admission:
      "Imposti l'ammissione dei tenant su «solo registrati», così che l'accesso richieda un tenant registrato nella sezione Tenant.",
    oidc_enterprise_sso:
      "Risolva i controlli della scheda Identità per rendere l'SSO pronto per l'uso aziendale.",
    oidc_secure_cookie_session:
      "Eroghi API e console su HTTPS con cookie di sessione Secure, firmati e a durata limitata.",
    external_model_egress_disabled:
      "Mantenga disattivato l'egress verso modelli esterni, oppure lo governi con policy del tenant e controlli di audit.",
    api_rate_limiting:
      "Attivi la limitazione della frequenza delle richieste API prima di esporre la piattaforma al traffico di produzione.",
    network_egress_restricted:
      "Limiti il traffico di rete in uscita con una network policy e un elenco consentito esplicito.",
    deployment_tenancy_profile:
      "Dichiari la modalità di tenancy e le evidenze su isolamento, residenza dei dati e accesso degli operatori.",
    live_connector_execution_disabled:
      "Mantenga disattivata l'esecuzione live dei connettori finché non sono disponibili le policy dei provider e i runbook.",
    ontology_graph_mutation_posture:
      "Configuri un indirizzo TypeDB e attivi le letture dell'ontologia prima di promuovere i nodi del grafo.",
    audit_ledger_signing_configured:
      "Configuri una chiave di firma del registro di audit, così che le esportazioni delle evidenze siano firmate.",
    production_object_store_adapter:
      "Configuri un object storage compatibile S3 con credenziali, TLS e conservazione WORM.",
    observability_instrumentation:
      "Attivi OpenTelemetry e indirizzi l'exporter verso il Suo collector per emettere le tracce.",
    production_dr_procedures:
      "Documenti i runbook di backup e disaster recovery con obiettivi RPO/RTO ed evidenze delle prove effettuate.",
    demo_support_ready:
      "Risolva i problemi di configurazione dell'installazione, così che una dimostrazione possa essere eseguita in sicurezza.",
    production_support_model:
      "Definisca un modello di assistenza 24x7 con tempi di risposta, percorsi di escalation e una pagina di stato.",
    production_support_commitments:
      "Predisponga impegni di assistenza sottoscritti, un modello di presidio e i termini contrattuali dello SLA.",
    support_slo_targets:
      "Imposti i tempi di risposta S1-S4 in ordine dal più breve al più lungo.",
    support_escalation_channels:
      "Configuri almeno due classi di canali di escalation per l'assistenza in produzione.",
  },
  guidanceFallback:
    "Esamini il dettaglio tecnico riportato di seguito e aggiorni la configurazione della piattaforma.",
  checkLabels: {
    auth_required: "Accesso all'API obbligatorio",
    https_issuer: "Emittente di identità HTTPS",
    explicit_jwks_url: "URL esplicito delle chiavi di firma (JWKS)",
    asymmetric_algorithms: "Firma asimmetrica dei token",
    openid_scope: "Ambito OpenID",
    tenant_claim: "Claim del tenant",
    actor_claim: "Claim dell'attore",
    authorization_code_client: "Client SSO per il browser",
    authorization_endpoint: "Endpoint di autorizzazione",
    token_endpoint: "Endpoint del token",
    end_session_endpoint: "Endpoint di uscita",
    post_logout_redirect: "Reindirizzamento dopo l'uscita",
    session_cookie_signing: "Segreto di firma del cookie di sessione",
    secure_session_cookie: "Cookie di sessione sicuri",
    host_prefixed_session_cookie: "Cookie di sessione legati all'host",
    refresh_credential_encryption: "Cifratura delle credenziali di aggiornamento",
    session_idle_timeout: "Timeout di inattività della sessione",
    session_absolute_timeout: "Durata massima della sessione",
    oidc_enterprise_sso: "Single sign-on aziendale",
    oidc_secure_cookie_session: "Sessioni del browser sicure",
    registered_tenant_admission: "Ammissione dei soli tenant registrati",
    external_model_egress_disabled: "Egress verso modelli esterni",
    api_rate_limiting: "Limitazione della frequenza API",
    network_egress_restricted: "Restrizioni sul traffico di rete in uscita",
    deployment_tenancy_profile: "Profilo di tenancy e isolamento",
    live_connector_execution_disabled: "Esecuzione live dei connettori",
    ontology_graph_mutation_posture: "Promozione nel grafo dell'ontologia",
    audit_ledger_signing_configured: "Firma del registro di audit",
    production_object_store_adapter: "Object storage delle evidenze",
    observability_instrumentation: "Tracce e metriche",
    production_dr_procedures: "Runbook di disaster recovery",
    support_diagnostics_public_safe: "Diagnostica condivisibile",
    support_runbook_baseline: "Runbook di assistenza di base",
    demo_support_ready: "Predisposizione dell'assistenza demo",
    deployment_readiness_attached: "Report dell'installazione allegato",
    production_support_model: "Modello di assistenza in produzione",
    production_support_commitments: "Impegni di assistenza",
    support_slo_targets: "Tempi di risposta dell'assistenza",
    support_escalation_channels: "Canali di escalation",
  },
  checkActions: {
    identityTab: "Aprire i controlli di identità",
    deploymentTab: "Aprire la configurazione dell'installazione",
    tenants: "Aprire i tenant",
    modelRouting: "Aprire il routing dei modelli",
    connectors: "Aprire i connettori",
    ontology: "Aprire l'ontologia",
    audit: "Aprire l'audit",
  },
  gatesSummary: (value: number) =>
    value === 1
      ? "1 requisito richiede un intervento prima della produzione."
      : `${value} requisiti richiedono un intervento prima della produzione.`,
} as const;

const ontology = {
  legend: {
    label: "Legenda del grafo dell'ontologia",
    entity: "Entità",
    selected: "Selezionata",
    relation: "Relazione",
    hint: "Faccia clic su un nodo o prema Invio per aprirne il dettaglio",
  },
  graph: {
    controlsLabel: "Controlli del grafo dell'ontologia",
    zoomIn: "Ingrandire",
    zoomOut: "Ridurre",
    resetView: "Ripristinare la vista",
  },
  sheet: {
    eyebrow: "Entità dell'ontologia",
    openFullPage: "Aprire a pagina intera",
    error: {
      title: "API delle entità non disponibile",
      detail:
        "Axis non ha ricevuto un'entità dell'ontologia dall'API. I record delle entità locali di riserva sono disattivati.",
    },
    notFound: {
      title: "Entità non trovata",
      detail:
        "Non esiste alcuna entità dell'ontologia con questo ID. Potrebbe essere stata rinominata o rimossa dal grafo.",
    },
  },
} as const;

const demoBadge = {
  label: "Demo",
  tooltip: "Questo tenant esegue lo scenario dimostrativo di produzione manifatturiera",
} as const;

const tenantLifecycle = {
  suspend: {
    title: "Sospensione del tenant",
    action: "Sospendere il tenant",
    saving: "Sospensione in corso",
    impactTitle: "Effetti della sospensione",
    impact:
      "Ogni accesso e ogni richiesta API effettuati per questo tenant vengono rifiutati fino alla riattivazione, quindi operatori, agenti e integrazioni restano esclusi. Le sessioni del browser residue vengono revocate dalla successiva riconciliazione. I dati del tenant e le evidenze di audit vengono conservati.",
  },
} as const;

const tenantVocabulary = {
  eyebrow: "Vocabolario del tenant",
  title: "Terminologia della console",
  description:
    "Scelga i termini che questo tenant vede per sedi, area di lavoro e domini operativi.",
  requiredScope: (scope: string) => `Il salvataggio richiede l'ambito ${scope}.`,
  endpoint: "Endpoint dell'API del vocabolario",
  source: {
    loading: "Caricamento del vocabolario del tenant",
    api: "API del vocabolario",
    missing: "Tenant non trovato",
    unavailable: "API del vocabolario non disponibile",
  },
  mode: {
    defaults: "Valori predefiniti in uso",
    defaultsDetail:
      "Questo tenant non ha ancora configurato il vocabolario. Il salvataggio crea una terminologia specifica per il tenant.",
    configured: "Configurato dal tenant",
    configuredDetail:
      "Questi valori sostituiscono, per questo tenant, i valori predefiniti indipendenti dal settore.",
  },
  fields: {
    siteSingular: "Sede (singolare)",
    siteSingularDetail: "Il termine singolare usato per una sede operativa.",
    sitePlural: "Sedi (plurale)",
    sitePluralDetail: "Il termine plurale usato per le sedi operative.",
    workspaceLabel: "Nome dell'area di lavoro",
    workspaceLabelDetail: "Il nome specifico del tenant per la propria area di lavoro operativa.",
    domainLabels: "Etichette dei domini",
    domainLabelsDetail:
      "Associ a ogni chiave di dominio memorizzata nei record operativi l'etichetta che gli operatori devono vedere.",
    domainKey: "Chiave di dominio",
    domainKeyPlaceholder: "supply",
    domainLabel: "Etichetta visualizzata",
    domainLabelPlaceholder: "Forniture farmaceutiche",
  },
  actions: {
    addDomain: "Aggiungere un'etichetta di dominio",
    removeDomain: "Rimuovere l'etichetta di dominio",
    review: "Esaminare l'aggiornamento del vocabolario",
    saving: "Salvataggio in corso",
    confirm: "Confermare l'aggiornamento del vocabolario",
    cancel: "Annullare",
  },
  validation: {
    fix: "Corregga i campi evidenziati; non è stato inviato nulla.",
    labelTooLong: (limit: number) => `Il valore può contenere al massimo ${limit} caratteri.`,
    domainLimit: (limit: number) => `Questa API accetta al massimo ${limit} etichette di dominio.`,
    missingDomainKey: "Inserisca una chiave di dominio o rimuova questa riga.",
    duplicateDomainKey: "Ogni chiave di dominio può comparire una sola volta.",
  },
  confirmation:
    "Confermi questo aggiornamento del vocabolario del tenant. I record operativi esistenti mantengono le chiavi di dominio memorizzate.",
  errors: {
    prefix: "Aggiornamento del vocabolario non riuscito:",
    unavailable: "L'API del vocabolario del tenant non è disponibile.",
    generic: "Aggiornamento del vocabolario non riuscito.",
    requiredPermission: (message: string, permission: string) =>
      `${message} Autorizzazione richiesta: ${permission}.`,
  },
  success: "Aggiornamento del vocabolario applicato.",
} as const;

/* Component copy moved out of JSX (#945); mirrors `ui` in lib/strings.ts. */
const ui = {
  actionRegistry: {
    theActionRegistryIsNot:
      "Il registro delle azioni non viene caricato finché l'attore e il tenant correnti non sono verificati.",
    axisDidNotReceiveApi:
      "Axis non ha ricevuto record delle azioni dall'API. I record delle azioni locali di riserva sono disattivati.",
    actionApiUnavailable: "API delle azioni non disponibile",
    governedActionsWillAppearHere:
      "Le azioni governate compariranno qui dopo essere state registrate per questo tenant.",
    noActionsRegisteredYet: "Nessuna azione registrata",
    theActionApiRespondedWithout:
      "L'API delle azioni ha risposto senza record del registro per questo tenant.",
    actionApiReturnedNoRecords: "L'API delle azioni non ha restituito record",
    actionSourceAndRegistryStatus: "Fonte delle azioni e stato del registro",
    actionRegistry: "Registro delle azioni",
    risk: "Rischio",
    allRisks: "Tutti i livelli di rischio",
    approval: "Approvazione",
    allModes: "Tutte le modalità",
    resetActionFilters: "Reimpostare i filtri delle azioni",
    actions: "Azioni",
    adjustOrResetTheDomain:
      "Modifichi o reimposti i filtri per dominio, rischio, approvazione e stato per visualizzare le azioni registrate.",
    noActionsMatchTheCurrent: "Nessuna azione corrisponde ai filtri correnti",
    actionId: "ID azione",
    runtime: "Runtime",
    autonomy: "Autonomia",
    connectedAgents: "Agenti collegati",
    workflowBindings: "Collegamenti ai workflow",
    approvalRefs: "Riferimenti alle approvazioni",
    inputSchema: "Schema di input",
    outputSchema: "Schema di output",
    sideEffects: "Effetti collaterali",
    guardrails: "Limiti di sicurezza",
    validationChecks: "Controlli di convalida",
    blockedConditions: "Condizioni di blocco",
    apiDryRunPayload: "Payload dell'esecuzione di prova via API",
    signInWithSsoTo: "Acceda con SSO per richiedere esecuzioni di azioni governate.",
    requesting: "Richiesta in corso",
    requestDryRun: "Richiedere un'esecuzione di prova",
    sampleInput: "Input di esempio",
    sampleOutput: "Output di esempio",
    actionRunResult: "Risultato dell'esecuzione dell'azione",
    persistedActionRun: "Esecuzione dell'azione persistita",
    runId: "ID esecuzione",
    idempotency: "Idempotenza",
    workflowSignal: "Segnale del workflow",
    actionRunPersistenceError: "Errore di persistenza dell'esecuzione dell'azione",
    actionRunPersistenceUnavailable: "Persistenza dell'esecuzione dell'azione non disponibile",
  },
  agentRegistry: {
    theAgentRegistryIsNot:
      "Il registro degli agenti non viene caricato finché l'attore e il tenant correnti non sono verificati.",
    theAuthenticatedIdentityResponseDoes:
      "La risposta dell'identità autenticata non contiene un tenant. Axis non ripiegherà su record di agenti dimostrativi.",
    loadingAgentApi: "Caricamento dell'API degli agenti",
    agentSourceAndRegistryStatus: "Fonte degli agenti e stato del registro",
  },
  agentsAgentRuns: {
    agentRunStepTimeline: "Cronologia dei passaggi dell'esecuzione dell'agente",
    loadingAgentRunSteps: "Caricamento dei passaggi dell'esecuzione",
    loadingAgentRuns: "Caricamento delle esecuzioni degli agenti",
  },
  apiStatusPanel: {
    apiStatus: "Stato dell'API",
    controlApi: "API di controllo",
  },
  appShell: {
    pendingApprovals: (count: number) =>
      `${count} ${count === 1 ? "approvazione in attesa" : "approvazioni in attesa"}`,
    axisSections: "Sezioni di Axis",
    skipToMainContent: "Passare al contenuto principale",
  },
  approvalInbox: {
    decisionStageRail: "Fasi della decisione",
    decisionHistory: "Cronologia delle decisioni",
    risks: "Rischi",
    alternatives: "Alternative",
    decisionTrail: "Traccia della decisione",
    requestedBy: "Richiesta da",
    costExposure: "Esposizione ai costi",
    theApprovalQueueIsNot:
      "La coda di approvazione non viene caricata finché l'attore e il tenant correnti non sono verificati.",
    loadingApprovalApi: "Caricamento dell'API delle approvazioni",
    approvalSourceAndStatus: "Fonte e stato delle approvazioni",
    approvalMetrics: "Metriche delle approvazioni",
    ready: "Pronte:",
    needsWatching: "Da monitorare:",
    actionRequired: "Intervento necessario:",
    thisLinkedApprovalIsOutside:
      "Questa approvazione collegata non rientra nei filtri correnti della coda.",
    clearQueueFilters: "Cancellare i filtri della coda",
    policyNotes: "Note sulla policy",
  },
  approvalsApprovalDecisionCard: {
    decisionPersistenceError: "Errore di persistenza della decisione",
  },
  approvalsApprovalQueue: {
    highRisk: "Rischio elevato",
    mediumRisk: "Rischio medio",
    lowRisk: "Rischio basso",
  },
  auditActivityHeatmap: {
    activityByTime: "Attività per fascia oraria",
    utc6HourBins: "UTC · fasce di 6 ore",
    auditEventsByUtcDate: "Eventi di audit per data UTC e fascia di sei ore",
    clearTimeFilter: "Cancellare il filtro temporale",
  },
  auditExplorer: {
    theConsoleCouldNotVerify:
      "La console non è riuscita a verificare l'attore e il tenant correnti. I dati di audit non vengono caricati finché l'identità non è disponibile.",
    governedActionsAndDecisionsWill:
      "Le azioni e le decisioni governate compariranno qui come evidenze in sola aggiunta.",
    noAuditEvidenceYet: "Nessuna evidenza di audit",
    noAuditEventsMatchThe: "Nessun evento di audit corrisponde ai filtri selezionati.",
    noMatchingAuditEvidence: "Nessuna evidenza di audit corrispondente",
    auditSourceAndLedgerStatus: "Fonte dell'audit e stato del registro",
    events: "Eventi",
    eventsInTheReturnedWindow: "Eventi nella finestra restituita",
    eventsMarkedForAttention: "Eventi segnalati per attenzione",
    auditExplorer: "Esplorazione dell'audit",
    allTenants: "Tutti i tenant",
    allEvents: "Tutti gli eventi",
    visibleAuditEvents: "Eventi di audit visibili",
    noReturnedEventsInThis:
      "Nessun evento restituito in questo intervallo corrisponde ai filtri correnti per tenant, evento e ambito. Selezioni un'altra cella o cancelli il filtro temporale.",
    noEventsInThisTime: "Nessun evento in questo intervallo di tempo",
    selectedAuditEvent: "Evento di audit selezionato",
    occurred: "Avvenuto",
    related: "Correlati",
    redactedFields: "Campi oscurati",
    connectorSnapshot: "Snapshot del connettore",
    retentionNotes: "Note sulla conservazione",
  },
  common: {
    theAuthenticatedIdentityResponseDoes:
      "La risposta dell'identità autenticata non contiene un tenant.",
    authenticatedTenantMissing: "Tenant autenticato mancante",
    filters: "Filtri",
    domain: "Dominio",
    allDomains: "Tutti i domini",
    status: "Stato",
    allStatuses: "Tutti gli stati",
    owner: "Responsabile",
    policy: "Policy",
    requiredPermissions: "Autorizzazioni richieste",
    payloadPreview: "Anteprima del payload",
    audit: "Audit",
    permission: "Autorizzazione",
    registryNotes: "Note sul registro",
    workflow: "Workflow",
    decision: "Decisione",
    tenant: "Tenant",
    event: "Evento",
    scope: "Ambito",
    allScopes: "Tutti gli ambiti",
    resetFilters: "Reimpostare i filtri",
    auditEvent: "Evento di audit",
    actor: "Attore",
    source: "Fonte",
    evidence: "Evidenze",
    node: "Nodo",
    type: "Tipo",
    none: "Nessuno",
    yes: "Sì",
    refreshState: "Aggiornare lo stato",
    provider: "Provider",
    model: "Modello",
    endpoint: "Endpoint",
    openAudit: "Aprire l'audit",
    reset: "Reimpostare",
    actionDomains: "Domini di azione",
    amountThreshold: "Soglia di importo",
    optional: "Facoltativo",
    policyVersion: "Versione della policy",
    effect: "Effetto",
    displayName: "Nome visualizzato",
    description: "Descrizione",
    notesOnePerLine: "Note (una per riga)",
    optionalReviewerNotes: "Note facoltative per il revisore",
    revision: "Revisione",
    conditions: "Condizioni",
    theConsoleCouldNotVerify:
      "La console non è riuscita a verificare l'attore e il tenant correnti. I dati delle policy non vengono caricati finché l'identità non è disponibile.",
    policies: "Policy",
    evaluationPrecedence: "Precedenza di valutazione",
    dismiss: "Ignorare",
    updated: "Aggiornato",
    registry: "Registro",
    emptyRegistry: "Registro vuoto",
    sessionApiUnavailable: "API delle sessioni non disponibile",
    unknown: "Sconosciuto",
    tenantApiUnavailable: "API dei tenant non disponibile",
    tenants: "Tenant",
    saving: "Salvataggio in corso",
    close: "Chiudere",
  },
  connectorConsole: {
    loadingConnectorIdentity: "Caricamento dell'identità per i connettori",
    theConnectorConsoleIsDisabled:
      "La console dei connettori è disattivata perché non è stato possibile verificare il tenant corrente.",
    tenantIdentityUnavailable: "Identità del tenant non disponibile",
    loadingConnectorApi: "Caricamento dell'API dei connettori",
    connectorSourceAndStatus: "Fonte e stato dei connettori",
    connectorDetailUnavailable: "Dettaglio del connettore non disponibile",
    refreshToLoadTheSelected: "Aggiorni la pagina per caricare di nuovo il connettore selezionato.",
    selectAConnector: "Selezioni un connettore",
    chooseAConnectorFromThe: "Scelga un connettore dall'elenco.",
  },
  connectorConsoleAddConnectorWizard: {
    loadingConnectorTemplates: "Caricamento dei modelli di connettore…",
    connectorTemplatesUnavailableCloseAnd:
      "Modelli di connettore non disponibili. Chiuda e riapra per riprovare.",
    ontologyTarget: "Destinazione nell'ontologia",
    column: "Colonna",
    target: "Destinazione",
  },
  connectorConsoleGovernance: {
    liveRefreshFailedShowingThe:
      "Aggiornamento non riuscito. Vengono mostrati gli ultimi dati convalidati.",
    reference: "Riferimento",
    rotation: "Rotazione",
    lease: "Lease",
    window: "Finestra",
    boundary: "Perimetro",
    profile: "Profilo",
  },
  connectorConsoleList: {
    connectorPages: "Pagine dei connettori",
    previousConnectors: "Connettori precedenti",
    previous: "Precedente",
    nextConnectors: "Connettori successivi",
    next: "Successiva",
  },
  connectorConsoleRuns: {
    liveRefreshFailedShowingThe:
      "Aggiornamento non riuscito. Vengono mostrati gli ultimi dati di esecuzione convalidati.",
  },
  connectorConsoleSourceIngestionPanel: {
    off: "Disattivata",
  },
  connectorConsoleSourceJourney: {
    completedStep: "Passaggio completato: ",
    notDoneYet: "Non ancora completato: ",
    needsAttention: "Richiede attenzione",
    done: "Completato",
    toDo: "Da fare",
  },
  consoleCommandMenu: {
    currentApiStatus: "Stato corrente dell'API",
  },
  consoleTopbar: {
    consoleStatusBar: "Barra di stato della console",
    utilityActions: "Azioni di servizio",
  },
  mobileNavigation: {
    navigationLabel: (section: string) => `Navigazione mobile di Axis. Sezione corrente: ${section}`,
    sheetDescription: (section: string) =>
      `Sezione corrente: ${section}. Scelga un'altra area della console.`,
    limesAxisOverview: "Limes Axis, panoramica",
    navigateAxis: "Navigazione in Axis",
    allAxisSections: "Tutte le sezioni di Axis",
  },
  modelRoutingConsole: {
    noLiveInvocationsDetail: (flag: string) =>
      `Per questo tenant non sono registrate invocazioni effettive dei modelli. L'esecuzione del routing dei modelli è rinviata per impostazione predefinita finché ${flag} non viene attivato sull'API; le richieste rinviate non effettuano alcuna chiamata ai provider e Axis non inventa mai righe.`,
    modelRoutingDataIsNot:
      "I dati di routing dei modelli non vengono caricati finché l'attore e il tenant correnti non sono verificati.",
    theAuthenticatedIdentityResponseDoes:
      "La risposta dell'identità autenticata non contiene un tenant. Axis non ripiegherà su dati di routing dimostrativi.",
    modelRoutingSourceAndStatus: "Fonte e stato del routing dei modelli",
    routingTelemetry: "Telemetria del routing",
    allProviders: "Tutti i provider",
    allDecisions: "Tutte le decisioni",
    resetRoutingFilters: "Reimpostare i filtri del routing",
    routes: "Route",
    providerBoundary: "Perimetro del provider",
    hosting: "Hosting",
    costBasis: "Base di costo",
    budgetNotes: "Note sul budget",
    liveExecuted: "Eseguita",
    loadingLiveModelRouterData: "Caricamento dei dati del router dei modelli in tempo reale",
    liveModelRouter: "Router dei modelli in tempo reale",
    executedInvocations: "Invocazioni eseguite",
    persistedInvocationRecordsFromThe:
      "Record delle invocazioni persistiti dal router dei modelli della piattaforma. Conteggi dei token, latenza, stime dei costi e decisioni di egress sono valori registrati, mai dati di riferimento.",
    liveModelRouterSourceAnd: "Fonte e stato del router dei modelli in tempo reale",
    liveInvocations: "Invocazioni effettive",
    awaitingInvocationApi: "In attesa dell'API delle invocazioni",
    noInvocationsRecordedYet: "Nessuna invocazione registrata",
    task: "Attività",
    tokensInOut: "Token in ingresso / uscita",
    estCost: "Costo stimato",
    latency: "Latenza",
    egress: "Egress",
    recorded: "Registrata",
    endpointRegistry: "Registro degli endpoint",
    awaitingEndpointApi: "In attesa dell'API degli endpoint",
    metadataOnly: "Solo metadati",
    noModelEndpointsRegistered: "Nessun endpoint di modello registrato",
    defaultModel: "Modello predefinito",
    taskTypes: "Tipi di attività",
    credentialAttached: "Credenziale associata",
    noCredentialHandle: "Nessun riferimento alle credenziali",
    egressPolicyAttached: "Policy di egress associata",
    noEgressPolicy: "Nessuna policy di egress",
    telemetryNotes: "Note sulla telemetria",
  },
  modelRoutingFlow: {
    routingDependencies: "Dipendenze del routing",
    includesBlockedRoutesWidthConfigured:
      "Include le route bloccate. Larghezza = route configurate.",
    selectAProviderOrModel:
      "Selezioni un provider o un modello per esaminarne le route configurate.",
    inspectFirstMatchingRoute: "Esaminare la prima route corrispondente",
    viewProviderRoutes: "Visualizzare le route del provider",
    resetSelection: "Reimpostare la selezione",
    noConfiguredRoutesToCompare: "Nessuna route configurata da confrontare.",
    providerToModelDiagram: "Diagramma da provider a modello",
    routesByProviderAndModel: "Route per provider e modello",
  },
  oidcSessionBridge: {
    oidcSession: "Sessione OIDC",
    oidcBearerToken: "Bearer token OIDC",
    bearerToken: "Bearer token",
    connectOidcSession: "Collegare la sessione OIDC",
    cancelOidcSessionEntry: "Annullare l'inserimento della sessione OIDC",
    connectOidcBearerToken: "Collegare il bearer token OIDC",
    clearOidcSession: "Cancellare la sessione OIDC",
  },
  ontologyEntityDetail: {
    backToOntology: "Tornare all'ontologia",
    notFoundDetail: (nodeId: string) =>
      `Non esiste alcuna entità dell'ontologia con ID ${nodeId}. Potrebbe essere stata rinominata o rimossa dal grafo.`,
    theEntityIsNotLoaded:
      "L'entità non viene caricata finché l'attore e il tenant correnti non sono verificati.",
    theAuthenticatedIdentityResponseDoes:
      "La risposta dell'identità autenticata non contiene un tenant. Axis non ripiegherà su un'entità dimostrativa.",
    loadingEntityApi: "Caricamento dell'API delle entità",
    axisDidNotReceiveAn:
      "Axis non ha ricevuto un'entità dell'ontologia dall'API. I record delle entità locali di riserva sono disattivati.",
    entityApiUnavailable: "API delle entità non disponibile",
    entityNotFound: "Entità non trovata",
    ontologyEntity: "Entità dell'ontologia",
    entitySourceAndNodeStatus: "Fonte dell'entità e stato del nodo",
    ontology: "Ontologia",
  },
  ontologyEntityDetailContent: {
    incomingRelationships: "Relazioni in ingresso",
    inbound: "In ingresso",
    outgoingRelationships: "Relazioni in uscita",
    outbound: "In uscita",
    relationships: "Relazioni",
    governance: "Governance",
    accessAndEvidence: "Accesso ed evidenze",
    derivedReadScope: "ambito di lettura derivato",
    nodeSummaryOnly: "solo riepilogo del nodo",
    workflows: "Workflow",
    noWorkflowRelation: "nessuna relazione con workflow",
    approvals: "Approvazioni",
    noApprovalRelation: "nessuna relazione con approvazioni",
    agents: "Agenti",
    noAgentRelation: "nessuna relazione con agenti",
    dataAccess: "Accesso ai dati",
    publicDemoSummaryOnly: "Solo riepilogo della demo pubblica",
    detailNotes: "Note di dettaglio",
  },
  ontologyEntitySheet: {
    liveRefreshFailedShowingThe:
      "Aggiornamento non riuscito. Vengono mostrati gli ultimi dati convalidati dell'entità.",
  },
  ontologyExplorer: {
    loadingOntologyApi: "Caricamento dell'API dell'ontologia",
    theOntologyIsNotLoaded:
      "L'ontologia non viene caricata finché l'attore e il tenant correnti non sono verificati.",
    theAuthenticatedIdentityResponseDoes:
      "La risposta dell'identità autenticata non contiene un tenant. Axis non ripiegherà sull'ontologia dimostrativa.",
    axisDidNotReceiveApi:
      "Axis non ha ricevuto record dell'ontologia dall'API. I record dell'ontologia locali di riserva sono disattivati.",
    ontologyApiUnavailable: "API dell'ontologia non disponibile",
    ontologySource: "Fonte dell'ontologia",
    ontologyView: "Vista dell'ontologia",
    graph: "Grafo",
    list: "Elenco",
    ontologyNodes: "Nodi dell'ontologia",
    ontologyRelationships: "Relazioni dell'ontologia",
    relationship: "Relazione",
    from: "Da",
    to: "A",
    sourceSystems: "Sistemi di origine",
    connectedContext: "Contesto collegato",
    graphQuery: "Query sul grafo",
    ontologyGraphQueryMetadata: "Metadati della query sul grafo dell'ontologia",
    permissionNotes: "Note sulle autorizzazioni",
    readBoundaries: "Perimetri di lettura",
  },
  overviewActivityTimeline: {
    returnedWindow: "Finestra restituita",
    chartLegend: "Legenda del grafico",
    eventsLeftAxis: "Eventi · asse sinistro",
    attentionShareRightAxis: "Quota da attenzionare · asse destro",
    eventsAndAttentionShareBy: "Eventi e quota da attenzionare per data UTC; scorra per altre date",
    eventsAndAttentionShareBy2: "Eventi e quota da attenzionare per data UTC",
    chooseAUtcDateArrow:
      "Scelga una data UTC. I tasti freccia spostano la selezione; Invio o Spazio selezionano; Esc annulla.",
    noValidTimestampsToPlot: "Nessun timestamp valido da rappresentare.",
    onlyOneUtcDateIn: "In questa finestra è presente una sola data UTC.",
    selectADateToInspect: "Selezioni una data da esaminare. Solo date restituite.",
    noDatedActivityInThis: "Nessuna attività datata in questa finestra.",
    dailyValues: "Valori giornalieri",
    attentionWatchActionRequiredShare:
      "Da attenzionare = Da monitorare + Intervento necessario; quota sugli eventi restituiti di quella data. Non sono totali giornalieri completi.",
    dailyActivityValues: "Valori giornalieri dell'attività",
  },
  overviewArtifactPanel: {
    governedArtifactActions: "Azioni sugli artefatti governati",
    persisting: "Salvataggio in corso...",
    idempotentReplay: "Ripetizione idempotente",
    created: "Creato",
    artifactPersistenceFailed: "Persistenza dell'artefatto non riuscita",
  },
  overviewNeedsAttention: {
    openTheFullApprovalInbox: "Aprire l'elenco completo delle approvazioni",
    needsAttentionDataSources: "Fonti dati degli elementi da esaminare",
  },
  overviewPostureCards: {
    platformPosture: "Stato della piattaforma",
  },
  overviewSideRail: {
    activityByDate: "Attività per data",
    activityChartView: "Vista del grafico delle attività",
    category: "Categoria",
    byDate: "Per data",
  },
  pageActions: {
    pageActions: "Azioni della pagina",
  },
  platformOverview: {
    overviewDataSources: "Fonti dati della panoramica",
    theConsoleCouldNotVerify:
      "La console non è riuscita a verificare l'attore e il tenant correnti. I dati del tenant non vengono caricati finché l'identità non è disponibile.",
    theAuthenticatedIdentityResponseDoes:
      "La risposta dell'identità autenticata non contiene un tenant. Axis non ripiegherà su dati dimostrativi per un attore autenticato.",
    operationsEvidence: "Evidenze operative",
  },
  policyConditionFields: {
    operationsFinanceCommaSeparated: "Operazioni, Finanza (separati da virgola)",
  },
  policyCreateForm: {
    authorPolicy: "Creazione della policy",
    newPolicy: "Nuova policy",
    platformPolicyAuthoring: "Creazione di policy di piattaforma",
    policyId: "ID policy",
    newPolicyId: "ID della nuova policy",
    newPolicyVersion: "Versione della nuova policy",
    newPolicyScope: "Ambito della nuova policy",
    newPolicyEffect: "Effetto della nuova policy",
    newPolicyDisplayName: "Nome visualizzato della nuova policy",
    denyCriticalActions: "Negare le azioni critiche",
    newPolicyDescription: "Descrizione della nuova policy",
    whatThisPolicyGatesAnd: "Che cosa controlla questa policy e perché",
    newPolicyNotes: "Note della nuova policy",
    authoring: "Creazione in corso",
    authorPolicy2: "Creare la policy",
    previewEvaluation: "Anteprima della valutazione",
    advisoryDryRunForThe: "Esecuzione di prova consultiva per l'ambito in bozza",
  },
  policyDetail: {
    policyRevisionHistory: "Cronologia delle revisioni della policy",
    authored: "Creata",
    initialRevision: "Revisione iniziale",
    platformPolicy: "Policy di piattaforma",
    policyNotFound: "Policy non trovata",
    policySourceAndStatus: "Fonte e stato della policy",
    currentRevision: "Revisione corrente",
    onlyTheActiveRevisionIs: "Viene valutata solo la revisione attiva",
    authoredBy: "Creata da",
    authoringScope: "Ambito di creazione",
    ruleConditions: "Condizioni della regola",
    riskLevels: "Livelli di rischio",
    autonomyLevels: "Livelli di autonomia",
    noAmountGate: "Nessuna soglia di importo",
    malformedAmountsFailClosed: "Gli importi non validi vengono respinti in modo sicuro",
    deterministicDecisionOrder: "Ordine di decisione deterministico",
    policyRevisionResult: "Risultato della revisione della policy",
    revisionHistory: "Cronologia delle revisioni",
    supersededRevisionsStayReadableBut:
      "Le revisioni sostituite restano consultabili ma non vengono mai valutate.",
    revisionCompare: "Confronto delle revisioni",
    diffARevisionAgainstThe: "Confrontare una revisione con quella corrente",
    fieldLevelCompareOfName:
      "Confronto campo per campo di nome, descrizione, effetto e condizioni tipizzate.",
    compareRevision: "Revisione da confrontare",
    revisionToCompare: "Revisione da confrontare",
    selectARevision: "Selezioni una revisione",
    onlyTheInitialRevisionExists:
      "Esiste solo la revisione iniziale; aggiunga una revisione per confrontare le definizioni.",
    dryRunEvaluation: "Valutazione di prova",
    evaluateAContextAgainstTenant: "Valutare un contesto rispetto alle policy del tenant",
    dryRunOnlyEvaluationIs:
      "Solo esecuzione di prova: la valutazione è deterministica, non registra eventi di audit e non modifica mai lo stato.",
  },
  policyEvaluationPanel: {
    noActivePolicyMatchedThis: "Nessuna policy attiva corrisponde a questo contesto",
    matchedPolicies: "Policy corrispondenti",
    evidencePayload: "Payload delle evidenze",
    evaluationScope: "Ambito di valutazione",
    actionDomain: "Dominio di azione",
    actionDomain2: "Dominio di azione",
    operations: "Operazioni",
    riskLevel: "Livello di rischio",
    riskLevel2: "Livello di rischio",
    notSet: "Non impostato",
    autonomyLevel: "Livello di autonomia",
    autonomyLevel2: "Livello di autonomia",
    requestedAmount: "Importo richiesto",
    requestedAmount2: "Importo richiesto",
    evaluating: "Valutazione in corso",
    runDryRunEvaluation: "Eseguire la valutazione di prova",
  },
  policyRegistry: {
    policyAuthoringResult: "Risultato della creazione della policy",
    policySourceAndRegistryStatus: "Fonte delle policy e stato del registro",
    tenantScopedRulesMatchingThe: "Regole del tenant che corrispondono ai filtri correnti",
    deny: "Negare",
    hardBlocksThatRejectMatching:
      "Blocchi rigidi che respingono le esecuzioni di azioni corrispondenti",
    requireApproval: "Richiedere approvazione",
    rulesThatForceTheHuman: "Regole che impongono il passaggio di approvazione umana",
    allowWithEvidence: "Consentire con evidenze",
    rulesThatRecordDecisionEvidence:
      "Regole che registrano le evidenze della decisione all'esecuzione",
    policyRegistry: "Registro delle policy",
    noPoliciesMatchTheCurrent: "Nessuna policy corrisponde ai filtri correnti",
    thePolicyApiRespondedWithout:
      "L'API delle policy ha risposto senza record per la selezione di tenant, ambito e stato. Crei la prima policy del tenant con il modulo seguente.",
  },
  policyReviseForm: {
    revisePolicy: "Revisione della policy",
    platformPolicyRevision: "Revisione della policy di piattaforma",
    revisionPolicyVersion: "Versione della policy nella revisione",
    revisionEffect: "Effetto della revisione",
    revisionDisplayName: "Nome visualizzato della revisione",
    revisionDescription: "Descrizione della revisione",
    revisionNotes: "Note della revisione",
    appending: "Aggiunta in corso",
    appendRevision: "Aggiungere la revisione",
  },
  policyRevisionCompare: {
    fieldsChangedRemovedValuesWere:
      "campi modificati. I valori rimossi (−) sono stati eliminati dalla revisione corrente; i valori aggiunti (+) sono nuovi in essa.",
    changed: "Modificato",
    unchanged: "Invariato",
  },
  sessionSecurityConsole: {
    browserSession: (ref: string) => `Sessione del browser ${ref}`,
    sessionShort: (ref: string) => `Sessione ${ref}`,
    current: "Corrente",
    revokingThisBrowsersSessionSigns:
      "La revoca della sessione di questo browser comporta l'uscita tramite il provider di identità",
    signOut: "Uscire",
    revoking: "Revoca in corso",
    revoke: "Revocare",
    signedOut: "Disconnessa",
    noAuthenticatedOperatorSession: "Nessuna sessione operatore autenticata",
    sessionManagementListsOnlyApi:
      "La gestione delle sessioni elenca solo sessioni verificate dall'API. Acceda con la sessione OIDC del browser gestita dall'API, oppure associ un bearer token dal pannello dell'account, prima di gestire le sessioni.",
    liveSessionDataRequiresThe:
      "I dati delle sessioni in tempo reale richiedono le API delle sessioni di identità di Axis. I record di sessione locali di riserva sono disattivati.",
    sessionsApiUnavailable: "API delle sessioni non disponibile",
    browserSessions: "Sessioni del browser",
    tenantWideSessions: "Sessioni dell'intero tenant",
    yourSessions: "Le Sue sessioni",
    showMySessions: "Mostrare le mie sessioni",
    showTenantSessions: "Mostrare le sessioni del tenant",
    loadingSessions: "Caricamento delle sessioni",
    liveRefreshFailedShowingThe:
      "Aggiornamento non riuscito. Vengono mostrati gli ultimi dati di sessione convalidati.",
    noBrowserSessionsRecorded: "Nessuna sessione del browser registrata",
    axisHasNoPersistedOidc:
      "Axis non ha sessioni OIDC del browser persistite per questo attore. I collegamenti tramite bearer token non creano sessioni con cookie; acceda con SSO per avviarne una.",
    empty: "Vuoto",
    loadingPersistedSessionRecordsFrom:
      "Caricamento dei record di sessione persistiti dall'API di Axis.",
    sessionRevocationFailed: "Revoca della sessione non riuscita",
    platformControl: "Controllo della piattaforma",
    apiOwnedOidcBrowserSessions:
      "Sessioni OIDC del browser gestite dall'API, con evidenze di rotazione, revoca e uscita.",
    sessionSecurity: "Sicurezza delle sessioni",
    liveSessionManagementRequiresThe:
      "La gestione delle sessioni in tempo reale richiede le API di identità di Axis. I record di sessione locali di riserva sono disattivati.",
    operatorSession: "Sessione operatore",
    apiVerifiedIdentity: "Identità verificata dall'API",
    cookieSession: "Sessione con cookie",
    bearerSession: "Sessione con bearer token",
    sessionBoundary: "Perimetro della sessione",
    scopes: "Ambiti",
    thisConsoleIsAttachedThrough:
      "Questa console è collegata tramite il bearer bridge per sviluppatori. La revoca seguente si applica alle sessioni del browser con cookie persistite; per scollegare questa console, cancelli il bearer bridge dal pannello dell'account.",
  },
  sidebarAccount: {
    openPlatformHelp: "Aprire l'assistenza della piattaforma",
  },
  simulationConsole: {
    theConsoleCouldNotVerify:
      "La console non è riuscita a verificare l'attore e il tenant correnti. I dati di replay non vengono caricati finché l'identità non è disponibile.",
    simulationSourceAndStatus: "Fonte e stato della simulazione",
    replayWindow: "Finestra di replay",
    windowStart: "Inizio della finestra",
    timeline: "Cronologia",
    historyEvents: "eventi della cronologia",
    ledgerEvents: "eventi del registro",
    outputs: "Output",
    artifacts: "Artefatti",
    workflowHistoryEvents: "eventi della cronologia dei workflow",
    replayReady: "Pronto per il replay",
    no: "No",
    previewFoundation: "base di anteprima",
    policySimulation: "Simulazione delle policy",
    baseline: "Riferimento",
    simulated: "Simulato",
    outcomeChange: "Variazione dell'esito",
    policySetDiff: "Differenze tra insiemi di policy",
    baselineSet: "Insieme di riferimento",
    candidateSet: "Insieme candidato",
    diffStatus: "Stato del confronto",
    changedPolicies: "Policy modificate",
    auditEventTypes: "Tipi di eventi di audit",
    mode: "Modalità",
    replayTrace: "Traccia del replay",
    timelineEvidence: "Evidenze della cronologia",
    persistedOutputs: "Output persistiti",
    noPersistedOutput: "Nessun output persistito",
    retention: "Conservazione",
    requestedBy: "Richiesto da",
    simulationNotes: "Note sulla simulazione",
  },
  tenantDetail: {
    axisDidNotReceiveAn:
      "Axis non ha ricevuto un tenant di piattaforma dall'API. I record dei tenant locali di riserva sono disattivati.",
    platformTenant: "Tenant di piattaforma",
    tenantNotFound: "Tenant non trovato",
    theTenantReadRouteReturned:
      "La route di lettura del tenant ha restituito 404: non è stato predisposto alcun tenant con questo ID.",
    noDescriptionRecorded: "Nessuna descrizione registrata.",
    tenantSourceAndStatus: "Fonte e stato del tenant",
    onlyActiveTenantsCanEstablish: "Solo i tenant attivi possono stabilire sessioni",
    createdBy: "Creato da",
    bootstrapAdmin: "Amministratore iniziale",
    optionalActorCreatedAtProvisioning: "Attore facoltativo creato al momento del provisioning",
    lastAuditEvent: "Ultimo evento di audit",
    noAuditId: "Nessun ID di audit",
    lifecycleTimeline: "Cronologia del ciclo di vita",
    provisioningAndLifecycleTransitions: "Provisioning e transizioni del ciclo di vita",
    everyTransitionRecordsTheOperator:
      "Ogni transizione registra l'attore operatore, un motivo facoltativo ed evidenze di audit in sola aggiunta.",
    unknownActor: "Attore sconosciuto",
    reason: "Motivo",
    noReasonRecorded: "Nessun motivo registrato",
    auditEventId: "ID dell'evento di audit",
    supersededByLaterEvent: "Sostituito da un evento successivo",
    tenantNotes: "Note sul tenant",
  },
  tenantLifecycleActions: {
    lifecycleActions: "Azioni del ciclo di vita",
    reactivateTenant: "Riattivare il tenant",
    noActionsAvailable: "Nessuna azione disponibile",
    suspendTenant: "Sospendere il tenant",
    suspensionReason: "Motivo della sospensione",
    suspensionReason2: "Motivo della sospensione",
    whyThisTenantIsBeing: "Perché questo tenant viene sospeso",
    reactivationReasonOptional: "Motivo della riattivazione (facoltativo)",
    reactivationReason: "Motivo della riattivazione",
    optionalReasonForReactivating: "Motivo facoltativo della riattivazione",
    reactivating: "Riattivazione in corso",
  },
  tenantProvisionForm: {
    provisionTenant: "Provisioning del tenant",
    newTenant: "Nuovo tenant",
    tenantProvisioning: "Provisioning dei tenant",
    tenantId: "ID tenant",
    newTenantId: "ID del nuovo tenant",
    newTenantDisplayName: "Nome visualizzato del nuovo tenant",
    acmeManufacturing: "Acme Manifatture",
    newTenantDescription: "Descrizione del nuovo tenant",
    whatThisTenantIsFor: "A che cosa serve questo tenant (facoltativo)",
    bootstrapAnAdminActor: "Creare un attore amministratore iniziale",
    bootstrapAnAdminActorFor: "Creare un attore amministratore iniziale per questo tenant",
    bootstrapAdminActorId: "ID dell'attore amministratore iniziale",
    bootstrapAdminActorId2: "ID dell'attore amministratore iniziale",
    bootstrapAdminDisplayName: "Nome visualizzato dell'amministratore iniziale",
    bootstrapAdminDisplayName2: "Nome visualizzato dell'amministratore iniziale",
    acmeAdministrator: "Amministratore Acme",
    bootstrapAdminRequestedScopesComma:
      "Ambiti richiesti per l'amministratore iniziale (separati da virgola o a capo)",
    bootstrapAdminRequestedScopes: "Ambiti richiesti per l'amministratore iniziale",
    recordedAsAuditEvidenceOnly:
      "Registrati solo come evidenze di audit. La concessione degli ambiti resta in capo all'IdP; l'API non li concede mai in tempo reale.",
    newTenantNotes: "Note del nuovo tenant",
    optionalProvisioningNotes: "Note facoltative sul provisioning",
    signInWithSsoTo: "Acceda con SSO per eseguire il provisioning dei tenant.",
    provisioning: "Provisioning in corso",
    provisionTenant2: "Eseguire il provisioning del tenant",
  },
  tenantQuotaEditor: {
    perTenantQuotas: "Quote per tenant",
    quotaOverrides: "Personalizzazioni delle quote",
    leavingAFieldBlankClears:
      "Lasciando vuoto un campo si elimina la personalizzazione e si torna alla configurazione globale.",
    tenantQuotaUpdate: "Aggiornamento delle quote del tenant",
    globalDefault: "Valore globale predefinito",
    confirmTheQuotaUpdateBlank:
      "Confermi l'aggiornamento delle quote: i campi vuoti eliminano la personalizzazione.",
    confirmQuotaUpdate: "Confermare l'aggiornamento delle quote",
    cancel: "Annullare",
    reviewQuotaUpdate: "Esaminare l'aggiornamento delle quote",
    quotaTechnicalDetails: "Dettagli tecnici delle quote",
  },
  tenantRegistry: {
    showingTenants: (count: string) => `Sono mostrati ${count} tenant. Altri tenant corrispondono a questo filtro.`,
    axisDidNotReceiveApi:
      "Axis non ha ricevuto record dei tenant di piattaforma dall'API. I record dei tenant locali di riserva sono disattivati.",
    tenantSourceAndRegistryStatus: "Fonte dei tenant e stato del registro",
    crossTenantOperatorSurfaceEvery:
      "Area operativa trasversale ai tenant; ogni modifica del ciclo di vita aggiunge evidenze di audit.",
    tenantsMatchingTheCurrentStatus: "Tenant corrispondenti al filtro di stato corrente",
    active: "Attivi",
    tenantsAbleToEstablishSessions: "Tenant in grado di stabilire sessioni",
    suspended: "Sospesi",
    rejectedFailClosedAtThe: "Respinti in modo sicuro al perimetro del principal OIDC",
    pendingDeletion: "In attesa di eliminazione",
    modeledAndBlockedNoDeletion:
      "Modellato e bloccato; nessuna pipeline di eliminazione ancora disponibile",
    tenantRegistry: "Registro dei tenant",
    createdBy: "Creato da",
    lifecycle: "Ciclo di vita",
    noLifecycleChanges: "Nessuna modifica del ciclo di vita",
    loading: "Caricamento…",
    loadMoreTenants: "Caricare altri tenant",
    axisCouldNotLoadThe: "Axis non è riuscito a caricare la pagina successiva dei tenant. Riprovi.",
    tenantPageUnavailable: "Pagina dei tenant non disponibile",
    noTenantsMatchTheCurrent: "Nessun tenant corrisponde al filtro corrente",
    theTenantApiRespondedWithout:
      "L'API dei tenant ha risposto senza record per questa selezione di stato. Esegua il provisioning del primo tenant con il modulo seguente.",
  },
  tenantUsagePanel: {
    usageMetering: "Misurazione dei consumi",
    noMeteredConsumptionInThis: "Nessun consumo misurato in questa finestra.",
    perMetricConsumption: "Consumo per metrica",
    usageMethodologyAndAccess: "Metodologia di misurazione e accesso",
    meteringIsCumulativeConsumptionAccounting:
      "La misurazione è una contabilizzazione cumulativa dei consumi; le quote restano i limiti applicati.",
  },
  tenantVocabularyEditor: {
    vocabularyTechnicalDetails: "Dettagli tecnici del vocabolario",
  },
  topbarAccountPanel: {
    pasteTokenError: "Incolli un bearer token JWT per collegare una sessione OIDC.",
    tokenRejected: "Token rifiutato. Axis richiede un JWT con i claim sub e axis_tenant.",
    sessionEndpointRequired: "La sessione di identità richiede `/identity/session`.",
    needsSessionEndpoint:
      "Il pannello dell'account richiede `/identity/session` per poter mostrare un attore verificato dall'API.",
    operatorAccount: "Account operatore",
    operator: "Operatore",
    publicEvaluationOperator: "Operatore di valutazione pubblica",
    apiStatus: "Stato dell'API",
    ssoPosture: "Stato dell'SSO",
    enterpriseReady: "Pronto per l'uso aziendale",
    needsHardening: "Da rafforzare",
    sessionExpires: "Scadenza della sessione",
    capability: "Funzionalità",
    limitation: "Limitazione",
    noScopesInToken: "Nessun ambito nel token",
    awaitingApiValidation: "In attesa di convalida da parte dell'API",
    manageSessions: "Gestire le sessioni",
    signOutWithIdentityProvider: "Uscire tramite il provider di identità",
    clearBearerBridge: "Cancellare il bearer bridge",
    openSsoSetup: "Aprire la configurazione SSO",
    developerAccess: "Accesso per sviluppatori",
    forLocalDevelopmentAgainstA: "Per lo sviluppo locale con un'API senza SSO.",
    developerBearerBridge: "Bearer bridge per sviluppatori",
    pasteJwtAccessToken: "Incolli l'access token JWT",
    attachBearerBridge: "Associare il bearer bridge",
  },
  topbarHelpPanel: {
    platformHelp: "Assistenza della piattaforma",
    docs: "Documentazione",
    modelRouting: "Routing dei modelli",
    inspectProviderBoundariesAndEgress:
      "Esamini i perimetri dei provider e le decisioni di egress.",
    architectureDocs: "Documentazione di architettura",
    openThePublicPlatformArchitecture:
      "Apra le note pubbliche sull'architettura della piattaforma.",
  },
  topbarNotificationPanel: {
    notifications: "Notifiche",
    loadingNotificationEvidence: "Caricamento delle evidenze delle notifiche.",
    acknowledged: "Presa visione",
    open: "Aperta",
    acked: "Vista",
    ack: "Presa visione",
    noActiveNotifications: "Nessuna notifica attiva",
    axisDidNotDerivePending:
      "Axis non ha ricavato avvisi in sospeso dallo stato persistito della piattaforma.",
    openAuditEvidence: "Aprire le evidenze di audit",
  },
  uiInspectDrawer: {
    inspect: "Esaminare",
    rawRecordFieldsExactlyAs: "Campi del record originale, esattamente come restituiti dall'API.",
    fields: "Campi",
    raw: "Originale",
    thisRecordHasNoFields: "Questo record non ha campi.",
  },
  uiStates: {
    loadingContent: "Caricamento del contenuto",
    apiBaseUrl: "URL di base dell'API",
  },
  uiToast: {
    viewDetails: "Visualizzare i dettagli",
    dismissNotification: "Ignorare la notifica",
  },
  workflowConsole: {
    currentBlocker: "Blocco corrente",
    workflowRuntimeTimeline: "Cronologia di esecuzione del workflow",
    theConsoleCouldNotVerify:
      "La console non è riuscita a verificare l'attore e il tenant correnti. I dati dei workflow non vengono caricati finché l'identità non è disponibile.",
    loadingWorkflowApi: "Caricamento dell'API dei workflow",
    workflowSourceAndRuntimeStatus: "Fonte dei workflow e stato di runtime",
    runtimeNotes: "Note di runtime",
  },
  ontologyGraph: {
    graphLabel: (nodes: number, relationships: number) =>
      `Grafo dell'ontologia con ${nodes} nodi e ${relationships} relazioni`,
  },
  overviewEvidenceFeed: {
    showingRecent: (shown: number, total: number) => `Sono mostrati ${shown} di ${total} eventi recenti`,
  },
  detailPages: {
    entityTitle: "Dettaglio dell'entità",
    entityMetaTitle: (nodeId: string) => `Entità ${nodeId}`,
    policyTitle: "Dettaglio della policy",
    policyMetaTitle: (policyId: string) => `Policy ${policyId}`,
    tenantTitle: "Dettaglio del tenant",
    tenantMetaTitle: (tenantId: string) => `Tenant ${tenantId}`,
    sessionsTitle: "Sessioni",
    sessionsDescription: "Esamini e revochi le sessioni attive della console per questo tenant.",
  },
  rootLayout: {
    title: "Axis Console",
    titleTemplate: "%s · Axis Console",
    description: "Il piano di controllo AI sovrano per le operazioni europee.",
  },
} as const;

export const stringsIt: ConsoleStrings = {
  clarity: {
    objectSummary: "Riepilogo",
    entityPurpose: "Esamini questo oggetto, le sue relazioni e chi vi può accedere.",
    policyPurpose: "Esamini la regola, confronti le revisioni e ne verifichi l'effetto.",
    tenantPurpose:
      "Gestisca gli accessi, i limiti di risorse e l'attività di questa organizzazione.",
    auditEventIdUnavailable: "ID dell'evento di audit non disponibile",
    recordedActivity: "Attività registrata",
    advancedConnectorImport: "Avanzate: importazione della configurazione dei connettori",
    actionCatalog: "Catalogo delle azioni: azioni disponibili e autorizzazioni",
    agentDetails: "Dettagli del registro degli agenti",
    modelMonitoring: "Dettagli del monitoraggio dei modelli",
    businessObjects: "Oggetti di business",
    relationships: "Relazioni",
    ontologySources: "Fonti e dettagli di accesso",
    ontologyObjects: "Oggetti di business e collegamenti",
    graphRegion: "Grafo dell'ontologia scorrevole",
    createPolicy: "Creare una policy",
    createOrganization: "Creare un'organizzazione",
    activity: {
      title: "Attività per categoria",
      window: (value: number, limit: number) =>
        `Distribuzione di ${value} eventi nell'ultima finestra (fino a ${limit}).`,
      dateWindow: (value: number, limit: number) =>
        `${value} eventi restituiti · ultima finestra, fino a ${limit}.`,
      errorTitle: "Ripartizione delle attività non disponibile",
      errorDetail: "Aggiorni la pagina per caricare la finestra di audit recente.",
      emptyTitle: "Nessuna attività da confrontare",
      emptyDetail: "Gli eventi registrati compariranno qui.",
    },
  },
  scopeDenial,
  nav,
  shell,
  identityGate,
  commandMenu,
  routeError,
  notFound,
  globalError,
  demoBadge,
  agents,
  approvals,
  audit,
  dataCatalog: {
    searchLabel: "Cercare negli asset di dati",
    searchPlaceholder: "Cerchi per nome o connettore",
    evidenceFilterLabel: "Filtrare per evidenza",
    evidence: {
      all: "Tutte le evidenze",
      sync_observed: "Sincronizzazione osservata",
      preview_only: "Solo anteprima",
      declared_only: "Solo dichiarato",
    },
    governance: {
      declared: "Governance dichiarata",
      partial: "Governance parziale",
      not_declared: "Governance non dichiarata",
    },
    listTitle: "Asset",
    detail: {
      assetId: "ID asset",
      connector: "Connettore",
      kind: "Tipo di asset",
      evidence: "Evidenza",
      governance: "Governance",
      sourceType: "Tipo di fonte",
      runtimeBoundary: "Perimetro di runtime",
      egressPolicy: "Policy di egress",
      payloadPolicy: "Policy sui contenuti",
      syncModes: "Modalità di sincronizzazione",
      lastSync: "Ultima sincronizzazione riuscita",
      manifestRevision: "Revisione del manifest",
      registryOrigin: "Origine nel registro",
      schemaTitle: "Corrispondenza dello schema dichiarata",
      schemaRegion: "Corrispondenza dello schema dichiarata scorrevole",
      schemaEmpty: "Questa fonte non ha ancora una corrispondenza dei campi dichiarata.",
      ontologyTargets: "Destinazioni nell'ontologia",
      notes: "Note di catalogo",
      columns: {
        source: "Colonna della fonte",
        target: "Campo di destinazione",
        ontology: "Destinazione nell'ontologia",
        type: "Tipo",
        required: "Obbligatorio",
      },
    },
    stewardship: {
      title: "Stewardship",
      description:
        "Responsabile dichiarato e vincoli di trattamento di questo asset. Le dichiarazioni sono versionate e idempotenti.",
      fields: {
        owner: "Responsabile",
        classification: "Classificazione",
        residency: "Residenza dei dati",
        retention: "Conservazione",
        revision: "Revisione",
        declaredBy: "Dichiarato da",
        declaredAt: "Dichiarato il",
      },
      classificationLabels: {
        public: "Pubblico",
        internal: "Interno",
        confidential: "Riservato",
        restricted: "Ad accesso limitato",
      },
      form: {
        title: "Dichiarazione di stewardship",
        description:
          "Dichiari un responsabile e i vincoli di trattamento di questo asset. La prima dichiarazione crea la revisione 1; gli aggiornamenti successivi passano dallo stesso endpoint.",
        submit: "Dichiarare la stewardship",
        submitting: "Dichiarazione in corso…",
        success: "Stewardship dichiarata.",
        errors: {
          ownerRequired: "Il responsabile è obbligatorio.",
          ownerTooLong: (limit: number) =>
            `Il responsabile può contenere al massimo ${limit} caratteri.`,
          residencyRequired: "La residenza dei dati è obbligatoria.",
          residencyTooLong: (limit: number) =>
            `La residenza dei dati può contenere al massimo ${limit} caratteri.`,
          retentionRequired: "La conservazione è obbligatoria.",
          retentionTooLong: (limit: number) =>
            `La conservazione può contenere al massimo ${limit} caratteri.`,
          declareFailed: "La dichiarazione di stewardship non è stata applicata.",
          conflict:
            "Un altro utente ha aggiornato la stewardship di questo asset durante la modifica. Ricarichi l'asset e riprovi con il record corrente.",
        },
      },
      states: {
        error: {
          title: "Stewardship non disponibile",
          detail:
            "Axis non è riuscito a caricare il record di stewardship di questo asset. Non viene mostrato nulla per evitare di presentare una dichiarazione non aggiornata o inventata.",
        },
      },
    },
    contract: {
      title: "Contratto dati",
      description:
        "Aspettative dichiarate valutate rispetto alle evidenze osservate al momento della lettura. Gli asset non dichiarati o non osservati risultano sconosciuti, mai conformi.",
      status: {
        pass: "Conforme",
        warn: "Avviso",
        fail: "Non conforme",
        unknown: "Sconosciuto",
        notDeclared: "Nessun contratto dichiarato",
      },
      checks: {
        presence: "Presenza",
        schema: "Schema",
        freshness: "Aggiornamento",
      },
      fields: {
        expectedResource: "Risorsa attesa",
        expectedFingerprint: "Fingerprint dello schema atteso",
        warnHours: "Soglia di avviso per l'aggiornamento (ore)",
        failHours: "Soglia di non conformità per l'aggiornamento (ore)",
        revision: "Revisione",
        declaredBy: "Dichiarato da",
        declaredAt: "Dichiarato il",
      },
      form: {
        title: "Dichiarazione di un contratto dati",
        description:
          "Indichi la risorsa che questo asset deve continuare a osservare e, facoltativamente, il fingerprint esatto dell'intestazione e il grado di aggiornamento richiesto per l'ultima osservazione.",
        submit: "Dichiarare il contratto",
        submitting: "Dichiarazione in corso…",
        success: "Contratto dichiarato. La valutazione avviene ora su osservazioni reali.",
        errors: {
          resourceRequired: "Il nome della risorsa attesa è obbligatorio.",
          fingerprintInvalid: (limit: number) =>
            `Il fingerprint dello schema deve essere composto da ${limit} caratteri esadecimali.`,
          hoursInvalid: "Le soglie devono essere numeri interi pari ad almeno 1 ora.",
          orderingInvalid:
            "La soglia di avviso non può superare la soglia di non conformità.",
          declareFailed: "La dichiarazione del contratto dati non è stata applicata.",
          conflict:
            "Un altro utente ha aggiornato il contratto di questo asset durante la modifica. Ricarichi l'asset e riprovi con il record corrente.",
        },
      },
      states: {
        error: {
          title: "Contratto dati non disponibile",
          detail:
            "Axis non è riuscito a caricare il contratto di questo asset. Non viene mostrato nulla per evitare di presentare una dichiarazione non aggiornata o inventata.",
        },
      },
    },
    resources: {
      title: "Risorse osservate",
      description:
        "File sorgente effettivamente osservati da Axis attraverso perimetri di anteprima governati. Solo metadati: nomi delle intestazioni e fingerprint, mai i valori delle righe.",
      countSummary: (value: number) =>
        value === 1 ? "1 risorsa osservata" : `${value} risorse osservate`,
      empty: {
        title: "Nessuna risorsa osservata",
        detail:
          "Esegua un'anteprima del connettore con esito positivo per registrare la prima osservazione di questo asset.",
      },
      drift: {
        added: "Aggiunta",
        changed: "Modificata",
        unchanged: "Invariata",
      },
      observations: (value: number) =>
        value === 1 ? "1 osservazione" : `${value} osservazioni`,
      notesTitle: "Come funziona l'osservazione",
      states: {
        error: {
          title: "Osservazioni delle risorse non disponibili",
          detail:
            "Axis non è riuscito a caricare le risorse osservate di questo asset. Non viene mostrato nulla per evitare di presentare un elenco non aggiornato o inventato.",
        },
      },
    },
    states: {
      error: {
        title: "Catalogo dei dati non disponibile",
        detail:
          "Axis non ha ricevuto un catalogo degli asset di dati valido. Non viene mostrato nulla per evitare di presentare asset non aggiornati o inventati.",
      },
      empty: {
        title: "Nessun asset di dati",
        detail:
          "Registri e sincronizzi un connettore per proiettare nel catalogo il primo asset di dati governato.",
      },
      noMatches: {
        title: "Nessun asset corrisponde ai filtri correnti",
        detail:
          "Modifichi la ricerca o il filtro per evidenza per visualizzare il resto del catalogo.",
      },
      unknownAsset: {
        title: "Questo asset di dati non esiste nel catalogo",
        detail:
          "L'ID asset richiesto non fa parte del catalogo di questo tenant. Axis non sostituisce un asset diverso a un link diretto sconosciuto.",
      },
    },
  },
  connectors,
  models,
  onboarding,
  ontology,
  overview,
  policyDetail,
  settings,
  simulation,
  tenantLifecycle,
  tenantVocabulary,
  workflows,
  states: {
    loading: "Caricamento…",
    retry: "Riprovare",
    technicalDetails: "Dettagli tecnici",
    reference: "Riferimento",
    identityUnavailable: {
      title: "Impossibile raggiungere Axis",
    },
    error: {
      title: "Impossibile caricare questi dati",
      detail:
        "La console non è riuscita a raggiungere l'API della piattaforma. Verifichi la connessione e riprovi.",
      retry: "Riprovare",
    },
    empty: {
      title: "Ancora nessun elemento",
      detail: "I record compariranno qui non appena saranno disponibili.",
    },
    tenantEmpty: {
      title: "Questo tenant non ha ancora record",
      detail:
        "Per questo tenant non è ancora stato configurato nulla. Completi la configurazione guidata nella panoramica, oppure carichi i dati dimostrativi: i record compariranno qui.",
      action: "Aprire la configurazione guidata",
    },
    requestedRecord: {
      title: "Il record richiesto non è in questa vista",
      detail:
        "Il record indicato nell'URL non è presente nei risultati correnti. Cancelli la selezione o modifichi i filtri.",
    },
  },
  pages,
  ui,
};
