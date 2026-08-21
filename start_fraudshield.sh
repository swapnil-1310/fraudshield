#!/bin/bash
# FraudShield-SEBI Pro — Linux/Mac Launcher

echo "======================================================"
echo "  Starting FraudShield-SEBI Pro Unified Platform"
echo "  Dual Visual Deepfake & Audio SEBI Compliance System"
echo "======================================================"

# Start Backend
echo "Starting FastAPI Backend on port 8000..."
cd backend && python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd ..

# Start Frontend
echo "Starting React Frontend on port 3000..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Platform launched!"
echo "Backend API: http://127.0.0.1:8000"
echo "Frontend UI: http://localhost:3000"
echo "API Docs:    http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for both
wait $BACKEND_PID $FRONTEND_PID
