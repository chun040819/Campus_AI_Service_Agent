# Issue #2 驗證紀錄

2026-10-23，範圍：第一條查資訊客服流程。基準 `7b3ef0f`；實作 `65b075a`，審查修正 `ce5179c`。

- `uv run pytest -q`：15 passed。涵蓋 CSV 重建／錯誤列號、查詢與受眾／limit、字面 `%`／`_`、非法參數、查無、工具結果回送模型、無工具空 trace、Session 隔離／多輪／reset、模型失敗／六步上限、工具內部錯誤中止。
- `uv run mypy backend`：7 source files 通過。
- `npm --prefix frontend run build`：TypeScript 與 Vite 生產建置通過。
- 測試有一項第三方 Starlette 對 httpx TestClient 的棄用警告，未影響結果。

真實 Chrome 搭配 Vite 開發代理及 FastAPI：先以一般後端驗證未設定模型時的 503 提示；再以 `tests.browser_server` 的受控 HTTP 回應驗證送出 429 問題、CSV→SQLite 的 H03 結果、工具名稱／參數／完整結果顯示，以及清除對話恢復開場畫面。窄螢幕截圖已視覺檢視；最後 console 無 error/warn。受控 fixture 固定選工具，只證明應用程式連通與呈現，不能證明模型選用能力。

Code-review skill 雙軸審查：Standards 0 項；Spec 初次 1 項（工具內部錯誤後未中止），新增失敗測試重現後修正，複查無剩餘發現。

使用者確認暫無模型設定，保留真實 OpenAI-compatible 模型驗收為待完成。未驗證真實供應商、模型選工具正確率或內容品質，不關閉 #2。後續依 README 設定與步驟驗收。
