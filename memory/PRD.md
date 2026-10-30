# PRD — Enterprise-Scale Synthetic ESG Data Generator ("ESG Data Forge")

## Original problem statement (summary)
Generate a realistic, interconnected, enterprise-scale synthetic data ecosystem for a fictional multinational diversified industrial enterprise (2022-01-01 → 2026-12-31): ERP (GL/AP/AR/procurement/inventory/production/assets/utilities), CRM, supplier management, MES, SCADA/IoT, HRMS, logistics, legacy IT (DAT/EDI/XML/logs), databases (DDL/exports/CDC), REST/XML APIs, file systems, real documents (PDF/DOCX/XLSX/EML/TXT/MD/LOG/CSV/JSON/XML/DAT), GHG Scope 1/2 (location + market)/3 (all 15 categories), ~10k SYNTHETIC emission factors, ESG (env/social/governance), decarbonisation opportunities, carbon credits, hidden anomaly ground truth with train/val/test splits, lineage, data dictionary, validation reports, dataset index. Deterministic, resumable batches; never silently reduce volumes.

## User choices
- Web dashboard + downloadable files (files also on server)
- Medium scale (10% of transaction targets; master data at full size)
- A few thousand documents (3,000 requested → ~3,540 generated)

## Architecture
- Generator package `/app/backend/generator/` (numpy/pandas, pyarrow, reportlab, python-docx, openpyxl)
  - core (Ctx, registry, anomaly recorder, lineage), master, ef, erp, ops, finance, ghg, esg, legacy, docs, finalize, runner (14 dependency-ordered batches B01–B14, manifest checkpoints, resume, SIGTERM pause)
- Output: `/app/data/Enterprise_ESG_Synthetic_Data/` (DATA_ROOT in backend/.env), ~390 MB, ~3,800 files, 109 datasets, ~5.9M records
- FastAPI `/api/*`: generate/stop/status, index, preview, validation, anomalies (+summary, clearance flag), ghg/summary, documents, tree, files/download, export (ZIP raw or with ground truth)
- React dashboard (dark command-center): Overview, Generator, Datasets, Validation, Ground truth, Documents, Export
- MongoDB: generation run history

## Implemented (2026-06)
- Full B01–B14 pipeline; run time ~100 s at 10% scale; 37k labelled anomalies across 6 families; held-out subtypes only in test split
- Validation: PK/FK/business rules/label leakage/GT reference checks; enterprise status VALIDATED
- Testing agent iteration 1: backend 22/22, frontend 100%; fixed path traversal, atomic ZIP export, preview offset, split order, raw export excludes label-revealing reports, mobile overflow, GT search debounce, docs empty state

## Backlog
- P1: Full-target (scale 1.0) run as multi-session resumable batches with disk-space guard
- P1: Per-batch configurable anomaly rates via UI
- P2: Parquet partitioning by year for very large tables; Excel workbook with live cross-sheet links; supplier-level PCF comparison views
