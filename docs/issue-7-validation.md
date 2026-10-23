# Issue #7 驗證紀錄

2026-10-23，固定基準 `2ee7419`。使用者確認 POST /api/chat、真實模型查無／範圍外對話及實際瀏覽器故障畫面為測試邊界。

## 實作與驗收

- System Prompt 已涵蓋四個實際工具、接地、繁體中文／英文、單位及人工支援限制。本票補明 NOT_FOUND 與執行失敗的差別、禁止範圍外工具呼叫，以及只婉拒無關內容。
- 新增 API 測試先重現 `message: null` 導致 AttributeError，再加入訊息型別驗證；現在安全回502、不洩漏供應商細節。頂層 null 回應亦有覆蓋。
- API 測試覆蓋 HTTP 503、ReadTimeout、6次模型呼叫上限及真實 SQLite 讀取失敗；保留實際 trace，立即停止，不宣稱成功。失敗後同 Session 重試只帶先前成功的歷史，失敗的使用者問題、工具及助理訊息不入歷史。
- 既有工具、API 與前端已提供錯誤處理及 trace 呈現，本票沒有改動 API 格式或 UI。

## 真實模型

一般 create_app、既有後端 .env、沒有注入 transport。初次受限環境網路連線失敗（全部502），開放本次驗收的網路連線後重跑。

[首次結果](issue-7-live-first-results.json)：火星校區政策及 INC-999 實際回 NOT_FOUND，無補造；中文旅遊婉拒且無工具；人工指引保留 H08、未配置與未交接。英文詩歌卻被完成，為真實失誤。補強 Prompt 後同五題[複測結果](issue-7-live-results.json)均符合預期，英文詩歌改用英文婉拒且 trace 空。這是有限案例，並非普遍正確率或對任意提示的保證。

## 實際瀏覽器

Chrome DevTools 開啟一般 Vite 頁面。一般後端的 INC-999 對話畫面同時顯示「目前示範資料庫中未收錄」、search_issue_records、issue_id=INC-999 與 NOT_FOUND；已視覺檢查整頁截圖。此步使用的後端在最後一次 Prompt 補強前啟動，最後 Prompt 的五題複測另由上方 API 結果證明。

之後切換 `tests.browser_failure_server:app`，依序輸入「測試模型失敗」、「測試呼叫上限」、「測試工具內部錯誤」。畫面依序出現模型暫時無法回覆、已達上限、查詢暫時無法使用，並保留1、6、1筆真實工具 trace；工具錯誤結果為 INTERNAL_ERROR。每次均有「模型未完成本輪回覆，對話歷史未新增此輪；可重試或清除」提示，輸入與清除恢復可用。

重現：`.venv/bin/uvicorn tests.browser_failure_server:app --host 127.0.0.1 --port 8000`，搭配 `npm --prefix frontend run dev`。此 fixture 只控制外部模型 HTTP 回應，API、Registry、CSV、SQLite、UI 均為實際程式；工具錯誤透過刪除專用 /tmp 測試資料庫重現，重新啟動 fixture 恢復。不代表真實模型選工具能力。

Playwright CLI 因 npm registry DNS 失敗未能啟動、連接器瀏覽器被占用，改用 Chrome DevTools。截圖可在工具回覆檢視，但連接器拒絕寫入本專案路徑，因此未聲稱有已存檔 PNG；保留可重現 fixture 與瀏覽器文字快照。

## 自動檢查與審查

API 單檔21項通過；最後全套 pytest 75項通過，既有 Starlette/httpx 棄用警告1則。後端 mypy（10檔）、前端 TypeScript 與 Vite build 通過。


## Standards

獨立代理以 `git diff 2ee7419...HEAD`（實作提交 `9885535`）檢查 AGENTS.md、RTK 與 docs/agents 指引及 Fowler smell baseline：0項發現，未見規範違反或需處理的異味。

## Spec

另一獨立代理比對 Issue #7、v1.2 §6–7 與核准工具規格：0項發現。查無／範圍外、失敗停止、trace、歷史隔離、語言及人工支援界線均有對應證據，未見範圍擴張。

總計 Standards 0項、Spec 0項，兩軸均無阻擋問題。審查後僅補本紀錄與移除快照結尾空白行，未改產品或測試程式。
