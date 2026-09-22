#!/bin/bash
# 啟動 Cloudflare Tunnel 免費公網穿透跳板
echo "============================================================"
echo "🚀 正在啟動 Cloudflare Tunnel 免費公網跳板 (Port 8080)..."
echo "📌 特點：永久 100% 免費、無限流量、免信用卡、0 扣款風險"
echo "📌 YouTube：直接走家用寬頻 IP，Google 絕不封鎖 403"
echo "============================================================"
/opt/homebrew/bin/cloudflared tunnel --url http://127.0.0.1:8080
