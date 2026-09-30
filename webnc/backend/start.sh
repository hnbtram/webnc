#!/bin/bash
set -e

echo "🚀 AI Web Apps — Render Startup"
echo "   PORT=$PORT"
echo "   PWD=$(pwd)"
echo "   Python: $(python --version)"

# Liệt kê thư mục để debug
echo "📁 Nội dung thư mục hiện tại:"
ls -la

echo "📁 Kiểm tra artifacts:"
ls -la artifacts/ 2>/dev/null || echo "   ⚠️ artifacts/ chưa tồn tại"
ls -la artifacts/classifier/ 2>/dev/null || echo "   ⚠️ artifacts/classifier/ chưa tồn tại"
ls -la artifacts/detector/ 2>/dev/null || echo "   ⚠️ artifacts/detector/ chưa tồn tại"
ls -la artifacts/retrieval/ 2>/dev/null || echo "   ⚠️ artifacts/retrieval/ chưa tồn tại"

# Tạo artifacts nếu thiếu
if [ ! -f "artifacts/classifier/model.pt" ]; then
  echo "📦 Bắt đầu tạo artifacts (mất 10-20 phút)..."
  python scripts/prepare_artifacts.py
  echo "✅ Đã tạo xong artifacts"
else
  echo "✅ Artifacts đã có sẵn"
fi

echo "▶ Khởi động uvicorn trên port $PORT..."
exec uvicorn api.main:app --host 0.0.0.0 --port $PORT