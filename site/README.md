# Treelemetry Static Site

Vite-powered visualization dashboard for Christmas tree water levels.

## Overview

The static site is the visualization layer of the Treelemetry pipeline:

```
MQTT Logger → DuckDB → Uploader → S3 → Static Site (this)
```

It fetches aggregated data from S3 (updated every 30 seconds by the uploader) and displays:
- Real-time water level charts
- Multi-scale aggregations (1m, 5m, 1h intervals)
- Consumption rate analysis
- Refill predictions

## Setup

Install dependencies:

```bash
npm install
```

## Configuration

The site is pre-configured to use the bucket: `treelemetry-sbma44-water-data`

No configuration changes needed unless you want to use a different bucket.

## Development

Start the development server:

```bash
npm run dev
```

The site will open at `http://localhost:3000`.

## Build

Build for production (outputs to `../docs/` for GitHub Pages):

```bash
npm run build
```

## Preview Production Build

Preview the production build locally:

```bash
npm run preview
```

## GitHub Pages Deployment

The production build outputs to the `docs/` directory, which can be served by GitHub Pages:

1. Build the site: `npm run build`
2. Commit the `docs/` directory
3. Push to GitHub
4. Enable GitHub Pages in repository settings (Settings → Pages)
5. Set source to "Deploy from a branch"
6. Select `main` branch and `/docs` folder
7. Site will be available at: `https://treelemetry.tomlee.space`

## Features

### Real-time Visualization

- Line chart showing water level over time
- Animated replay with play/pause controls
- Smooth transitions and hover interactions

### Statistics Cards

- Current water level
- Current temperature
- Average level
- Total measurements

### Auto-refresh

The site automatically refreshes data every 30 seconds to show the latest measurements.

## Technologies

- **Vite**: Fast build tool and dev server
- **Chart.js**: Modern, responsive charting library
- **Vanilla JavaScript**: No framework overhead
- **CSS Custom Properties**: Theming and design system

