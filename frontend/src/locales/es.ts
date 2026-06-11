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
    authContextOutsideProvider: "useAuth debe usarse dentro de AuthProvider.",
  },

  user: {
    defaultUsername: "Usuario",
  },

  authScreen: {
    login: {
      title: "Iniciar sesión",
      subtitle: "Introduce tus credenciales para acceder a COTUTOR IA.",
      formAriaLabel: "Formulario de inicio de sesión",
      usernamePlaceholder: "Nombre de usuario",
      usernameLabel: "Nombre de usuario",
      passwordPlaceholder: "Contraseña",
      passwordLabel: "Contraseña",
      submitButton: "Entrar",
      submitAriaLabel: "Iniciar sesión con las credenciales introducidas",
      registerLink: "¿No tienes cuenta? Crear cuenta",
      forgotHint: "Contacta con tu administrador si has olvidado tu contraseña.",
    },
    register: {
      title: "Crear cuenta",
      subtitle: "Crea tu cuenta para acceder a COTUTOR IA.",
      formAriaLabel: "Formulario de registro",
      usernamePlaceholder: "Nombre de usuario",
      usernameLabel: "Nombre de usuario",
      passwordPlaceholder: "Contraseña",
      passwordLabel: "Contraseña",
      confirmPasswordPlaceholder: "Repite la contraseña",
      confirmPasswordLabel: "Confirmar contraseña",
      submitButton: "Crear cuenta",
      submitAriaLabel: "Crear nueva cuenta con los datos introducidos",
      loginLink: "¿Ya tienes cuenta? Iniciar sesión",
      passwordMismatch: "Las contraseñas no coinciden. Asegúrate de escribir exactamente lo mismo en los dos campos.",
      usernameHint: "Solo minúsculas, números, guion (-) o guion bajo (_).",
      passwordHint: "Mínimo 8 caracteres con mayúscula, minúscula, dígito y símbolo.",
    },
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
    welcomeMessage: (name: string) =>
      `Hola ${name}, soy COTUTOR IA. ¿En qué puedo ayudarte hoy?`,
    loadingMessage: "Cotutor está analizando tu respuesta...",
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
      clearSessionSuccess: "Sesión limpiada correctamente.",
      clearSessionError: "Error al limpiar sesión.",
      logout: "Cerrar sesión",
      logoutLoading: "Cerrando sesión...",
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
      podcasts: "Podcasts",
      summaries: "Resúmenes",
      exams: "Exámenes",
    },
    discoveryHub: {
      openSummaries: "Abrir resúmenes",
      openExams: "Abrir exámenes",
      createAudio: "Crear audio",
      audioLoading: "Generando audio…",
      audioError: "No se pudo generar el audio.",
      emptySummaries:
        "Aún no hay resúmenes guardados. Pide un resumen de tus documentos en el chat (por ejemplo: «resume el manual»).",
      emptyExams:
        "Aún no hay exámenes guardados. Pide un examen o test en el chat (por ejemplo: «hazme un examen sobre el tema X»).",
      modalSummariesTitle: "Resúmenes del chat",
      modalExamsTitle: "Exámenes del chat",
      promptLabel: "Tu petición",
      listLoading: "Cargando…",
      podcastNeedSummaries: "Primero crea resúmenes en el chat; el audio une los que elijas.",
      podcastReadyHint: (count: number) =>
        `Elige cuáles de los ${count} resumen(es) guardados incluir en el audio.`,
      modalPodcastTitle: "Resúmenes para el podcast",
      podcastPickHint:
        "Marca uno o varios resúmenes. El audio seguirá el orden en que aparecen abajo (el más antiguo arriba).",
      podcastSelectAll: "Marcar todos",
      podcastSelectNone: "Quitar todos",
      podcastNeedSelection: "Marca al menos un resumen.",
      podcastLoadingSummaries: "Cargando resúmenes…",
      podcastCancel: "Cancelar",
      podcastListError: "No se pudieron cargar los resúmenes.",
      podcastCloseWhileGeneratingHint:
        "Puedes cerrar este cuadro y seguir usando la app: cuando el audio esté listo verás el reproductor en esta tarjeta.",
    },
  },

  trainer: {
    modeToggle: {
      toTrainer: "Modo formador",
      toStudent: "Modo alumno",
    },
    tabs: {
      config: "Configurar curso",
      progress: "Progreso del alumno",
    },
    chat: {
      title: "Chat de configuración",
      placeholder: "Ej: Crea un curso de Python de 4 semanas, 10h a la semana…",
      send: "Generar",
      generating: "Generando itinerario…",
      hint: "Describe el curso (tema, semanas, horas) y la IA propondrá el cuadrante usando la base de conocimientos.",
      error: "No se pudo generar el itinerario.",
      emptyState: "El itinerario generado aparecerá a la derecha para que lo valides.",
    },
    quadrant: {
      title: "Cuadrante del curso",
      emptyState: "Genera un itinerario con el chat para previsualizarlo aquí.",
      weeksLabel: "Semanas",
      hoursLabel: "Horas/semana",
      themeHeader: "Tema",
      unitHeader: "Concepto",
      definitionHeader: "Definición",
      weightHeader: "Peso %",
      competencyHeader: "Competencia",
      competencyPlaceholder: "Sin enlace",
      competencyLoading: "Cargando competencias…",
      noCompetencies:
        "Sube documentos al proyecto para extraer competencias y poder enlazarlas aquí.",
      totalWeight: (total: string) => `Peso total: ${total}%`,
      weightWarning: "El peso total debería sumar 100%.",
      save: "Validar y Guardar",
      saving: "Guardando…",
      saveSuccess: (msg: string) => msg,
      saveError: "Error al guardar el itinerario.",
      deleteUnitAriaLabel: (name: string) => `Eliminar unidad ${name}`,
    },
    progress: {
      title: "Cuadrante de progreso",
      loading: "Cargando progreso…",
      emptyState:
        "No hay itinerario guardado para esta sesión. Créalo primero en «Configurar curso».",
      error: "No se pudo cargar el progreso.",
      overallLabel: "Nota global",
      refresh: "Actualizar",
      cellAriaLabel: (name: string, score: number) =>
        `${name}: ${score} sobre 10. Pulsa para ver el detalle.`,
      generateQuiz: "Evaluar Unidad",
      generateQuizAriaLabel: (name: string) =>
        `Generar cuestionario adaptativo sobre ${name}`,
    },
    detailModal: {
      generateQuiz: "Generar Cuestionario",
      generateQuizHint:
        "Se creará un cuestionario en el chat (sin soluciones). Envía tus respuestas allí para recibir corrección y nota.",
      title: "Detalle de la celda",
      close: "Cerrar",
      loading: "Cargando detalle…",
      error: "No se pudo cargar el detalle.",
      scoreLabel: "Puntuación total",
      quizPointsLabel: "Puntos por cuestionarios (máx. 7,5)",
      actionPointsLabel: "Puntos por preguntas al chat (máx. 2,5)",
      quizCount: (n: number) => `${n} cuestionario(s)`,
      quizAverage: (avg: string) => `Nota media: ${avg}`,
      noQuizzes: "Sin cuestionarios todavía",
      chatCount: (n: number) => `${n} pregunta(s) al chat`,
      historyTitle: "Histórico de actividades",
      emptyHistory: "Sin actividades registradas en esta celda.",
      activityLabels: {
        video: "Vídeo",
        chat_question: "Pregunta chat",
        quiz: "Cuestionario",
      },
    },
  },

  dashboard: {
    maturity: {
      title: "Competencias de Aprendizaje",
      loadingLabel: "Cargando competencias…",
      criteriaEmpty:
        "Sube documentos al proyecto para que se extraigan competencias y aparezcan aquí.",
      criteriaError: "No se pudieron cargar las competencias.",
      noCompetenciesYet:
        "Aún no hay competencias extraídas para este documento.",
      practiceLevelTitle: (percent: number) =>
        `Práctica en modo aprendizaje: ${percent} % (negro = sin practicar, verde claro = dominio)`,
      practiceLevelAriaLabel: (percent: number) =>
        `Nivel de práctica en modo aprendizaje: ${percent} por ciento. Negro indica sin práctica; cuanto más claro el verde, mayor dominio.`,
    },
  },
} as const;

export type Dictionary = typeof dictionaries;
