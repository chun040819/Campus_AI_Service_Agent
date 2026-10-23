# 綜合型校園 AI 平台智慧客服工具規格（Issue #1）

- 依據：[Issue #1](https://github.com/chun040819/Campus_AI_Service_Agent/issues/1)、系統規格 v1.2。
- 狀態：2026-10-23 專案負責人確認本草案，採用學生每日 20 次、教師每日 40 次、每分鐘 5 次的模擬額度；人工支援明示「尚未配置」；紀錄限公開模擬故障。下列工具合約與資料設計作為後續實作基準，尚非已實作功能。
- 全部平台政策、額度、故障紀錄及處理進度均為模擬教學資料，不代表真實學校服務。

## 1. 已確認的服務範圍

服務學生與教師，協助平台操作、帳號權限、API 使用、系統異常與問題回報。支援查資訊、查歷史／已知問題與處理階段、剩餘請求次數試算，以及取得人工協助方式。

不讀取真實個人用量、帳號或工單，不建立真實派案，不承諾已通知維運。模型費率與 Token 計費不在範圍內。

## 2. 共用合約（已確認基準）

所有工具只接受列出的參數；拒絕額外欄位，不接受 SQL 或程式碼。字串去除首尾空白後驗證長度。結果成功為 `{"ok":true,"data":{...}}`；失敗為 `{"ok":false,"error":{"code":"...","message":"..."}}`。必要錯誤為 `INVALID_ARGUMENT`、`NOT_FOUND`、`INTERNAL_ERROR`；內部錯誤不得洩漏堆疊或憑證。

查詢結果須包含資料識別碼與 `simulated: true`。使用固定查詢及參數綁定；搜尋字串中的 `%`、`_` 視為普通字元。資料不得包含個資、API Key 或真實帳號事件。

## 3. 工具規格卡（已確認基準）

### 3.1 `search_help_articles` — 查資訊

- 適用問題：API Key 申請、OpenAI SDK 連線、429、學生／教師額度、操作及權限說明。
- 供 LLM 的描述：查詢模擬平台操作與政策；不查故障進度、不計算剩餘次數。使用問題中的具體主題詞查詢；查無時不得補造政策。
- 輸入：必填 `query: string`（1–100 字元）；選填 `audience: "student" | "teacher" | "all"`，預設 `all`；選填 `limit: integer`，1–8，預設 5。
- 讀取：`help_articles` 全部欄位。`all` 搜尋全部受眾；指定受眾時包含該受眾與 `all`。
- 查詢：對 topic、keywords、content 做大小寫不敏感的字面子字串比對，以 article_id 排序後限制筆數；沒有語意搜尋。呼叫端可換具體關鍵字重查，不把查無解釋成政策不存在。
- 輸出：`data.articles` 陣列，每筆含資料表全部欄位；`data.simulated: true`。只回傳命中內容，不生成最終客服話術。
- 失敗：零筆為 `NOT_FOUND`；空白 query、不合法受眾或 limit 為 `INVALID_ARGUMENT`；資料存取失敗為 `INTERNAL_ERROR`。
- 案例：`query="API Key"` 命中 H01；`query="429"` 命中 H03；指定 student 不回 teacher 專用文章；不存在的主題查無；空白及 limit=0 拒絕；limit=8 合法。

### 3.2 `search_issue_records` — 查紀錄

- 適用問題：類似錯誤、已知故障清單、指定問題目前的處理階段。
- 供 LLM 的描述：查公開的模擬平台故障紀錄；不查使用者私人工單，不把歷史故障當成目前仍故障。查資訊操作指引使用查資訊工具。
- 輸入：選填 `query: string`（1–100 字元）、`issue_id: string`（格式 `INC-` 加三位數字）、`status: "investigating" | "identified" | "monitoring" | "resolved"`；`limit: integer`（1–15，預設 5）。不傳篩選條件時列出最近紀錄；傳入空白字串為無效。
- 讀取：`issue_records` 全部欄位；同時提供的篩選條件取交集。query 比對 title、service、symptom、workaround 的字面子字串；issue_id 精確比對。
- 查詢：updated_at 由新到舊，時間相同以 issue_id 升冪；最多 limit 筆。status 是處理階段，available 是該筆紀錄最後更新時的服務可用性，兩者不互相推導。
- 輸出：`data.records` 陣列（完整欄位）、`data.simulated: true`。回覆必須保留最後更新時間及模擬標示。
- 失敗：無符合項目為 `NOT_FOUND`；不合法篩選值為 `INVALID_ARGUMENT`；資料存取失敗為 `INTERNAL_ERROR`。available=false 是有效查詢結果，不是工具失敗。
- 案例：查 INC-001 取得 investigating；無條件查詢可列紀錄；query="429" 找到 INC-004；status="resolved" 只回已解決項目；INC-999 查無；非法階段、空 query、limit=16 拒絕。

### 3.3 `calculate_remaining_requests` — 計算

- 適用問題：「假設每日 20 次、已用 8 次還剩多少？」及已知各限制與已用次數時的剩餘可發送次數。
- 供 LLM 的描述：由 Python 執行請求次數試算。每個限制須有明確上限、已用次數與同一統計期間；缺少任一資料先詢問，不能猜測真實用量。429 不一定是每日額度耗盡。不能用本工具計算 Token、金額或並行數。
- 輸入：必填 `limits: array`（1–4 項）；每項必填 `name: string`（1–40 字元且不得重複）、`window: "minute" | "day"`、`maximum: integer` 與 `used: integer`（皆 0–1,000,000）、`source: "user_assumption" | "help_article"`。source=help_article 時另必填 `article_id: string`，必須對應具有同 window 與 maximum 的政策文章；user_assumption 不接受 article_id。禁止浮點、布林值當整數與額外欄位。
- 讀取：user_assumption 不讀資料表；help_article 由後端讀 help_articles 的 request_limit、limit_window，驗證與輸入一致。used 永遠來自使用者明確提供的同期間用量，沒有自動讀取用量能力。
- 公式與單位：每項 `remaining = max(maximum - used, 0)`，單位為「請求次數」。同時適用的限制取 `sendable_now = min(remaining)`；這只是依提供數字估算的當下剩餘次數，不保證後續請求成功、不預測重設時間、不將每日剩餘等同每分鐘可送量。
- 輸出：`data.limits` 每項回傳輸入、remaining 與 `over_limit = used > maximum`；另回 `data.sendable_now`、`data.unit="requests"`、`data.simulated=true`。來源為使用者假設或模擬政策；不是帳戶實際餘額。
- 失敗：缺值、負數、超界、非整數、期間不明確、名稱重複或政策值不一致為 `INVALID_ARGUMENT`；article_id 不存在為 `NOT_FOUND`；資料存取失敗為 `INTERNAL_ERROR`。used 超過 maximum 合法，回 0 並標記超限。
- 案例：每日 20/8 得 12；20/20 得 0；20/21 得 0 且 over_limit=true；每日 20/8、每分鐘 5/4 得 sendable_now=1；0/0 得 0；負數、小數、缺 used 拒絕；不存在文章查無；政策值不一致拒絕。

### 3.4 `get_human_support` — 轉真人

- 適用問題：使用者要求人工協助、持續登入失敗、工具資料不足而需要維運處理。
- 供 LLM 的描述：取得人工支援指引；本示範不建立工單、不傳送訊息、不宣稱真人已接手。未設定管道時如實說明。
- 輸入：必填 `reason: "login" | "permission" | "api" | "outage" | "other"`。不收帳密、API Key、電子郵件或自由文字個資。
- 讀取：資訊文章 H08 的聯絡說明；不讀私人紀錄、不寫資料庫、不執行外部操作。
- 操作：回傳 H08 的指引及要求使用者自行提供給人工的診斷項目（錯誤碼、發生時間、去除機密的重現步驟）。聯絡方式尚未設定時只提供平台管理者確認管道的下一步，不能產生虛構網址或信箱。
- 輸出：`data.article_id`、`data.instructions`、`data.channel_configured`、`data.handoff_completed=false`、`data.simulated=true`；目前 channel_configured=false。
- 失敗：不合法 reason 為 `INVALID_ARGUMENT`；H08 缺少為 `NOT_FOUND`；讀取例外為 `INTERNAL_ERROR`。沒有聯絡管道仍可成功回傳未設定狀態，但不得宣稱轉接成功。
- 案例：reason=login 回傳登入問題支援指引且 handoff_completed=false；未設定管道時明示；非法 reason 拒絕；文章缺少與資料存取錯誤分別處理。

## 4. CSV 與資料表設計（已確認設計，種子 CSV 已交付；資料表由後續實作建立）

### 資訊：`data/help_articles.csv` → `help_articles`

欄位：article_id（唯一字串）、topic（非空）、audience（student/teacher/all）、keywords（非空文字）、content（非空文字）、request_limit（可空非負整數，最多 1,000,000）、limit_window（可空 minute/day）。後兩欄必須同時有值或同時留空，每篇至多一組限制。

| ID | 主題 | 受眾 | 預定內容與數值來源 |
|---|---|---|---|
| H01 | API Key 申請 | all | 示範申請、保管、撤銷流程；不提供真實金鑰 |
| H02 | OpenAI SDK 連線 | all | 示範 base_url 與環境變數用法；實際端點待設定 |
| H03 | 429 錯誤 | all | 區分速率與額度限制，依錯誤內容排查，不一律判為額度耗盡 |
| H04 | 學生每日額度 | student | 20 次/day，已確認的模擬政策 |
| H05 | 教師每日額度 | teacher | 40 次/day，已確認的模擬政策 |
| H06 | API 每分鐘限制 | all | 5 次/minute，已確認的模擬政策 |
| H07 | 登入與帳號權限 | all | 登入排查、學生／教師權限說明；無實際解鎖能力 |
| H08 | 人工支援與問題回報 | all | 未配置真實管道；告知向平台管理者確認，不承諾已交接 |

### 紀錄：`data/issue_records.csv` → `issue_records`

欄位：issue_id（唯一、INC-三位數）、title、service、symptom、status（四種階段）、available（true/false）、affected_requests（非負整數，單位：次，示範受影響請求數）、workaround（非空，沒有則明寫無已知方法）、updated_at（ISO 8601 UTC 時間）。皆必填。數值用於呈現故障影響，不能當成使用者已用次數或剩餘額度。

下列兩表以 issue_id 對應，合起來定義 15 筆種子的完整欄位內容。時間全為固定的教學示範時間，不表示當時真的發生故障。affected_requests 是故障影響摘要；剩餘額度的計算數值另由 H04–H06 與使用者提供的用量取得，不混用兩者。

| ID | 名稱 | 服務 | 階段 | 可用 | 受影響請求（次） |
|---|---|---|---|---|---:|
| INC-001 | 學生登入失敗 | login | investigating | false | 12 |
| INC-002 | 教師權限延遲 | permissions | identified | false | 6 |
| INC-003 | API Key 建立延遲 | api_keys | monitoring | true | 8 |
| INC-004 | 429 速率限制誤觸 | api | resolved | true | 30 |
| INC-005 | SDK 連線逾時 | api | investigating | false | 15 |
| INC-006 | 每日額度顯示延遲 | quota | monitoring | true | 9 |
| INC-007 | 平台頁面無法載入 | web | resolved | true | 22 |
| INC-008 | API 回傳 503 | api | identified | false | 40 |
| INC-009 | API Key 撤銷延遲 | api_keys | resolved | true | 3 |
| INC-010 | 登入重新導向循環 | login | resolved | true | 18 |
| INC-011 | 教師服務入口無法開啟 | web | monitoring | true | 4 |
| INC-012 | 使用次數重設延遲 | quota | identified | false | 11 |
| INC-013 | SDK 端點設定錯誤 | api | resolved | true | 7 |
| INC-014 | 問題回報頁面異常 | support | investigating | false | 5 |
| INC-015 | 權限變更未同步 | permissions | resolved | true | 10 |

| ID | symptom | workaround | updated_at |
|---|---|---|---|
| INC-001 | 學生登入顯示暫時無法登入 | 無已知方法；稍後重試並保留錯誤碼 | 2026-10-20T08:00:00Z |
| INC-002 | 教師登入後未顯示應有權限 | 登出再登入；仍異常則依人工支援指引處理 | 2026-10-20T07:00:00Z |
| INC-003 | 建立 API Key 時頁面等待過久 | 先確認清單是否已建立，避免重複申請 | 2026-10-20T06:00:00Z |
| INC-004 | 低於限制仍收到 429 | 已修正；再次發生時記錄錯誤內容，勿密集重試 | 2026-10-19T08:00:00Z |
| INC-005 | SDK 請求等待後逾時 | 暫停連續重試，保留去除金鑰的錯誤訊息 | 2026-10-19T07:00:00Z |
| INC-006 | 額度頁面顯示舊使用次數 | 重新整理頁面；不要將顯示延遲解讀為額度增加 | 2026-10-19T06:00:00Z |
| INC-007 | 平台首頁顯示空白 | 已修正；重新整理頁面 | 2026-10-18T08:00:00Z |
| INC-008 | API 請求回傳 503 | 暫停請求，稍後重試；無已知即時修復方法 | 2026-10-18T07:00:00Z |
| INC-009 | 撤銷後清單仍顯示舊狀態 | 已修正；重新載入清單，勿分享或繼續使用已撤銷金鑰 | 2026-10-18T06:00:00Z |
| INC-010 | 登入頁面反覆重新導向 | 已修正；關閉舊登入分頁後重試 | 2026-10-17T08:00:00Z |
| INC-011 | 教師入口顯示載入失敗 | 重新整理後觀察；仍失敗則記錄發生時間 | 2026-10-17T07:00:00Z |
| INC-012 | 新統計日仍顯示前日次數 | 無已知方法；勿自行假定已恢復額度 | 2026-10-17T06:00:00Z |
| INC-013 | SDK 使用錯誤端點而無法連線 | 已修正示範設定；依 H02 核對設定，不猜測平台端點 | 2026-10-16T08:00:00Z |
| INC-014 | 問題回報頁面無法送出 | 保留去除個資的錯誤碼與重現步驟；人工管道尚未配置 | 2026-10-16T07:00:00Z |
| INC-015 | 權限調整後仍顯示舊權限 | 已修正；登出再登入 | 2026-10-16T06:00:00Z |

CSV 使用 UTF-8；匯入檢查唯一識別碼、必要欄位、數值與列舉、時間格式，錯誤指出檔案與列號。啟動重建示範資料避免重複插入；SQLite 產物不提交。以上尚非 CSV 匯入實作或驗收結果。

## 5. 後續驗收題目（尚未執行）

| 問題 | 可接受的工具與判定 |
|---|---|
| API Key 怎麼申請？ | search_help_articles，取得 H01 |
| 如何使用 OpenAI SDK 連接？ | search_help_articles，取得 H02；不虛構實際端點 |
| 429 代表什麼？ | search_help_articles，取得 H03 |
| 學生每日使用額度？ | search_help_articles，取得 H04 並標模擬 |
| 之前有類似 429 的故障嗎？ | search_issue_records，取得 INC-004 |
| 有哪些已知故障？ | search_issue_records，保留階段與最後更新時間 |
| INC-001 處理到哪？ | search_issue_records，investigating |
| 假設每日 20 次、用 8 次還剩多少？ | calculate_remaining_requests，12 次 |
| 依學生政策已用 8 次還能送幾次？ | search_help_articles → calculate_remaining_requests；以核准政策計算 |
| 每日 20/8、每分鐘 5/4，現在還能送幾次？ | calculate_remaining_requests，1 次試算 |
| 查 INC-999 | search_issue_records，NOT_FOUND；不可補造紀錄 |
| 一直無法登入，想找人工 | get_human_support；可先查登入指引，但必須提供人工指引且不宣稱交接完成 |
| 問題沒解決，聯絡維運 | get_human_support，明示未配置真實管道 |
| 幫我寫旅遊行程 | 不呼叫工具，說明超出客服範圍 |

計算用量不明時先詢問；目前階段不寫固定關鍵字路由、不聲稱模型選工具準確率。正常查詢、計算與查無資料三組展示待實作後取得真實 trace。

## 6. 確認與完成門檻

- 2026-10-23 負責人確認規格草案與三個明確決策：採用模擬額度、人工管道明示尚未配置、僅查公開模擬故障。
- 四張工具卡、兩表欄位、8 個資訊主題與 15 筆完整紀錄內容設計已記錄；`data/help_articles.csv` 與 `data/issue_records.csv` 已交付，作為 Issue #1 的規格與種子資料。資料匯入、工具與應用程式仍由後續票實作。
- H02 的真實平台端點不是本票的承諾功能；後續示範以明確的設定占位值呈現，沒有設定時不得聲稱可連線。
- 人工支援此次核准的是「未配置管道」的示範指引，不代表已有真人轉接能力；後續驗收依此邊界判定。
- 本次僅交付規格與 CSV 種子資料；儲存庫尚無可執行程式、型別檢查或測試套件，TDD 與程式測試不適用。CSV 已檢查筆數、唯一識別碼、必要欄位、核准額度、數值、狀態與時間格式。後續建立測試前，依 tdd 技能與使用者確認公開測試介面。
