cd ./card_payment_service && uv sync
nohup uv run uvicorn app.main:app --reload --port 8001 &
deactivate
cd ../netbanking_support
nohup go run ./cmd/netbanking &
cd ../upi_payment_service && npm i && npm run build
nohup npm start &