# Issue #2 驗證紀錄

2026-10-23，範圍：第一條查資訊客服流程。基準 `7b3ef0f`；實作 `65b075a`，審查修正 `ce5179c`。

- `uv run pytest -q`：15 passed。涵蓋 CSV 重建／錯誤列號、查詢與受眾／limit、字面 `%`／`_`、非法參數、查無、工具結果回送模型、無工具空 trace、Session 隔離／多輪／reset、模型失敗／六步上限、工具內部錯誤中止。
- `uv run mypy backend`：7 source files 通過。
- `npm --prefix frontend run build`：TypeScript 與 Vite 生產建置通過。
- 測試有一項第三方 Starlette 對 httpx TestClient 的棄用警告，未影響結果。

真實 Chrome 搭配 Vite 開發代理及 FastAPI：先以一般後端驗證未設定模型時的 503 提示；再以 `tests.browser_server` 的受控 HTTP 回應驗證送出 429 問題、CSV→SQLite 的 H03 結果、工具名稱／參數／完整結果顯示，以及清除對話恢復開場畫面。窄螢幕截圖已視覺檢視；最後 console 無 error/warn。受控 fixture 固定選工具，只證明應用程式連通與呈現，不能證明模型選用能力。

Code-review skill 雙軸審查：Standards 0 項；Spec 初次 1 項（工具內部錯誤後未中止），新增失敗測試重現後修正，複查無剩餘發現。

初次實作時無模型設定，真實模型驗收當時保留待完成。

## 後續真實模型驗收（2026-10-23）

使用者補齊後端 `.env` 後，以真實 Gemini `gemini-3.5-flash-lite` 透過 OpenAI-compatible HTTP 端點執行 FastAPI 聊天 API，沒有替換模型回應或工具。端點與模型顯示名稱經官方文件及帳戶模型清單核對後，於本機設定改成相容端點與 API 模型 ID；未變更金鑰，`.env` 不提交。

- API Key：實際查詢 H01/H02，回覆依 H01 說明申請及保管流程並註明模擬。
- 429：實際查詢 H03，保留速率／額度兩種可能，沒有讀取帳戶用量的宣稱。
- 不存在的火星校區政策：實際工具回 NOT_FOUND，回覆查無且沒有編造政策。
- 旅遊行程：婉拒範圍外問題，trace 為空。
- 學生每日額度：第一次字面查詢 NOT_FOUND，模型換詞查詢取得 H04，回答 20 次；同一 Session 追問教師，取得 H05，回答 40 次，皆標示模擬。
- reset 回 200，舊 Session 後續聊天回 404。

這六輪案例通過本次人工核對，不推論為普遍模型選用正確率。實際結果見 [去除 Session ID 的紀錄](issue-2-live-results.json)。真實模型本輪驗證走 API；瀏覽器呈現證據仍是前述受控模型測試，未宣稱真實模型瀏覽器驗收。
