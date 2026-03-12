# Redmine MCP（`redmine/`）

透過 Redmine REST API 讀取 / 建立 / 更新 issue（task），方便在 Cursor 裡直接操作你的 Thortron Redmine：

- Redmine 網址：`https://redmine.thortron.dev/`
- 透過 `X-Redmine-API-Key` 進行身份驗證

> ⚠️ **注意**：API Token 請放在環境變數中，不要寫進程式碼或 commit。

---

## 功能一覽

- **`get_my_issues`**：列出目前「指派給我」的任務（可選擇是否包含已關閉）
- **`create_issue`**：在指定專案底下建立新的 issue
- **`update_issue`**：更新既有 issue 的狀態 / 標題 / 優先權 / 備註

---

## 安裝與啟動

在 `redmine/` 目錄下建立虛擬環境並安裝依賴：

```bash
cd redmine
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

啟動 MCP server（本機測試）：

```bash
cd /Users/chu-cheng-yang/cases/mcp/redmine
.venv/bin/python main.py
```

實際由 Cursor 啟動時，會由 `~/.cursor/mcp.json` 的設定來執行。

---

## 環境變數設定

Redmine 的 domain 與 token 都放在環境變數中，以便每個人用自己的帳號與權限：

| 變數名稱 | 說明 | 範例 |
|----------|------|------|
| `REDMINE_BASE_URL` | Redmine 伺服器的 base URL | `https://redmine.thortron.dev` |
| `REDMINE_API_TOKEN` | 你的 Redmine API Token（個人金鑰） | `xxxxxxxxxxxxxxxxxxxx` |

### 在 `~/.cursor/mcp.json` 中設定

範例設定（請把路徑換成你自己的絕對路徑，token 換成自己的）：

```json
"redmine": {
  "command": "sh",
  "args": [
    "-c",
    "cd /Users/chu-cheng-yang/cases/mcp/redmine && .venv/bin/python main.py"
  ],
  "env": {
    "REDMINE_BASE_URL": "{{PROJECT_BASE_URL}}",
    "REDMINE_API_TOKEN": "{{PROJECT_API_TOKEN}}",
    "REDMINE_PROJECT_IDS": "{{PROJECT_PROJECT_IDS}}",
    "REDMINE_SELF_NAME": "{{PROJECT_SELF_NAME}}"
  }
}
```

---

## 可用工具詳解

### `get_my_issues`

**說明**：取得目前「指派給我」的 Redmine 任務列表，預設只顯示未結案的 issue。

**參數**：

- `limit: int = 20`：最多回傳幾筆（1～100）
- `include_closed: bool = False`：是否包含已關閉任務

**輸出**：Markdown 文字，包含 issue 編號、標題、狀態、專案與連結。

**使用範例（在 Cursor Chat 中對我說）**：

- 「幫我用 redmine 的 `get_my_issues` 看一下我現在的 task」
- 「請呼叫 `get_my_issues`，把已關閉的也列出來」

---

### `create_issue`

**說明**：在指定專案底下建立新的 issue（task）。

**參數**：

- `project_identifier: str`：專案識別碼（Redmine 專案的 `identifier`，例如 `backend`, `infra`）
- `subject: str`：標題
- `description: str | None = None`：描述（可省略）
- `tracker_id: int | None = None`：tracker ID（如 1: Bug, 2: Feature，依你系統設定）
- `status_id: int | None = None`：初始狀態 ID
- `priority_id: int | None = None`：優先權 ID

**輸出**：建立成功後，會回傳一段 Markdown，顯示該 issue 的重要欄位與網頁連結。

**使用範例（語意指令）**：

- 「幫我在 Redmine 建一個 `backend` 專案的新 task，標題是 xxx，內容是 yyy」
- 「在 `infra` 專案建立一個高優先權的 issue，tracker 是 Feature」

---

### `update_issue`

**說明**：更新既有的 issue，例如改狀態、補 notes 或調整優先級。

**參數**：

- `issue_id: int`：要更新的 issue 編號
- `status_id: int | None = None`：新的狀態 ID（例如 2: In Progress, 3: Resolved）
- `notes: str | None = None`：備註文字
- `subject: str | None = None`：新的標題
- `priority_id: int | None = None`：新的優先權 ID

**限制**：至少要提供一個要更新的欄位（`status_id` / `notes` / `subject` / `priority_id`）。

**輸出**：更新成功後會回傳簡要變更摘要與 issue 連結。

**使用範例**：

- 「把 Redmine 上 #12345 的狀態改成 In Progress，並加一段備註說我已經開始處理」
- 「把 #67890 的優先權調高，並更新標題」

---

## 在 Cursor 裡實際使用

1. 完成上述的虛擬環境與 `~/.cursor/mcp.json` 設定。
2. 重新啟動 Cursor，或在 **Settings → Features → MCP** 裡重新整理。
3. 開啟 Chat / Composer，直接用自然語言請 AI：
   - 「幫我用 redmine MCP 查看我今天的 task」
   - 「請用 redmine 建一個新的 task 給自己」
   - 「更新這個 issue 的狀態為已完成並加個備註」

如果設定沒問題，AI 會自動選擇 `redmine` MCP 的工具來呼叫 Redmine API。
