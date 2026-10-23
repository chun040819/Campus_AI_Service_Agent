# Issue #9：真實模型路由評測與展示

2026-10-23。實作基準 `bb76402`，評測與範例實作 `b577faf`。所有政策、額度及故障都是虛構教學資料；真實的是本次供應商模型呼叫、Registry/SQLite 執行及瀏覽器操作。

## 方法與重現

- 供應商：Google Gemini，實際相容 API 主機 `generativelanguage.googleapis.com`；模型 API ID `gemini-3.5-flash-lite`。四個工具均在本次真實 trace 中出現，驗證此模型在本帳戶支援 Tool Calling。使用現有後端 `.env`，未注入受控 transport，憑證不寫入結果。
- [14 題題庫](issue-9-cases.json)在第一次執行前固定。每題以獨立 Session 透過公開 `POST /api/chat` 執行，保存回覆、HTTP 狀態、工具名稱、參數與結果，再清除 Session。
- 每個 `stages` 元素是一階段可接受的工具集合；階段內允許同工具換詞重查，每階段至少一次，禁止漏掉、逆序或加入額外工具；空 stages 代表不得呼叫工具。Q08 必須先查政策再計算。首次與複測使用相同題庫 SHA-256 `006bf91e79a273a83d85a951d176aaf32da32cb9dca00f24ec8ecae64c87f92a`。
- 自動路由正確 = HTTP 200 且工具名稱順序符合預定 stages。此分數不代表參數與回覆正確；另逐題按 `content_check` 人工比對真實工具參數、結果及回覆，不能只靠工具名稱宣稱內容驗收。
- 評測器僅供離線驗收，不改正式客服路由；每題實際由模型選工具。輸出檔已存在時拒絕覆寫，逐題落盤保留中斷及失敗證據。

```bash
rtk proxy .venv/bin/python -m scripts.evaluate_routing --output /tmp/campus-routing-new.json
rtk proxy .venv/bin/mypy backend scripts
rtk proxy .venv/bin/pytest -q
rtk npm --prefix frontend run build
```

## 結果

[首次完整結果](issue-9-first.json)：14/14，100% 路由正確；未觀察到路由失誤，沒有為評測修改 System Prompt、工具、模型或題庫。這是實際執行後的有限題庫結果，不保證其他問題、模型版本或重跑必然滿分。

第一次複測因工作中斷只完成6/14題，保留為 [中斷紀錄](issue-9-interrupted.json)，完成部分6題路由皆通過；不把它當完整複測或併入完整評測分母。另以同一題庫從頭進行完整複測。

[完整複測結果](issue-9-retest.json)：12/14，85.7%（依事前定義，HTTP 502 一律算失敗）。兩次完整執行間沒有修改 Prompt、工具、模型或題庫，不為追求滿分再覆蓋結果。

| 題目 | 首次 | 複測 | 人工檢查／失誤紀錄 |
|---|---|---|---|
| Q01 API Key | 通過 | 通過 | H01，示範流程與安全保存；不代建 |
| Q02 SDK | 通過 | 通過 | H02，未配置端點，無虛構網址 |
| Q03 429 | 通過 | 通過 | H03，速率／額度分辨，不一律判每日耗盡 |
| Q04 學生額度 | 通過 | 通過 | H04，20次/day；複測首次關鍵字查無，換詞取得文章，屬預先允許的同工具重查 |
| Q05 INC-001 | 通過 | 通過 | investigating、available=false、更新時間、模擬標示一致 |
| Q06 歷史429 | 通過 | 通過 | INC-004 resolved、更新時間、模擬資料，不當作目前真實狀態 |
| Q07 假設計算 | 通過 | 通過 | user_assumption，20/8/day，剩12、sendable_now=12次 |
| Q08 政策計算 | 通過 | 通過 | 查得H04與H06後才計算；來源help_article，20/8/day剩12、5/4/minute剩1、現在1次 |
| Q09 超限 | 通過 | 通過 | 20/21/day，工具over_limit=true、remaining=0、sendable_now=0次 |
| Q10 紀錄查無 | 通過 | 通過 | INC-999 NOT_FOUND，回覆未收錄，未補造 |
| Q11 政策查無 | 通過 | 通過 | 火星校區 NOT_FOUND，未補造政策 |
| Q12 人工指引 | 通過 | **失敗502** | 首次H08明示未配置、未交接；複測工具get_human_support已成功回傳，但後續模型未完成回覆 |
| Q13 中文旅遊 | 通過 | **失敗502** | 首次無工具並婉拒；複測無工具但模型未完成回覆，不能把空trace當成功婉拒 |
| Q14 英文詩歌 | 通過 | 通過 | 無工具、英文婉拒，未生成詩歌 |

首次內容人工檢查14/14符合題庫條件；複測完成的12題符合，另2題因502未完成驗收，仍保留在分母。工具名稱順序在兩次完整紀錄中皆未觀察到錯選，但本票採用的端到端路由指標同時要求正常回覆，所以複測不是100%。對502只能確認模型呼叫流程未完成；後端刻意不保存供應商敏感錯誤，因此無法從此證據斷言是配額、逾時或其他供應商錯誤，未據猜測修改正式程式。

## 三組真實對話展示

以一般 `backend.main:app` 與 Vite 前端啟動，Chrome DevTools 真實點選範例／填入問題、送出、等待模型回覆。沒有使用 browser fixture 或重播 API 結果。桌面同頁左右欄同時呈現回覆與完整 trace，以下為已視覺檢查的整頁 PNG：

| 展示 | 問題與證據 |
|---|---|
| [正常查詢](issue-9-query.png) | API Key 怎麼申請？回覆依 H01，search_help_articles 參數與真實文章結果同畫面；不代建、不索取金鑰 |
| [計算](issue-9-calculation.png) | 假設每日20次、今天已用8次。回覆與 calculate_remaining_requests 的 user_assumption、20/8/day、remaining=12、sendable_now=12、requests、simulated 同畫面 |
| [查無資料](issue-9-not-found.png) | INC-999。回覆明示示範資料未收錄；search_issue_records 的 issue_id 與 NOT_FOUND 同畫面，沒有補造階段 |

截圖工具直接寫檔受連接器路徑限制，因此以其原始 PNG 回傳資料存入本專案，未修改圖片內容。計算展示使用「使用者假設」為來源；政策文章來源計算另由 Q08 的完整 trace 證明。

## 前端與檢查

開場及五個範例已對應查資訊、查紀錄、請求次數試算與人工支援指引，明示人工管道未配置、不建立工單或完成交接。既有原生 details/summary 支援折疊 trace。

Chrome 裝置模擬 `390x844x1,mobile,touch`，實際 innerWidth=390、scrollWidth=390：點選「429 代表什麼？」、送出、等待真實模型 H03 回覆，再點選 summary 收合 trace；按 Enter 可重新展開，焦點保留在 SUMMARY。清除後回到五個範例的開場。[手機截圖](issue-9-mobile.png)保留回覆與已收合 trace。另檢查 320、768、1024、1440px，scrollWidth 均等於 viewport，五個範例與輸入欄均可見；瀏覽器沒有 console error/warning。最初 resize_page 要求390px卻得到500px，改用裝置模擬後才列為390px驗收，未把500px當成手機尺寸證據。

使用者同意以評測器 trace 比對函式為新增測試邊界。先執行新增單檔，因尚無實作產生 ModuleNotFoundError（Red），加入比對函式後2項通過（Green）。涵蓋必需階段、重查、錯序、額外工具與空工具路由。全套 pytest 95項通過；既有 Starlette/httpx 棄用警告1則。mypy backend/scripts 共11檔、前端 TypeScript 與 Vite build 通過。

## Standards

獨立代理審查 `bb76402...b577faf`，並對 `bb76402...2f68bd6` 完成最終補審，依 AGENTS.md、RTK、docs/agents 指引及 Fowler smell baseline：0項發現，無阻擋問題。路由指標明確區別於內容正確率；首次、完整複測與中斷紀錄的分母及失敗處理均與 JSON 一致。

## Spec

獨立代理比對 Issue #9 與核准工具規格，最終補審至 `2f68bd6`：0項發現、0項範圍擴張，先前完整複測、390px與最終文件的待交付證據已補齊。三組真實截圖、計算來源與結果、查無未編造、型別檢查／建置／全套測試均有證據；本票要求如實量測而非滿分，因此複測兩題502已如實記錄，未視作未揭露的成功。
