# Issue #3 驗證紀錄

2026-10-23，Issue #3「完成紀錄查詢與可用狀態呈現」。固定基準 `0f51d6d`，主實作 `9904c09`。

## 實作與自動驗證

啟動時驗證並重建至少 15 筆公開模擬故障紀錄；CSV 驗證唯一 ID、必要欄位、狀態、布林、非負 SQLite 整數及 ISO UTC 時間，錯誤顯示檔案與列號，無效輸入不覆蓋既有紀錄。

`search_issue_records` 支援字面查詢、ID 精確查詢、處理階段交集與 1–15 筆限制；可用性獨立回傳 JSON boolean，不可用不是錯誤。結果包含所有紀錄欄位與 simulated 標示。按 UTC 時間降冪及 ID 升冪排序，使用 Decimal 保留小數秒精度。

- `.venv/bin/pytest -q`：22 passed；工具查詢、啟動匯入、重匯入、排序與微秒邊界、15 筆上限、交集、字面萬用符號、查無、非法參數、匯入錯誤保留原資料、API 結果回送模型與 trace。
- `.venv/bin/mypy backend`：8 個來源檔通過。
- `npm --prefix frontend run build`：TypeScript 與 Vite 建置通過。
- Starlette/httpx TestClient 有既存第三方棄用警告。

首次以 INC-001 查詢測試取得 red，實作匯入／註冊工具後 green。審查排序問題另以相差一微秒案例取得 red，修正後 green。

## 真實模型 API 與聊天

沿用後端 `.env` 的 Gemini 相容服務，以一般 `backend.main:app` 執行；沒有替換模型或固定路由。去除 Session ID 的完整結果見 [實際 API 結果](issue-3-live-results.json)。

- INC-001：investigating、最後更新時不可用、12 次、2026-10-20T08:00:00Z，標明模擬。
- 429 歷史故障：INC-004、可用、30 次、2026-10-19T08:00:00Z，標明模擬及歷史狀態。
- 最近 15 筆：模型傳 limit=15，工具回傳全部 15 筆，回覆保留階段、可用性、數值單位與更新時間。
- INC-999：工具 NOT_FOUND，模型如實回答查無，未補造紀錄。

真實 Chrome 經 Vite 代理與一般 FastAPI 後端送出 INC-001 查詢，核對真實模型回覆與 search_issue_records trace、參數、完整結果。窄視窗截圖已視覺檢視：回覆與 trace 可讀，呈現 false、12、更新時間與 simulated:true；既有聊天介面仍將模型 Markdown 作純文字顯示。Chrome DevTools MCP 因 profile 衝突無法連線，改用原生 Chrome UI；未取得 console/network 自動化檢查證據。

非法工具參數以受控 API／工具測試確認；不要求真實模型故意產生無效參數。本次有限案例不代表一般化模型選工具準確率。

## Code review

code-review 技能以兩個獨立代理審查：Standards 0 項；Spec 初次 1 項（SQLite julianday 丟失微秒精度），補測修正後複查無剩餘發現。
