/**
 * Diccionario central de textos en español para la interfaz.
 *
 * Convenciones:
 *  - Las claves se agrupan por módulo o componente (common, welcomeScreen, chatPanel, ...).
 *  - Los textos con datos dinámicos se exponen como funciones puras `(args) => string`,
 *    de modo que la concatenación quede contenida aquí y no en el JSX.
 *  - El objeto se marca `as const` para inferir literales y evitar cambios accidentales.
 */
export const dictionaries = {
  common: {
    appName: "COTUTOR IA",
    loading: "Cargando...",
    close: "Cerrar",
    metadataTitle: "COTUTOR IA - Discovery Hub",
    metadataDescription: "Explora y fortalece tus competencias críticas",
  },

  errors: {
    invalidSessionId: "El ID de sesión no es válido.",
    welcomeFallback: "Error al iniciar sesión.",
    userContextOutsideProvider: "useUser debe usarse dentro de UserProvider.",
    projectsContextOutsideProvider:
      "useProjects debe usarse dentro de ProjectsProvider.",
  },

  user: {
    defaultUsername: "Usuario",
  },

  welcomeScreen: {
    title: "Bienvenido al Chatbot RAG Educativo",
    subtitle:
      "Introduce tu nombre de usuario o ID de sesión para continuar. Se guardará tu historial y preferencias.",
    formAriaLabel:
      "Formulario de acceso con nombre de usuario o ID de sesión",
    inputLabel: "Nombre de usuario o ID de sesión",
    inputPlaceholder: "Ej: juan_perez, mi_sesion_123",
    submitButton: "Comenzar",
    submitAriaLabel:
      "Iniciar sesión y entrar al chatbot con el identificador introducido",
    hint: "Usa siempre el mismo nombre para recuperar tu historial.",
  },

  chatPanel: {
    title: "Chat Integrado",
    expandButton: {
      expand: "Expandir chat",
      collapse: "Contraer chat",
    },
    sourcesLabel: (count: number) => `Fuentes citadas (${count})`,
    welcomeMessage: (name: string) =>
      `Hola ${name}, soy COTUTOR IA. ¿En qué puedo ayudarte hoy?`,
    loadingMessage: "Cotutor está analizando tu respuesta...",
    historyButton: "Ver historial completo",
  },

  sidebar: {
    newKnowledgeButton: "Nuevo Conocimiento",
    searchPlaceholder: "Buscar proyecto...",
    uploadModalTitle: "Nuevo Conocimiento",
    uploadModalCurrentProject: (name: string) => `Se añadirá a: ${name}`,
    closeUploadModal: "Cerrar",
    projects: {
      sectionTitle: "Proyectos",
      emptyState: "Crea tu primer proyecto con el botón +.",
      noResults: (query: string) => `Sin resultados para "${query}".`,
      defaultName: (n: number) => `Proyecto ${n}`,
      newProjectAriaLabel: "Crear nuevo proyecto",
      renameAriaLabel: (name: string) => `Renombrar ${name}`,
      selectAriaLabel: (name: string) => `Seleccionar ${name}`,
      deleteAriaLabel: (name: string) => `Eliminar ${name}`,
      expandAriaLabel: (name: string) => `Mostrar documentos de ${name}`,
      collapseAriaLabel: (name: string) => `Ocultar documentos de ${name}`,
      noDocuments: "Sin documentos aún.",
    },
    settings: {
      buttonLabel: "Configuración",
      clearSession: "Limpiar sesión",
      clearSessionLoading: "Limpiando...",
      forgetData: "Olvidar datos sobre mí",
      forgetDataLoading: "Eliminando...",
      clearSessionSuccess: "Sesión limpiada correctamente.",
      clearSessionError: "Error al limpiar sesión.",
      forgetDataSuccess: (count: number) =>
        `Se eliminaron ${count} datos sobre ti.`,
      forgetDataError: "Error al eliminar datos.",
      confirmClear: {
        title: "Limpiar sesión",
        description:
          "Se eliminarán todos los datos guardados de este usuario, incluidos todos los proyectos, sus chats y los conocimientos cargados. Esta acción no se puede deshacer.",
        accept: "Eliminar todo",
        cancel: "Cancelar",
      },
    },
  },

  uploadManager: {
    tabs: {
      manual: "Manual (Upload)",
      cloud: "Nube",
      youtube: "YouTube",
    },
    manual: {
      selectLabel: "Seleccionar PDF",
      submit: "Subir PDF",
      missingFileError: "Selecciona un archivo PDF",
    },
    cloud: {
      description:
        "Carga todos los PDFs configurados en el bucket para esta sesión.",
      loading: "Cargando...",
      submit: "Cargar PDFs del bucket",
    },
    youtube: {
      placeholder: "https://www.youtube.com/watch?v=...",
      submit: "Procesar video",
      missingUrlError: "Introduce la URL del video de YouTube",
    },
    progress: {
      fallbackMessage: "Procesando...",
    },
    result: {
      successFallback: "Completado correctamente.",
      errorFallback: "Error desconocido.",
      closeAndStartOver: "Cerrar y empezar otra",
    },
  },

  mainContent: {
    pageTitle: "Discovery Hub",
    pageSubtitle: "Explora y fortalece tus competencias críticas",
    newProjectButton: "Nuevo Proyecto",
    userMenuLabel: (name: string) =>
      name ? `Menú de usuario (${name})` : "Menú de usuario",
    activesLabel: (count: number) => `${count} Activos`,
    chatInput: {
      placeholder: "Pregúntale a COTUTOR algo sobre los manuales...",
    },
    learningModeToggle: {
      activate: "Activar modo aprendizaje",
      deactivate: "Desactivar modo aprendizaje",
      activeTitle: "Modo aprendizaje activo",
    },
    contentCards: {
      videoPills: "Video Píldoras",
      podcasts: "Podcasts",
      summaries: "Resúmenes",
      exams: "Exámenes",
    },
  },

  dashboard: {
    maturity: {
      title: "Dashboard de Madurez de Habilidades",
      lastUpdated: "Actualizado hace 2h",
      description: "Progreso dinámico según tu actividad y evaluaciones.",
      criteriaSectionTitle: "Criterios de Aprendizaje y Calificaciones",
      heatmapLevelTitle: (level: number) => `Nivel ${level}`,
      criteriaLoading: "Cargando competencias...",
      criteriaEmpty:
        "Sube documentos al proyecto para que se extraigan competencias y aparezcan aquí.",
      criteriaError: "No se pudieron cargar las competencias.",
    },
    categories: {
      dataSovereignty: "Soberanía de Datos",
      privacyArchitecture: "Arquitectura Privacidad",
      aiEthics: "Ética en IA",
    },
    learningCriteria: {
      dataGovernance: {
        name: "Gobernanza de Datos",
        description:
          "Capacidad para diseñar políticas de gobernanza y ciclo de vida del dato.",
      },
      privacyByDesign: {
        name: "Privacy by Design",
        description:
          "Aplicación de principios de privacidad desde la fase de diseño de sistemas.",
      },
      algorithmicBias: {
        name: "Sesgo Algorítmico",
        description:
          "Identificación y mitigación de sesgos en modelos de IA y pipelines de datos.",
      },
    },
  },
} as const;

export type Dictionary = typeof dictionaries;
