// Configuration
export default {
  // Y-axis range (distance from sensor in mm)
  yAxisMin: 0,   // Closest to sensor (top of chart)
  yAxisMax: 50,  // Farthest from sensor (bottom of chart)
  
  // Data refresh settings
  dataRefreshInterval: 30000, // 30 seconds - fetch new JSON
  replayInterval: 1000,        // 1 second - add next point from buffer
  
  // Visual settings
  pulseAnimationDuration: 2000, // 2 seconds for pulse cycle
  
  // Data URL
  dataUrl: 'https://treelemetry-sbma44-water-data.s3.amazonaws.com/water-level.json',
};

