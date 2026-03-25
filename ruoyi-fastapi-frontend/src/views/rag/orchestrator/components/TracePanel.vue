<template>
  <el-card class="trace-panel" shadow="hover">
    <template #header>
      <div class="trace-header">
        <span>{{ title }}</span>
        <el-tag size="small" effect="plain">{{ timelineItems.length }} 步</el-tag>
      </div>
    </template>

    <el-empty v-if="timelineItems.length === 0" description="暂无执行轨迹" :image-size="72" />

    <template v-else>
      <el-timeline>
        <el-timeline-item
          v-for="item in timelineItems"
          :key="item.stepKey"
          :type="timelineTypeMap[item.status] || 'info'"
          :timestamp="formatTime(item.startTime)"
          placement="top"
        >
          <div class="timeline-card">
            <div class="timeline-main">
              <div class="timeline-title">
                <span>{{ item.stepLabel }}</span>
                <el-tag size="small" :type="timelineTypeMap[item.status] || 'info'" effect="light">
                  {{ statusTextMap[item.status] || item.status }}
                </el-tag>
              </div>
              <div v-if="item.summary" class="timeline-summary">{{ item.summary }}</div>
              <div class="timeline-meta">
                <span v-if="item.latencyMs !== null && item.latencyMs !== undefined">耗时 {{ item.latencyMs }} ms</span>
                <span v-if="item.endTime">完成于 {{ formatTime(item.endTime) }}</span>
              </div>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>

      <el-collapse v-model="activePanels" class="trace-collapse">
        <el-collapse-item title="耗时瀑布图" name="waterfall">
          <div ref="chartRef" class="trace-chart" />
        </el-collapse-item>
      </el-collapse>
    </template>
  </el-card>
</template>

<script setup name="TracePanel">
import * as echarts from 'echarts'

const props = defineProps({
  traceEvents: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: '执行轨迹'
  }
})

const STEP_ORDER = ['request.accepted', 'rag.retrieve', 'rag.query', 'response.finalized']

const timelineTypeMap = {
  started: 'warning',
  success: 'success',
  failed: 'danger'
}

const statusTextMap = {
  started: '进行中',
  success: '成功',
  failed: '失败'
}

const activePanels = ref(['waterfall'])
const chartRef = ref(null)
const chartInstance = shallowRef(null)

const timelineItems = computed(() => {
  const latestMap = new Map()
  ;(props.traceEvents || []).forEach(event => {
    latestMap.set(event.stepKey, event)
  })
  return STEP_ORDER.map(stepKey => latestMap.get(stepKey)).filter(Boolean)
})

const waterfallItems = computed(() => {
  return timelineItems.value
    .filter(item => item.status !== 'started')
    .map(item => ({
      name: item.stepLabel,
      value: item.latencyMs || 0,
      status: item.status
    }))
})

function formatTime(value) {
  if (!value) {
    return '--'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function getBarColor(status) {
  if (status === 'failed') {
    return '#f56c6c'
  }
  if (status === 'success') {
    return '#67c23a'
  }
  return '#e6a23c'
}

function renderChart() {
  if (!chartRef.value) {
    return
  }

  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }

  if (waterfallItems.value.length === 0) {
    chartInstance.value.clear()
    return
  }

  const items = waterfallItems.value.slice().reverse()
  chartInstance.value.setOption({
    grid: {
      left: 90,
      right: 24,
      top: 18,
      bottom: 18
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter(params) {
        const current = params?.[0]
        if (!current) {
          return ''
        }
        return `${current.name}<br/>耗时: ${current.value} ms`
      }
    },
    xAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value} ms'
      }
    },
    yAxis: {
      type: 'category',
      data: items.map(item => item.name)
    },
    series: [
      {
        type: 'bar',
        data: items.map(item => ({
          value: item.value,
          itemStyle: {
            color: getBarColor(item.status),
            borderRadius: [0, 4, 4, 0]
          }
        })),
        barWidth: 18
      }
    ]
  })
}

function resizeChart() {
  chartInstance.value?.resize()
}

watch(
  () => props.traceEvents,
  () => {
    nextTick(() => {
      renderChart()
    })
  },
  { deep: true, immediate: true }
)

onMounted(() => {
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance.value?.dispose()
  chartInstance.value = null
})
</script>

<style scoped>
.trace-panel {
  min-height: 100%;
}

.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.timeline-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #ffffff 0%, #f7fafc 100%);
}

.timeline-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
}

.timeline-summary {
  margin-top: 8px;
  color: #303133;
  line-height: 1.6;
}

.timeline-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #909399;
  font-size: 12px;
}

.trace-collapse {
  margin-top: 16px;
}

.trace-chart {
  height: 260px;
}
</style>
