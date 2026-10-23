# Issue #8 驗證資料與工具執行邊界

2026-10-23，基準 d082f3c。使用者確認 CSV 匯入公開函式、ToolRegistry、POST /api/chat 及實際瀏覽器為測試邊界。

## CSV

新增測試先重現非法 UTF-8 缺少檔名列號，以及資訊 CSV 缺尾欄仍被接受，共3項失敗。修正為匯入前完整解碼，編碼錯誤轉成含來源與實體列號的 ValueError；兩種匯入都拒絕缺欄（None），允許規格定義的空字串選填值。

18項新增邊界測試涵蓋兩種 CSV 編碼錯誤、必要值、重複主鍵、非整數、受眾／可用狀態、重複匯入後資料仍可查、錯誤匯入保留既有資料。既有 tests/test_records.py 另驗證重匯入恰15筆，test_tools.py 驗證無重複 ID。CSV 列內容驗證既有診斷以資料列序號（從2起）呈現；目前種子每筆一行，未宣稱多行欄位內容的實體起始列診斷。

## 工具與執行界線

新增 Registry 公開介面測試拒絕 Schema／handler 欄位不一致且不註冊；handler 拋出含測試機密的例外，只回 INTERNAL_ERROR 與通用訊息。

受控外部模型 HTTP 回應經真實 POST /api/chat、Registry、SQLite：execute_sql、run_python、read_environment 均未註冊而回 INVALID_ARGUMENT；合法工具額外 sql 參數亦拒絕。SQL 注入字串在兩種查詢中當字面值處理，回 NOT_FOUND；之後 H03 及15筆紀錄仍完整可查。模型收到實際錯誤，使用者回應與 trace 可見拒絕結果，不包含測試 API key。

程式檢視：backend/tools 下的所有 SQL 使用固定查詢與位置參數，沒有模型 SQL／eval／exec 執行入口。ToolRegistry 只允許註冊 handler；公開 schema 僅四個已核准工具。未新增寫入工具，沒有新增需確認的外部副作用。

## XSS 與機密

以 Chrome DevTools 開啟實際 Vite 頁面、tests.browser_xss_server 後端，送出 `<img src=x onerror="window.__campusXss=1"><script>window.__campusXss=2</script>`。fixture 在外部模型邊界輸出同 payload 作為工具名稱、參數及最終回覆；Registry 真實拒絕未知工具。

[瀏覽器快照](issue-8-browser-xss.txt) 顯示使用者訊息、回覆、工具名與參數皆為文字。DOM 檢查結果：window.__campusXss 未設定，main 中 img、script、[onerror] 元素共0個。既有 React 插值與 JSON.stringify 未用 HTML 注入，無須改前端。

重現：以 `.venv/bin/uvicorn tests.browser_xss_server:app --host 127.0.0.1 --port 8000` 搭配 `npm --prefix frontend run dev`，送出任意文字。這是受控惡意輸出測試，不是模型拒絕攻擊的普遍能力證據。

後端的 key 只用於 Authorization，System Prompt 不放環境值；供應商錯誤與 handler 例外採通用提示。既有 API 測試涵蓋供應商機密／錯誤細節不外洩。本票未讀取或輸出真實憑證。System Prompt 含禁止洩漏設定規則；不宣稱能保證任意真實模型不複述系統提示。

## 檢查

邊界單檔18 passed；最後全套93 passed，既有 Starlette/httpx 棄用警告1則。mypy backend（10檔）、前端 TypeScript 與 Vite build 通過。驗收後已停止本機服務。

雙軸 code-review 結果於交付前補記。
