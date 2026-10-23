# Issue #5 驗證紀錄

2026-10-23，Issue #5「完成轉真人協助流程」，實作前基準 `438b9eece006e5603c1d33732e7b89b22ce67d04`。依已確認工具規格 §3.4；使用者確認測試介面為 `ToolRegistry.execute` 與 `POST /api/chat`。

## 實作

註冊 `get_human_support`，只接受 reason 列舉 login/permission/api/outage/other，拒絕缺值、非法值、非字串及額外欄位。讀取 H08，回傳文章 ID、原始 instructions、channel_configured=false、handoff_completed=false、simulated=true。指引包含向平台管理者確認聯絡方式，以及錯誤碼、發生時間及去除機密的重現步驟。不寫資料、不建立工單、不傳送訊息。

模型依工具結果組織回覆；使用者要求人工、持續登入失敗或資料不足需維運時使用本工具，不採關鍵字路由。H08 缺少、無效參數及讀取失敗分別回 NOT_FOUND、INVALID_ARGUMENT、INTERNAL_ERROR。讀取失敗沿用既有聊天 502 與 trace 行為。

## 自動驗證

Registry 正常呼叫與文章缺少／讀取錯誤先取得失敗測試，再實作通過。初次測試把搜尋結果首筆誤當 H08，修正為依 article_id 選取。受控聊天測試驗證結果回送模型及 trace，涵蓋正常與三種錯誤；不代表模型自主選用能力。

- `.venv/bin/pytest -q`：68 passed，含新增17個案例。
- `.venv/bin/mypy backend`：10個來源檔通過。
- `npm --prefix frontend run build`：TypeScript 與 Vite 建置通過。
- 既有 Starlette/httpx 棄用警告未擴大處理。

## 真實模型 API 驗證

沿用後端 .env 設定，TestClient 呼叫一般 create_app，使用真實 HTTP 模型服務，未注入受控 transport。三題為「一直無法登入，想找人工協助」、「問題沒解決，聯絡維運」、「請幫我轉真人客服」。三題皆回200、實際執行 get_human_support 並依 H08 回覆，標示模擬、未配置管道及未完成交接，沒有虛構派案或聯絡方式。

首次沙箱網路連線三題皆502且無 trace；取得網路執行許可後三題皆成功。兩次結果均保留在 [實際對話與 trace](issue-5-live-results.json)，移除 Session ID，未記錄模型設定或憑證。

這是有限真實模型 API 案例；未進行瀏覽器、正式部署或真實人工接手驗收。正常的未配置管道回覆不等於工具失敗；處理失敗由受控 API 與 Registry 測試驗證。

## Code review

依 code-review skill，以實作前固定基準檢查本票變更，兩個獨立代理分別審查。Standards：0項，未發現規範違反或需處理的程式異味。Spec：0項，工具合約、錯誤處理與驗收證據符合確認規格，未發現範圍擴張。
