# DataLens — CSV Analysis Tool

## Status: DONE

### What It Is
A FastAPI web app where you upload a CSV and get auto-generated statistical analysis and charts. Aimed at non-technical users who want quick insights from spreadsheet data.

### Tech Stack
Python, FastAPI, pandas, matplotlib, seaborn, Docker

### Features
- CSV upload and parsing
- Automatic data type detection
- Descriptive statistics (mean, median, std, quartiles)
- Auto-generated charts (histograms, scatter plots, correlation heatmaps)
- Summary report generation
- Deployed on Railway

### What I Learned
- FastAPI is clean and fast to build with
- pandas can handle most data tasks but memory usage gets tricky with large files
- matplotlib's API is painful — seaborn is better for quick charts
- Docker deployment was straightforward once I figured out the Dockerfile

### Timeline
- Started: August 2026
- Shipped: September 2026

### Repository
github.com/arjunmehta/datalens
