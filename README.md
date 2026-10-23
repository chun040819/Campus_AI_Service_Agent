# Campus AI Service Agent

虛構校園 AI 平台客服，政策及 CSV 全為教學示範資料，不代表任何真實學校政策、端點或服務狀態。目前提供查資訊與公開模擬故障紀錄流程；計算與轉真人工具尚未開放。

## 本機啟動

需求：Python 3.11+、uv、Node.js 20.19+ 或 22.12+、npm。

```bash
cp .env.example .env
uv sync --locked
npm --prefix frontend ci
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
# 另一個終端
npm --prefix frontend run dev
```

開啟 http://127.0.0.1:5173。Vite 將 `/api` 代理到 `127.0.0.1:8000`；API 文件為 http://127.0.0.1:8000/docs。

只在後端 `.env` 設定 `LLM_BASE_URL`（含 `/v1/` 或供應商等價路徑）、`LLM_API_KEY`、`LLM_MODEL`。模型必須支援 OpenAI-compatible `/chat/completions` 工具呼叫；本專案直接透過 HTTP 呼叫，不使用關鍵字路由。`.env.example` 不含可用憑證；未設定模型時健康檢查仍可用，聊天回 503。請勿在聊天輸入金鑰，或將機密加入任何 `VITE_*` 變數。

`DATABASE_PATH` 預設 `var/demo.db`，相對路徑以啟動目錄為準；建議從儲存庫根目錄啟動。啟動時驗證並重建 `data/help_articles.csv` 的 8 篇資訊，錯誤會指出檔案與列號。SQLite 僅留在後端並被 Git 忽略。同時驗證並重建 `data/issue_records.csv` 的至少 15 筆公開模擬紀錄；可用性與處理階段分開保存，受影響請求數單位為次。

## API 與限制

- `GET /api/health`：服務存活，不代表模型可用。
- `POST /api/chat`：`{"session_id":null,"message":"429 代表什麼？"}`；回傳 `session_id`、`reply`、本輪 `tool_traces`。後續帶入同一 ID 以延續對話。沒有工具呼叫則 trace 為空。
- `POST /api/reset`：`{"session_id":"後端核發的 ID"}`；清除後端歷史，重複清除仍成功。
- ToolRegistry 公開 `search_help_articles` 與 `search_issue_records`，固定字面子字串查詢；`%`、`_` 不是萬用字元。驗證名稱、參數及 schema/handler 欄位，統一 ok/data 或 ok/error。
- 模型每輪最多 6 次呼叫，每次最多 8 個工具呼叫；失敗回 502 並保留已產生的 trace，本輪不加入歷史。每個 session 最多約 200 則訊息、服務最多 100 個對話；清除可釋放。
- 單程序記憶體 Session，重啟即清空；請使用一個 worker。本機示範未提供身分認證，僅綁定 loopback，勿直接公開部署。所有聊天共用序列鎖，適合教學規模。

`search_issue_records` 支援 query（title/service/symptom/workaround 字面比對）、issue_id（INC-三位數精確比對）、status（investigating/identified/monitoring/resolved），條件取交集；不提供條件時列最近 5 筆，limit 為 1–15。按更新時間降冪、ID 升冪排序。不可用是有效結果，查無為 NOT_FOUND；回覆保留模擬標示與最後更新時間，不表示目前真實狀態。

## 驗證

```bash
uv run mypy backend
uv run pytest
npm --prefix frontend run build
```

API 測試以受控 OpenAI-compatible HTTP 回應驅動真實 Registry、CSV 與 SQLite，驗證結果回送、trace、Session、重設、查無、失敗與步數上限。這不是模型選工具能力或內容品質的驗收。

可重現受控瀏覽器驗證：以 `uv run uvicorn tests.browser_server:app --host 127.0.0.1 --port 8000` 取代一般後端，啟動 Vite 後送出「429 代表什麼？」。此 fixture 固定查 429，回覆明示受控測試，不作正式模型路由。

真實模型驗收：設定後端環境後，以一般 `backend.main:app` 啟動，分別詢問「API Key 怎麼申請？」、「429 代表什麼？」、「查詢不存在的火星校區政策」與範圍外問題；檢查工具名稱、參數、結果與最終回覆一致。多輪與清除也需驗證。2026-10-23 已完成 Gemini 真實模型的上述 API 案例及學生／教師多輪查詢、重設驗證，見 [驗證紀錄](docs/issue-2-validation.md)。此為有限案例，不宣稱普遍模型選用正確率或完整作業完成。

Gemini 的相容端點為 `https://generativelanguage.googleapis.com/v1beta/openai/`，`LLM_MODEL` 使用 API ID（例如本次驗證的 `gemini-3.5-flash-lite`），不能填顯示名稱。請依 [官方文件](https://ai.google.dev/gemini-api/docs/openai/) 與帳戶可用模型設定。
