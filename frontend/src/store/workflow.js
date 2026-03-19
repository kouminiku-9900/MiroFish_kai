import { reactive } from 'vue'

const STORAGE_KEY = 'mirofish-workflow'

const stageOrder = [
  'upload',
  'ontology',
  'graph_build',
  'simulation_prepare',
  'simulation_run',
  'report_generate'
]

const stageLabelKeys = {
  upload: 'workflow.stage.upload',
  ontology: 'workflow.stage.ontology',
  graph_build: 'workflow.stage.graph_build',
  simulation_prepare: 'workflow.stage.simulation_prepare',
  simulation_run: 'workflow.stage.simulation_run',
  report_generate: 'workflow.stage.report_generate'
}

const createStage = (labelKey) => ({
  labelKey,
  status: 'idle',
  progress: 0,
  message: '',
  messageKey: '',
  updatedAt: null
})

const defaultState = () => ({
  stages: stageOrder.reduce((acc, key) => {
    acc[key] = createStage(stageLabelKeys[key])
    return acc
  }, {}),
  overallStatus: 'idle',
  failedStage: null,
  ids: {
    project_id: null,
    ontology_task_id: null,
    graph_task_id: null,
    simulation_id: null,
    prepare_task_id: null,
    report_id: null,
    report_task_id: null
  }
})

const normalizeStage = (stage, labelKey) => ({
  ...createStage(labelKey),
  ...(stage || {}),
  labelKey
})

const loadState = () => {
  if (typeof window === 'undefined') return defaultState()

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState()
    const parsed = JSON.parse(raw)
    const base = defaultState()

    stageOrder.forEach((key) => {
      base.stages[key] = normalizeStage(parsed.stages?.[key], stageLabelKeys[key])
    })
    base.overallStatus = parsed.overallStatus || 'idle'
    base.failedStage = parsed.failedStage || null
    base.ids = { ...base.ids, ...(parsed.ids || {}) }
    return base
  } catch (error) {
    console.warn('Failed to load workflow state:', error)
    return defaultState()
  }
}

const state = reactive(loadState())

const persist = () => {
  if (typeof window === 'undefined') return

  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
    stages: state.stages,
    overallStatus: state.overallStatus,
    failedStage: state.failedStage,
    ids: state.ids
  }))
}

const updateOverallStatus = () => {
  const statuses = stageOrder.map((key) => state.stages[key].status)

  if (statuses.includes('failed')) {
    state.overallStatus = 'failed'
    return
  }

  if (statuses.every((status) => status === 'completed')) {
    state.overallStatus = 'completed'
    return
  }

  if (statuses.some((status) => status === 'running')) {
    state.overallStatus = 'running'
    return
  }

  state.overallStatus = 'idle'
}

const resetWorkflow = () => {
  const fresh = defaultState()
  stageOrder.forEach((key) => {
    state.stages[key] = fresh.stages[key]
  })
  state.overallStatus = fresh.overallStatus
  state.failedStage = fresh.failedStage
  state.ids = fresh.ids
  persist()
}

const setWorkflowIds = (ids = {}) => {
  state.ids = { ...state.ids, ...ids }
  persist()
}

const setWorkflowStage = (stageKey, patch = {}) => {
  if (!state.stages[stageKey]) return

  state.stages[stageKey] = {
    ...state.stages[stageKey],
    ...patch,
    labelKey: state.stages[stageKey].labelKey,
    updatedAt: patch.updatedAt || new Date().toISOString()
  }

  if (patch.status === 'failed') {
    state.failedStage = stageKey
  } else if (state.failedStage === stageKey && patch.status !== 'failed') {
    state.failedStage = null
  }

  updateOverallStatus()
  persist()
}

const clearFollowingStages = (stageKey) => {
  const startIndex = stageOrder.indexOf(stageKey)
  if (startIndex === -1) return

  stageOrder.slice(startIndex + 1).forEach((key) => {
    state.stages[key] = createStage(stageLabelKeys[key])
  })

  updateOverallStatus()
  persist()
}

const syncWorkflowFromProject = (project) => {
  if (!project) return

  setWorkflowIds({
    project_id: project.project_id,
    ontology_task_id: project.ontology_task_id || state.ids.ontology_task_id,
    graph_task_id: project.graph_build_task_id || state.ids.graph_task_id
  })

  switch (project.status) {
    case 'created':
      setWorkflowStage('upload', { status: 'completed', progress: 100, messageKey: 'workflow.messages.files_uploaded', message: '' })
      setWorkflowStage('ontology', { status: 'idle', progress: 0, messageKey: 'workflow.messages.waiting_analysis', message: '' })
      clearFollowingStages('ontology')
      break
    case 'ontology_generating':
      setWorkflowStage('upload', { status: 'completed', progress: 100, messageKey: 'workflow.messages.files_uploaded', message: '' })
      setWorkflowStage('ontology', {
        status: 'running',
        progress: state.stages.ontology.progress,
        messageKey: state.stages.ontology.message ? '' : 'workflow.messages.analyzing_documents',
        message: state.stages.ontology.message
      })
      clearFollowingStages('ontology')
      break
    case 'ontology_generated':
      setWorkflowStage('upload', { status: 'completed', progress: 100, messageKey: 'workflow.messages.files_uploaded', message: '' })
      setWorkflowStage('ontology', { status: 'completed', progress: 100, messageKey: 'workflow.messages.ontology_generated', message: '' })
      setWorkflowStage('graph_build', { status: 'idle', progress: 0, messageKey: 'workflow.messages.waiting_graph', message: '' })
      clearFollowingStages('graph_build')
      break
    case 'graph_building':
      setWorkflowStage('upload', { status: 'completed', progress: 100, messageKey: 'workflow.messages.files_uploaded', message: '' })
      setWorkflowStage('ontology', { status: 'completed', progress: 100, messageKey: 'workflow.messages.ontology_generated', message: '' })
      setWorkflowStage('graph_build', {
        status: 'running',
        progress: state.stages.graph_build.progress,
        messageKey: state.stages.graph_build.message ? '' : 'workflow.messages.building_graph',
        message: state.stages.graph_build.message
      })
      clearFollowingStages('graph_build')
      break
    case 'graph_completed':
      setWorkflowStage('upload', { status: 'completed', progress: 100, messageKey: 'workflow.messages.files_uploaded', message: '' })
      setWorkflowStage('ontology', { status: 'completed', progress: 100, messageKey: 'workflow.messages.ontology_generated', message: '' })
      setWorkflowStage('graph_build', { status: 'completed', progress: 100, messageKey: 'workflow.messages.graph_ready', message: '' })
      break
    case 'failed':
      setWorkflowStage('ontology', {
        status: 'failed',
        messageKey: project.error ? '' : 'workflow.messages.project_failed',
        message: project.error || ''
      })
      break
  }
}

const syncWorkflowFromSimulation = (simulation) => {
  if (!simulation) return

  setWorkflowIds({
    simulation_id: simulation.simulation_id,
    prepare_task_id: simulation.prepare_task_id || state.ids.prepare_task_id
  })

  if (simulation.status === 'preparing') {
    setWorkflowStage('simulation_prepare', {
      status: 'running',
      progress: state.stages.simulation_prepare.progress,
      messageKey: state.stages.simulation_prepare.message ? '' : 'workflow.messages.preparing_simulation',
      message: state.stages.simulation_prepare.message
    })
    clearFollowingStages('simulation_prepare')
    return
  }

  if (simulation.status === 'ready') {
    setWorkflowStage('simulation_prepare', {
      status: 'completed',
      progress: 100,
      messageKey: 'workflow.messages.simulation_ready',
      message: ''
    })
    setWorkflowStage('simulation_run', {
      status: 'idle',
      progress: 0,
      messageKey: 'workflow.messages.waiting_start',
      message: ''
    })
    clearFollowingStages('simulation_run')
    return
  }

  if (simulation.status === 'running') {
    setWorkflowStage('simulation_prepare', {
      status: 'completed',
      progress: 100,
      messageKey: 'workflow.messages.simulation_ready',
      message: ''
    })
    setWorkflowStage('simulation_run', {
      status: 'running',
      progress: state.stages.simulation_run.progress,
      messageKey: state.stages.simulation_run.message ? '' : 'workflow.messages.simulation_running',
      message: state.stages.simulation_run.message
    })
    clearFollowingStages('simulation_run')
    return
  }

  if (simulation.status === 'completed') {
    setWorkflowStage('simulation_prepare', {
      status: 'completed',
      progress: 100,
      messageKey: 'workflow.messages.simulation_ready',
      message: ''
    })
    setWorkflowStage('simulation_run', {
      status: 'completed',
      progress: 100,
      messageKey: 'workflow.messages.simulation_completed',
      message: ''
    })
    return
  }

  if (simulation.status === 'failed' || simulation.status === 'stopped') {
    setWorkflowStage('simulation_run', {
      status: 'failed',
      progress: state.stages.simulation_run.progress,
      messageKey: simulation.error ? '' : simulation.status === 'stopped' ? 'workflow.messages.simulation_stopped' : '',
      message: simulation.error || ''
    })
  }
}

const syncWorkflowFromReport = ({ reportId, taskId, status, progress, message }) => {
  setWorkflowIds({
    report_id: reportId || state.ids.report_id,
    report_task_id: taskId || state.ids.report_task_id
  })

  setWorkflowStage('report_generate', {
    status,
    progress,
    message
  })
}

export const workflowState = state
export {
  stageOrder,
  resetWorkflow,
  setWorkflowIds,
  setWorkflowStage,
  clearFollowingStages,
  syncWorkflowFromProject,
  syncWorkflowFromSimulation,
  syncWorkflowFromReport
}
