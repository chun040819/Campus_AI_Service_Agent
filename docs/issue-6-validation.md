# Issue #6 驗證紀錄

2026-10-23，Issue #6「完成多輪對話、Session 隔離與清除」。固定基準 `e626316353d6f49797a9c69679cfae6d8036a7c6`。使用者確認以 POST /api/chat、POST /api/reset、實際瀏覽器及真實模型多輪驗證為範圍。

## 交付範圍

既有後端已由 uuid4 產生 Session ID，按 Session 保存包含工具回傳的訊息；不存在或已重設的 ID 回404。清除只移除指定 Session。既有前端保存多輪訊息、每輪 trace，送出中顯示「處理中…」並停用控制項；清除成功後移除本地歷史與 Session ID。

本票補上針對完整使用流程的回歸測試與驗收證據，沒有新增產品行為。新測試對既有程式即通過，因此沒有虛構 red→green 或刻意改壞程式。受控模型僅位於外部 HTTP 邊界，Registry、SQLite、Session、API 都使用實際實作。

## 驗收條件與證據

1. 後端產生 Session ID、多輪前文：新增 API 測試驗證兩個不同 UUID，首輪查學生／教師政策，追問「那是多少次？」由同 Session 的工具訊息取得 H04/20 或 H05/40。
2. Session 隔離：交錯首輪、追問及清除，檢查模型請求的使用者訊息、助理訊息與工具結果沒有混用；清除 A 後 B 仍保有 H05。
3. 畫面多輪與每輪 trace、執行中：實際 Playwright 瀏覽器完成學生政策→指代追問，畫面保留兩個 article；第一輪展示 search_help_articles、query、H04 結果，第二輪明示未執行工具。1秒受控模型延遲期間觀察到「處理中…」，送出、輸入、清除皆停用。
4. 同步重設：瀏覽器觀察 /api/reset 回200與 ok=true，訊息及 trace 清空；後續 /api/chat 的 session_id=null，受控模型要求提供前文。API 測試另驗證舊 ID 回404、新 ID 不同、重複重設成功且 B 不受影響。

瀏覽器受控伺服器可用 `.venv/bin/uvicorn tests.browser_session_server:app --host 127.0.0.1 --port 8000`，搭配一般 Vite 前端重現；固定回覆皆明示受控測試，不能當成真實模型選工具能力。CLI wrapper 因 npm registry DNS 連線失敗而無法啟動，改用已連接 Playwright 工具操作真實瀏覽器。摘要見 [瀏覽器結果](issue-6-browser-results.json)，Console 0 errors、0 warnings。

## 真實模型

沿用既有後端 .env，TestClient 呼叫一般 create_app，未注入受控 transport；不是瀏覽器真實模型驗收。

- A 查學生政策 H04=20；B 查教師政策 H05=40。
- A 追問「那如果今天已用了8次，還剩多少？」：計算工具使用 H04，回12。
- B 同一句追問：計算工具使用 H05，回32。
- 重設 A 回200；舊 A 再問回404。
- 新 A 問「那每日額度是多少？」：模型列出學生／教師兩種政策並詢問身分，沒有沿用舊 A 身分或用量。
- B 追問剛才剩餘：仍回答32。

去除實際 Session ID 的完整對話與 trace 見 [真實模型結果](issue-6-live-results.json)。有限案例不能證明任意語句的模型正確率，不涉及正式部署或跨使用者身分認證。

## 自動檢查

- API 單檔：15 passed。
- 後端 mypy：10個來源檔通過。
- 前端 TypeScript / Vite build：通過。
- 最後全套 pytest：69 passed；既有 Starlette/httpx 棄用警告1則，未擴大處理。

## Code review

依 code-review skill，以固定基準對本票變更進行兩個獨立代理審查。Standards：0項，未發現規範違反或需處理的程式異味。Spec：0項，既有行為與新增驗證涵蓋四項驗收條件，未發現缺漏、錯誤或範圍擴張。
