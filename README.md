# BoutiqueOS MVP

Working local MVP for independent clothing boutiques.

## Stack
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy 2.x + Pydantic v2
- Database: SQLite (schema structured for future PostgreSQL migration)

## Features in this MVP
- Dashboard metrics
- Catalog and inventory list
- Unique piece holds with expiry
- Customer creation
- Manual order creation
- Tailoring stage updates
- Seed/demo data on startup

## Seed Data
Auto-seeded on backend startup if missing:
- Merchant: Meera Boutique
- Customers: Anjali Rao, Priya Sharma, Neha Reddy
- Items:
  - Hand Embroidered Bridal Lehenga (UNIQUE)
  - Chanderi Fabric Roll (YARDAGE 22.5)
  - Cotton Kurta - Blue (STOCKED 8)
  - Kanjeevaram Saree (UNIQUE)
  - Designer Blouse (STOCKED 5)

## Backend (Windows)
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run tests:
```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

## Frontend (Windows)
```powershell
cd frontend
npm install
npm run dev
```

Production build:
```powershell
cd frontend
npm run build
```

## Environment Files
- backend/.env.example
- frontend/.env.example

Frontend API base defaults to `http://localhost:8000`.
