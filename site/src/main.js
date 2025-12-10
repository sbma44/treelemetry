import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import './style.css';
import config from './config.js';

// Register Chart.js components
Chart.register(...registerables);

// State
let chartInstance = null; // Real-time chart
let chart5m = null; // 5-minute aggregates chart
let chart1h = null; // 1-hour aggregates chart
let chartSegments = null; // Segments with extrema chart
let chartSlopes = null; // Slope trends chart
let allMeasurements = []; // All measurements from JSON
let displayedData = []; // Currently displayed data points
let aggregatedData = {
  agg_1m: null,
  agg_5m: null,
  agg_1h: null,
};
let analysisData = null; // Segment analysis data
let currentUnit = 'mm'; // 'mm' or 'mL'
let replayInterval = null;
let refreshInterval = null;
let countdownInterval = null;
let replayDelayMs = 300000; // 5 minutes in milliseconds
let predictedRefillTime = null; // Store predicted refill time

// DOM Elements
const elements = {
  loading: document.getElementById('loading'),
  error: document.getElementById('error'),
  mainContent: document.getElementById('main-content'),
  currentLevel: document.getElementById('current-level'),
  timeToRefill: document.getElementById('time-to-refill'),
  refillUnit: document.getElementById('refill-unit'),
  measurementFrequency: document.getElementById('measurement-frequency'),
  lastUpdateTime: document.getElementById('last-update-time'),
  dataWindow: document.getElementById('data-window'),
  canvas: document.getElementById('water-chart'),
  canvas5m: document.getElementById('chart-5m'),
  canvas1h: document.getElementById('chart-1h'),
  canvasSegments: document.getElementById('chart-segments'),
  canvasSlopes: document.getElementById('chart-slopes'),
};

/**
 * Convert mm to mL using the formula: mL = -25.125 * mm
 */
function mmToML(mm) {
  return -25.125 * mm;
}

/**
 * Convert mL to mm using the inverse formula: mm = mL / -25.125
 */
function mlToMM(ml) {
  return ml / -25.125;
}

/**
 * Convert value based on current unit
 */
function convertValue(mmValue) {
  if (currentUnit === 'mL') {
    return mmToML(mmValue);
  }
  return mmValue;
}

/**
 * Get the appropriate unit label
 */
function getUnitLabel() {
  return currentUnit;
}

/**
 * Get data for current view (real-time only)
 */
function getCurrentViewData() {
  return displayedData.map(m => ({
    x: new Date(m.timestamp),
    y: convertValue(m.water_level_mm),
    y_mm: m.water_level_mm, // Store original mm value
  }));
}

/**
 * Get chart title
 */
function getChartTitle() {
  return 'Last 10 Minutes (Real-time)';
}

/**
 * Fetch water level data from S3
 */
async function fetchData() {
  try {
    const response = await fetch(config.dataUrl, {
      cache: 'no-cache',
      headers: {
        'Cache-Control': 'no-cache',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Update replay delay from server
    if (data.replay_delay_seconds) {
      replayDelayMs = data.replay_delay_seconds * 1000;
    }

    // Store aggregated data if available
    if (data.agg_1m) {
      aggregatedData.agg_1m = data.agg_1m;
    }
    if (data.agg_5m) {
      aggregatedData.agg_5m = data.agg_5m;
    }
    if (data.agg_1h) {
      aggregatedData.agg_1h = data.agg_1h;
    }

    // Store analysis data if available
    if (data.analysis) {
      analysisData = data.analysis;
      console.log(`Analysis data loaded: ${analysisData.segments?.length || 0} segments`);
      if (data.analysis.current_prediction) {
        predictedRefillTime = new Date(data.analysis.current_prediction.predicted_refill_time);
        console.log(`Predicted refill time: ${predictedRefillTime.toISOString()}`);
      }
    } else {
      console.warn('No analysis data in JSON response');
    }

    return data;
  } catch (error) {
    console.error('Error fetching data:', error);
    throw error;
  }
}

/**
 * Create pulsing point plugin for Chart.js
 * Only applies to the real-time chart
 */
const pulsingPointPlugin = {
  id: 'pulsingPoint',
  afterDatasetsDraw(chart) {
    // Only apply to the real-time chart (water-chart canvas)
    if (chart.canvas.id !== 'water-chart') return;
    
    const ctx = chart.ctx;
    const meta = chart.getDatasetMeta(0);

    if (meta.data.length === 0) return;

    // Get the last point
    const lastPoint = meta.data[meta.data.length - 1];
    const x = lastPoint.x;
    const y = lastPoint.y;

    // Calculate pulse animation
    const now = Date.now();
    const phase = (now % config.pulseAnimationDuration) / config.pulseAnimationDuration;
    const radius = 8 + phase * 12; // Expands from 8 to 20
    const opacity = 1 - phase; // Fades out

    // Draw pulsing circle
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = `rgba(45, 212, 191, ${opacity * 0.6})`;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();

    // Request animation frame for continuous animation
    requestAnimationFrame(() => chart.update('none'));
  }
};

Chart.register(pulsingPointPlugin);

/**
 * Initialize the chart
 */
function initializeChart() {
  const ctx = elements.canvas.getContext('2d');

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Water Level',
          data: [],
          borderColor: '#2dd4bf',
          backgroundColor: 'rgba(45, 212, 191, 0.3)',
          borderWidth: 3,
          tension: 0.4,
          fill: {
            target: {value: 50},  // Fill from line down to bottom (50mm initially)
            above: 'rgba(45, 212, 191, 0.3)'
          },
          pointRadius: 5,
          pointHoverRadius: 7,
          pointBackgroundColor: '#2dd4bf',
          pointBorderColor: '#0f1419',
          pointBorderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        title: {
          display: false,  // Disabled - HTML has title
        },
        legend: {
          display: false,
        },
          tooltip: {
            backgroundColor: '#1a1f2e',
            titleColor: '#e5e7eb',
            bodyColor: '#9ca3af',
            borderColor: '#2d3748',
            borderWidth: 1,
            padding: 12,
            displayColors: false,
            callbacks: {
              label: function(context) {
                const unit = getUnitLabel();
                return `${context.parsed.y.toFixed(2)} ${unit}`;
              },
            },
          },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            displayFormats: {
              minute: 'HH:mm',
              hour: 'MMM d HH:mm',
              day: 'MMM d',
              second: 'HH:mm:ss',
            },
          },
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 12,
          },
        },
        y: {
          min: config.yAxisMin,
          max: config.yAxisMax,
          reverse: true, // Initial: 0 at top, 50 at bottom for mm
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            callback: function(value) {
              return value.toFixed(0) + ' ' + getUnitLabel();
            },
          },
          title: {
            display: true,
            text: '← Further from Sensor | Closer to Sensor →',
            color: '#9ca3af',
            font: {
              size: 11,
            },
          },
        },
      },
    },
  });
}

/**
 * Create a static aggregated chart (no pulsing effect)
 */
function createAggregatedChart(canvasElement, title) {
  const ctx = canvasElement.getContext('2d');

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Mean',
          data: [],
          borderColor: '#2dd4bf',
          backgroundColor: 'rgba(45, 212, 191, 0.3)',
          borderWidth: 3,
          tension: 0.4,
          fill: {
            target: {value: 50},
            above: 'rgba(45, 212, 191, 0.3)'
          },
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: '#2dd4bf',
          pointBorderColor: '#0f1419',
          pointBorderWidth: 2,
        },
        {
          label: 'Min',
          data: [],
          borderColor: '#818cf8',
          backgroundColor: 'rgba(129, 140, 248, 0.1)',
          borderWidth: 2,
          borderDash: [5, 5],
          tension: 0.4,
          fill: false,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
        {
          label: 'Max',
          data: [],
          borderColor: '#f472b6',
          backgroundColor: 'rgba(244, 114, 182, 0.1)',
          borderWidth: 2,
          borderDash: [5, 5],
          tension: 0.4,
          fill: false,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        title: {
          display: false,  // Disabled - HTML has title
        },
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: '#9ca3af',
            usePointStyle: true,
            padding: 15,
          },
        },
        tooltip: {
          backgroundColor: '#1a1f2e',
          titleColor: '#e5e7eb',
          bodyColor: '#9ca3af',
          borderColor: '#2d3748',
          borderWidth: 1,
          padding: 12,
          displayColors: true,
          callbacks: {
            label: function(context) {
              const unit = getUnitLabel();
              const label = context.dataset.label || '';
              return `${label}: ${context.parsed.y.toFixed(2)} ${unit}`;
            },
          },
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: title.includes('All Historical') || title.includes('24 Hours') ? 'day' : undefined,
            displayFormats: {
              minute: 'HH:mm',
              hour: 'HH:mm',
              day: 'M/d',
            },
          },
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 12,
          },
        },
        y: {
          min: 0,
          max: 50,
          reverse: true,
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            callback: function(value) {
              return value.toFixed(0) + ' ' + getUnitLabel();
            },
          },
          title: {
            display: true,
            text: '← Further from Sensor | Closer to Sensor →',
            color: '#9ca3af',
            font: {
              size: 11,
            },
          },
        },
      },
    },
    plugins: [], // No pulsing plugin for aggregated charts
  });
}

/**
 * Update aggregated chart with data
 */
function updateAggregatedChart(chartInstance, aggData) {
  if (!chartInstance || !aggData || !aggData.data) return;

  const data = aggData.data;

  // Convert timestamps and values
  const timestamps = data.map(d => new Date(d.t));
  const means = data.map(d => convertValue(d.m));
  const mins = data.map(d => convertValue(d.min));
  const maxs = data.map(d => convertValue(d.max));

  chartInstance.data.labels = timestamps;
  chartInstance.data.datasets[0].data = means;
  chartInstance.data.datasets[1].data = mins;
  chartInstance.data.datasets[2].data = maxs;

  // Update y-axis configuration
  const yAxis = chartInstance.options.scales.y;
  const datasets = chartInstance.data.datasets;

  if (currentUnit === 'mm') {
    yAxis.reverse = true;
    yAxis.min = 0;
    yAxis.max = 50;
    yAxis.title.text = '← Further from Sensor | Closer to Sensor →';
    datasets[0].fill = {
      target: {value: 50},
      above: 'rgba(45, 212, 191, 0.3)'
    };
  } else {
    yAxis.reverse = false;
    yAxis.min = -1300;
    yAxis.max = 0;
    yAxis.title.text = 'Water Volume';
    datasets[0].fill = {
      target: {value: -1300},
      above: 'rgba(45, 212, 191, 0.3)'
    };
  }

  chartInstance.update('none');
}

/**
 * Create segments chart with 1h data overlay
 */
function createSegmentsChart(canvasElement) {
  const ctx = canvasElement.getContext('2d');

  return new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        title: {
          display: false,  // Disabled - HTML has title
        },
        legend: {
          display: false,  // Suppress legend as it becomes messy with many segments
        },
        tooltip: {
          enabled: false,  // Disabled - too many overlapping datasets
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'day',
            displayFormats: {
              hour: 'M/d HH:mm',
              day: 'M/d',
            },
          },
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            maxRotation: 0,
            autoSkip: true,
          },
        },
        y: {
          min: 0,
          max: 50,
          reverse: true,
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            callback: function(value) {
              return value.toFixed(0) + ' ' + getUnitLabel();
            },
          },
          title: {
            display: true,
            text: '← Further from Sensor | Closer to Sensor →',
            color: '#9ca3af',
            font: {
              size: 11,
            },
          },
        },
      },
    }
  });
}

/**
 * Update segments chart with analysis data overlaid on 1h data
 */
function updateSegmentsChart() {
  if (!chartSegments) {
    console.warn('Segments chart not initialized');
    return;
  }
  if (!analysisData) {
    console.warn('No analysis data available for segments chart');
    return;
  }
  if (!aggregatedData.agg_1h) {
    console.warn('No 1h aggregated data available for segments chart');
    return;
  }

  // Get all 1h data points
  const allData = aggregatedData.agg_1h.data.map(d => ({
    x: new Date(d.t),
    y: convertValue(d.m)
  }));

  console.log(`Segments chart: ${allData.length} total 1h data points`);

  // Clear all existing datasets
  chartSegments.data.datasets = [];

  // For each segment, create a separate dataset with only its data points
  if (analysisData.segments && analysisData.segments.length > 0) {
    console.log(`Segments chart: Processing ${analysisData.segments.length} segments`);
    analysisData.segments.forEach((segment, idx) => {
      const startTime = new Date(segment.start_time).getTime();
      const endTime = new Date(segment.end_time).getTime();

      // Filter data points that fall within this segment
      const segmentData = allData.filter(point => {
        const time = point.x.getTime();
        return time >= startTime && time <= endTime;
      });

      console.log(`Segment ${segment.id}: ${segmentData.length} data points (${new Date(startTime).toISOString()} to ${new Date(endTime).toISOString()})`);

      // Add data series for this segment
      if (segmentData.length > 0) {
        chartSegments.data.datasets.push({
          label: `Segment ${segment.id} Data`,
          data: segmentData,
          borderColor: segment.is_current ? '#2dd4bf' : 'rgba(45, 212, 191, 0.8)',
          backgroundColor: 'rgba(45, 212, 191, 0.3)',
          borderWidth: segment.is_current ? 3 : 2,
          tension: 0.4,
          fill: false,
          pointRadius: 3,
          pointHoverRadius: 5,
          showLine: true,
          order: 2,  // Behind markers
        });
      } else {
        console.warn(`Segment ${segment.id}: No data points found in range!`);
      }

      // Add segment fit line
      const startVal = convertValue(segment.start_distance_mm);
      const endVal = convertValue(segment.end_distance_mm);

      chartSegments.data.datasets.push({
        label: `Segment ${segment.id} Fit`,
        data: [
          { x: new Date(segment.start_time), y: startVal },
          { x: new Date(segment.end_time), y: endVal }
        ],
        borderColor: '#f472b6',  // Pink solid bars for all segments
        backgroundColor: 'transparent',
        borderWidth: segment.is_current ? 3 : 2,  // Slightly thicker for current
        pointRadius: 0,
        showLine: true,
        tension: 0,
        borderDash: [],  // Solid for all segments
        order: 1,  // Above data, below markers
      });
    });

    console.log(`Segments chart: Total datasets after update: ${chartSegments.data.datasets.length}`);
  } else {
    console.warn('No segments to display');
  }

  // Update y-axis configuration
  const yAxis = chartSegments.options.scales.y;
  if (currentUnit === 'mm') {
    yAxis.reverse = true;
    yAxis.min = 0;
    yAxis.max = 50;
    yAxis.title.text = '← Further from Sensor | Closer to Sensor →';
  } else {
    yAxis.reverse = false;
    yAxis.min = -1300;
    yAxis.max = 0;
    yAxis.title.text = 'Water Volume';
  }

  chartSegments.update('none');
}

/**
 * Create slope trends chart
 */
function createSlopesChart(canvasElement) {
  const ctx = canvasElement.getContext('2d');

  return new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [{
        label: 'Consumption Rate',
        data: [],
        borderColor: '#818cf8',
        backgroundColor: 'rgba(129, 140, 248, 0.3)',
        borderWidth: 3,
        tension: 0.4,
        fill: false,
        pointRadius: 5,
        pointHoverRadius: 7,
        pointBackgroundColor: '#818cf8',
        pointBorderColor: '#0f1419',
        pointBorderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        title: {
          display: false,  // Disabled - HTML has title
        },
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: '#1a1f2e',
          titleColor: '#e5e7eb',
          bodyColor: '#9ca3af',
          borderColor: '#2d3748',
          borderWidth: 1,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return `${context.parsed.y.toFixed(3)} mm/hour`;
            },
          },
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'day',
            displayFormats: {
              hour: 'M/d HH:mm',
              day: 'M/d',
            },
          },
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            maxRotation: 0,
            autoSkip: true,
          },
        },
        y: {
          min: 0,
          grid: {
            color: '#2d3748',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            callback: function(value) {
              return value.toFixed(1) + ' mm/h';
            },
          },
          title: {
            display: true,
            text: 'Consumption Rate (mm/hour)',
            color: '#9ca3af',
            font: {
              size: 12,
            },
          },
        },
      },
    },
  });
}

/**
 * Update slopes chart with analysis data
 */
function updateSlopesChart() {
  if (!chartSlopes) {
    console.warn('Slopes chart not initialized');
    return;
  }
  if (!analysisData) {
    console.warn('No analysis data available for slopes chart');
    return;
  }
  if (!analysisData.segments || analysisData.segments.length === 0) {
    console.warn('No segments available for slopes chart');
    return;
  }

  // Get midpoint times and slopes for each segment
  const slopeData = analysisData.segments.map(segment => {
    const startTime = new Date(segment.start_time);
    const endTime = new Date(segment.end_time);
    const midTime = new Date((startTime.getTime() + endTime.getTime()) / 2);

    return {
      x: midTime,
      y: segment.slope_mm_per_hr
    };
  });

  console.log(`Updating slopes chart with ${slopeData.length} data points`);
  chartSlopes.data.datasets[0].data = slopeData;
  chartSlopes.update('none');
}

/**
 * Synchronize x-axis range across historical charts
 */
function synchronizeHistoricalChartRanges() {
  // Collect all timestamps from relevant data sources
  let allTimestamps = [];

  // Get timestamps from 1h aggregated data
  if (aggregatedData.agg_1h && aggregatedData.agg_1h.data) {
    const timestamps = aggregatedData.agg_1h.data.map(d => new Date(d.t).getTime());
    allTimestamps.push(...timestamps);
  }

  // Get timestamps from segments
  if (analysisData && analysisData.segments) {
    analysisData.segments.forEach(seg => {
      allTimestamps.push(new Date(seg.start_time).getTime());
      allTimestamps.push(new Date(seg.end_time).getTime());
    });
  }

  if (allTimestamps.length === 0) {
    return; // No data to synchronize
  }

  // Calculate min and max with some padding
  const minTime = Math.min(...allTimestamps);
  const maxTime = Math.max(...allTimestamps);
  const padding = (maxTime - minTime) * 0.02; // 2% padding on each side

  const xMin = new Date(minTime - padding);
  const xMax = new Date(maxTime + padding);

  // Apply to all three charts
  if (chart1h && chart1h.options && chart1h.options.scales && chart1h.options.scales.x) {
    chart1h.options.scales.x.min = xMin;
    chart1h.options.scales.x.max = xMax;
    chart1h.update('none'); // Update without animation
  }

  if (chartSegments && chartSegments.options && chartSegments.options.scales && chartSegments.options.scales.x) {
    chartSegments.options.scales.x.min = xMin;
    chartSegments.options.scales.x.max = xMax;
    chartSegments.update('none'); // Update without animation
  }

  if (chartSlopes && chartSlopes.options && chartSlopes.options.scales && chartSlopes.options.scales.x) {
    chartSlopes.options.scales.x.min = xMin;
    chartSlopes.options.scales.x.max = xMax;
    chartSlopes.update('none'); // Update without animation
  }

  console.log(`Synchronized chart x-axes: ${xMin.toISOString()} to ${xMax.toISOString()}`);
}

/**
 * Update countdown timer for refill in HH:MM:SS format
 */
function updateCountdown() {
  if (!predictedRefillTime || !elements.timeToRefill) {
    elements.timeToRefill.textContent = '--:--:--';
    elements.refillUnit.textContent = '';
    return;
  }

  const now = new Date();
  const msRemaining = predictedRefillTime - now;

  if (msRemaining <= 0) {
    elements.timeToRefill.textContent = '00:00:00';
    elements.refillUnit.textContent = '(refill now!)';
    return;
  }

  // Calculate total hours, minutes, seconds
  const totalSeconds = Math.floor(msRemaining / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  // Format as HH:MM:SS with zero padding
  const hoursStr = String(hours).padStart(2, '0');
  const minutesStr = String(minutes).padStart(2, '0');
  const secondsStr = String(seconds).padStart(2, '0');

  elements.timeToRefill.textContent = `${hoursStr}:${minutesStr}:${secondsStr}`;
  elements.refillUnit.textContent = '';
}

/**
 * Start countdown timer
 */
function startCountdown() {
  if (countdownInterval) {
    clearInterval(countdownInterval);
  }

  console.log('Starting countdown timer');
  updateCountdown();
  countdownInterval = setInterval(updateCountdown, 1000);
}

/**
 * Calculate measurement frequency over the last 60 seconds of rendered data
 */
function calculateMeasurementFrequency() {
  if (displayedData.length < 2) {
    return 0;
  }

  // Get the last timestamp
  const lastTimestamp = new Date(displayedData[displayedData.length - 1].timestamp);
  const cutoffTime = new Date(lastTimestamp.getTime() - 60000); // 60 seconds ago

  // Count measurements in the last 60 seconds
  const recentMeasurements = displayedData.filter(m => {
    const timestamp = new Date(m.timestamp);
    return timestamp >= cutoffTime;
  });

  if (recentMeasurements.length < 2) {
    return 0;
  }

  // Calculate the actual time span of the recent measurements
  const firstTimestamp = new Date(recentMeasurements[0].timestamp);
  const lastTimestamp2 = new Date(recentMeasurements[recentMeasurements.length - 1].timestamp);
  const timeSpanSeconds = (lastTimestamp2 - firstTimestamp) / 1000;

  if (timeSpanSeconds === 0) {
    return 0;
  }

  // Frequency = measurements / time span in seconds
  return recentMeasurements.length / timeSpanSeconds;
}

/**
 * Update stats display
 */
function updateStats(data) {
  const stats = data?.stats || {};

  if (displayedData.length > 0) {
    const latest = displayedData[displayedData.length - 1];
    const value = convertValue(latest.water_level_mm);
    elements.currentLevel.textContent = value?.toFixed(2) || '--';
  }

  // Update unit labels in stat cards (only first one shows water level)
  const firstStatUnit = document.querySelector('.stat-unit');
  if (firstStatUnit) {
    firstStatUnit.textContent = getUnitLabel();
  }

  // Update measurement frequency (Hz)
  const frequency = calculateMeasurementFrequency();
  elements.measurementFrequency.textContent = frequency.toFixed(2);

  // Note: Countdown timer updates independently via setInterval

  // Update info section
  const now = new Date();
  elements.lastUpdateTime.textContent = now.toLocaleString();

  // Show data window info
  const shouldBeVisible = allMeasurements.filter(m => {
    const timestamp = new Date(m.timestamp);
    const ageMs = Date.now() - timestamp.getTime();
    return ageMs >= replayDelayMs;
  }).length;

  // not used
//   const windowInfo = `${displayedData.length} of ${shouldBeVisible} points (${allMeasurements.length} total)`;
//   elements.dataWindow.textContent = windowInfo;
}

/**
 * Update chart with currently displayed data
 */
function updateChart() {
  if (!chartInstance) return;

  const viewData = getCurrentViewData();

  chartInstance.data.labels = viewData.map(d => d.x);
  chartInstance.data.datasets[0].data = viewData.map(d => d.y);

  // Update chart title
  chartInstance.options.plugins.title.text = getChartTitle();

  // Update y-axis configuration based on unit
  updateYAxisConfig();

  // Smooth update without animation
  chartInstance.update('none');
}

/**
 * Update Y-axis configuration based on current unit
 */
function updateYAxisConfig() {
  if (!chartInstance) return;

  const yAxis = chartInstance.options.scales.y;
  const dataset = chartInstance.data.datasets[0];

  if (currentUnit === 'mm') {
    // For mm: reverse axis (0 at top, 50 at bottom) to show distance from sensor
    yAxis.reverse = true;
    yAxis.min = 0;
    yAxis.max = 50;
    yAxis.title.text = '← Further from Sensor | Closer to Sensor →';
    // Fill from line to bottom (50mm)
    dataset.fill = {
      target: {value: 50},
      above: 'rgba(45, 212, 191, 0.3)'
    };
  } else {
    // For mL: normal axis (-1300 at bottom, 0 at top) to show water volume
    yAxis.reverse = false;
    yAxis.min = -1300;
    yAxis.max = 0;
    yAxis.title.text = 'Water Volume';
    // Fill from line to bottom (-1300mL)
    dataset.fill = {
      target: {value: -1300},
      above: 'rgba(45, 212, 191, 0.3)'
    };
  }
}

/**
 * Switch between different units (mm/mL)
 */
function switchUnit(newUnit) {
  currentUnit = newUnit;

  // Update button states
  document.querySelectorAll('.units-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.unit === newUnit) {
      btn.classList.add('active');
    }
  });

  // Update all charts and stats
  updateChart();
  if (chart5m && aggregatedData.agg_5m) {
    updateAggregatedChart(chart5m, aggregatedData.agg_5m);
  }
  if (chart1h && aggregatedData.agg_1h) {
    updateAggregatedChart(chart1h, aggregatedData.agg_1h);
  }
  if (chartSegments && analysisData) {
    updateSegmentsChart();
  }
  // Slopes chart doesn't need updating for unit changes
  updateStats({});
}

/**
 * Check if any measurements should now be visible based on replay delay
 */
function updateVisibleData() {
  const now = Date.now();
  let updated = false;

  // Find measurements that are now old enough to display
  for (const measurement of allMeasurements) {
    const timestamp = new Date(measurement.timestamp).getTime();
    const ageMs = now - timestamp;

    // If this measurement is old enough and not already displayed
    if (ageMs >= replayDelayMs && !displayedData.includes(measurement)) {
      displayedData.push(measurement);
      updated = true;
    }
  }

  // Keep displayed data sorted by timestamp
  if (updated) {
    displayedData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Keep only last 500 points for performance
    if (displayedData.length > 500) {
      displayedData = displayedData.slice(-500);
    }

    updateChart();
    updateStats({});
  }
}

/**
 * Start the replay timer
 */
function startReplay() {
  // Check every second for new data to reveal
  replayInterval = setInterval(() => {
    updateVisibleData();
  }, 1000);
}

/**
 * Refresh data from server and merge with existing
 */
async function refreshData() {
  try {
    const data = await fetchData();
    const measurements = data.measurements || [];

    if (measurements.length === 0) {
      console.warn('No measurements in fetched data');
      return;
    }

    // Merge new measurements with existing ones
    const existingTimestamps = new Set(allMeasurements.map(m => m.timestamp));
    const newMeasurements = measurements.filter(m => !existingTimestamps.has(m.timestamp));

    if (newMeasurements.length > 0) {
      console.log(`Added ${newMeasurements.length} new measurements`);
      allMeasurements.push(...newMeasurements);

      // Sort by timestamp
      allMeasurements.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

      // Immediately check if any should be visible
      updateVisibleData();
    }

    // Update aggregated charts with fresh data
    if (chart5m && aggregatedData.agg_5m) {
      updateAggregatedChart(chart5m, aggregatedData.agg_5m);
    }
    if (chart1h && aggregatedData.agg_1h) {
      updateAggregatedChart(chart1h, aggregatedData.agg_1h);
    }

    // Update analysis charts if new data available
    if (analysisData) {
      if (chartSegments) {
        updateSegmentsChart();
      }
      if (chartSlopes) {
        updateSlopesChart();
      }
      // Restart countdown timer if prediction time was updated
      if (predictedRefillTime && !countdownInterval) {
        startCountdown();
      }
    }

    // Synchronize x-axis ranges across historical charts
    synchronizeHistoricalChartRanges();

  } catch (error) {
    console.error('Failed to refresh data:', error);
  }
}

/**
 * Initial load and display
 */
async function loadData() {
  try {
    elements.loading.style.display = 'block';
    elements.error.style.display = 'none';
    elements.mainContent.style.display = 'none';

    const data = await fetchData();
    const measurements = data.measurements || [];

    if (measurements.length === 0) {
      throw new Error('No measurements available');
    }

    // Initialize charts if not already done
    if (!chartInstance) {
      initializeChart();
    }
    if (!chart5m && elements.canvas5m) {
      chart5m = createAggregatedChart(elements.canvas5m, 'Last 24 Hours');
    }
    if (!chart1h && elements.canvas1h) {
      chart1h = createAggregatedChart(elements.canvas1h, 'All Historical Data');
    }
    if (!chartSegments && elements.canvasSegments) {
      console.log('Initializing segments chart');
      chartSegments = createSegmentsChart(elements.canvasSegments);
    }
    if (!chartSlopes && elements.canvasSlopes) {
      console.log('Initializing slopes chart');
      chartSlopes = createSlopesChart(elements.canvasSlopes);
    }

    // Store all measurements
    allMeasurements = measurements.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    displayedData = [];

    // Immediately show all data older than replay delay
    const now = Date.now();
    for (const measurement of allMeasurements) {
      const timestamp = new Date(measurement.timestamp).getTime();
      const ageMs = now - timestamp;

      if (ageMs >= replayDelayMs) {
        displayedData.push(measurement);
      }
    }

    console.log(`Showing ${displayedData.length} of ${allMeasurements.length} measurements immediately`);

    // Update real-time chart
    updateChart();

    // Update aggregated charts
    if (chart5m && aggregatedData.agg_5m) {
      updateAggregatedChart(chart5m, aggregatedData.agg_5m);
      console.log(`5-minute aggregates: ${aggregatedData.agg_5m.data.length} points`);
    }
    if (chart1h && aggregatedData.agg_1h) {
      updateAggregatedChart(chart1h, aggregatedData.agg_1h);
      console.log(`1-hour aggregates: ${aggregatedData.agg_1h.data.length} points`);
    }

    // Update analysis charts
    if (analysisData) {
      console.log('Updating analysis charts with data');
      if (chartSegments) {
        updateSegmentsChart();
        console.log(`Segments chart: ${analysisData.segments?.length || 0} segments`);
      } else {
        console.warn('Segments chart not initialized');
      }
      if (chartSlopes) {
        updateSlopesChart();
      } else {
        console.warn('Slopes chart not initialized');
      }
    } else {
      console.warn('No analysis data available to update charts');
    }

    // Synchronize x-axis ranges across historical charts
    synchronizeHistoricalChartRanges();

    updateStats(data);

    // Start countdown timer
    if (predictedRefillTime) {
      startCountdown();
    }

    // Show main content
    elements.loading.style.display = 'none';
    elements.mainContent.style.display = 'block';

    // Start the replay timer
    if (!replayInterval) {
      startReplay();
    }

    // Set up periodic data refresh
    if (!refreshInterval) {
      refreshInterval = setInterval(refreshData, config.dataRefreshInterval);
    }

  } catch (error) {
    console.error('Failed to load data:', error);
    elements.loading.style.display = 'none';
    elements.error.style.display = 'block';
  }
}

/**
 * Initialize app
 */
function init() {
  // Set up units toggle buttons
  document.querySelectorAll('.units-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchUnit(btn.dataset.unit);
    });
  });

  // Initial load
  loadData();
}

// Start the app
init();

