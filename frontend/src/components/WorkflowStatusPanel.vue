<template>
  <aside class="workflow-panel">
    <div class="workflow-panel-header">
      <span class="panel-title">{{ $t('workflow.panel_title') }}</span>
      <span class="panel-pill" :class="`panel-pill--${overallStatus}`">{{ overallLabel }}</span>
    </div>

    <div class="workflow-stage-list">
      <div
        v-for="stage in stageItems"
        :key="stage.key"
        class="workflow-stage"
        :class="`workflow-stage--${stage.status}`"
      >
        <div class="stage-row">
          <div class="stage-label-group">
            <span class="stage-dot"></span>
            <span class="stage-label">{{ resolveLabel(stage) }}</span>
          </div>
          <span class="stage-progress mono">{{ stage.progress }}%</span>
        </div>

        <div class="stage-bar">
          <div class="stage-fill" :style="{ width: `${stage.progress}%` }"></div>
        </div>

        <div class="stage-meta">
          <span class="stage-message">{{ resolveMessage(stage) }}</span>
          <span class="stage-time mono">{{ formatTime(stage.updatedAt) }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { stageOrder, workflowState } from '../store/workflow'

const { t } = useI18n()

const stageItems = computed(() => stageOrder.map((key) => ({
  key,
  ...workflowState.stages[key]
})))

const overallStatus = computed(() => workflowState.overallStatus)
const overallLabel = computed(() => {
  if (overallStatus.value === 'completed') return t('workflow.overall.completed')
  if (overallStatus.value === 'failed') return t('workflow.overall.failed')
  if (overallStatus.value === 'running') return t('workflow.overall.running')
  return t('workflow.overall.idle')
})

const fallbackMessage = (status) => {
  if (status === 'completed') return t('workflow.messages.completed')
  if (status === 'running') return t('workflow.messages.running')
  if (status === 'failed') return t('workflow.messages.failed')
  return t('workflow.messages.waiting')
}

const resolveLabel = (stage) => t(stage.labelKey)

const resolveMessage = (stage) => {
  if (stage.message) return stage.message
  if (stage.messageKey) return t(stage.messageKey)
  return fallbackMessage(stage.status)
}

const formatTime = (value) => {
  if (!value) return '--:--:--'
  try {
    return new Date(value).toLocaleTimeString('ja-JP', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return '--:--:--'
  }
}
</script>

<style scoped>
.workflow-panel {
  padding: 14px 16px;
  border-bottom: 1px solid #eaeaea;
  background: linear-gradient(180deg, #ffffff 0%, #fcfcfc 100%);
}

.workflow-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #666;
}

.panel-pill {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.panel-pill--idle {
  background: #f3f4f6;
  color: #6b7280;
}

.panel-pill--running {
  background: #fff4ed;
  color: #c2410c;
}

.panel-pill--completed {
  background: #ecfdf3;
  color: #027a48;
}

.panel-pill--failed {
  background: #fef2f2;
  color: #b42318;
}

.workflow-stage-list {
  display: grid;
  gap: 10px;
}

.workflow-stage {
  padding: 10px 12px;
  border: 1px solid #ececec;
  border-radius: 8px;
  background: #fff;
}

.stage-row,
.stage-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stage-label-group {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d1d5db;
  flex: none;
}

.workflow-stage--running .stage-dot {
  background: #f97316;
}

.workflow-stage--completed .stage-dot {
  background: #16a34a;
}

.workflow-stage--failed .stage-dot {
  background: #dc2626;
}

.stage-label,
.stage-message {
  min-width: 0;
  word-break: break-word;
}

.stage-label {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

.mono,
.stage-progress,
.stage-time {
  font-family: 'JetBrains Mono', monospace;
}

.stage-progress,
.stage-time {
  font-size: 11px;
  color: #6b7280;
  flex: none;
}

.stage-bar {
  height: 6px;
  margin: 8px 0 6px;
  border-radius: 999px;
  background: #f3f4f6;
  overflow: hidden;
}

.stage-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ff6a3d 0%, #ff9a3d 100%);
  transition: width 0.25s ease;
}

.workflow-stage--completed .stage-fill {
  background: linear-gradient(90deg, #12b76a 0%, #16a34a 100%);
}

.workflow-stage--failed .stage-fill {
  background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
}

.stage-message {
  font-size: 12px;
  color: #4b5563;
  line-height: 1.5;
  flex: 1;
}

@media (max-width: 960px) {
  .workflow-panel {
    padding: 12px;
  }

  .stage-row,
  .stage-meta {
    align-items: flex-start;
  }
}
</style>
