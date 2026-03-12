# 在 Cursor 使用本專案的 MCP

本專案可放置多個 MCP 伺服器，方便在 Cursor 內呼叫不同外部服務。

| 目錄 | 說明 |
|------|------|
| `outline/` | Outline Reader MCP：讀取與搜尋 Outline wiki 文件 |
| `hacker-news/` | Hacker News MCP：抓取 HN 熱門（AI/科技，以 Algolia 搜尋，預設 20 則）並翻譯成中文；另可取得過去一週精選 |
| `redmine/` | Redmine MCP：讀取 / 建立 / 更新 Redmine 上的任務（issue），使用個人 API Token 驗證 |

之後若要新增其它 MCP，可在專案根目錄建立新資料夾（例如 `another-mcp/`），各自擁有 `package.json` 或 Python 進入點即可。

---

## 快速開始

1. **選擇要啟用的 MCP**
   - `outline/`：讀取 / 搜尋 Outline 文件。
   - `hacker-news/`：取得 Hacker News AI / 科技熱門與過去一週精選。
   - `redmine/`：讀取 / 建立 / 更新 Redmine issue。

2. **在各子目錄內完成安裝步驟**
   - 依各節「安裝與啟動」或「使用前請先」完成 `npm install` / `pip install` 等準備。

3. **設定 `~/.cursor/mcp.json`**
   - 參考各 MCP 範例，將路徑改為你自己機器上的專案絕對路徑（例如 `/ABSOLUTE/PATH/TO/mcp/...`）。

4. **在 Cursor 內測試**
   - 在 Chat / Composer 中直接下指令，例如：
     - 「用 outline-reader 搜尋關鍵字 XXX」
     - 「用 hacker-news 抓一下今天 HN 熱門並翻譯成中文」
     - 「用 redmine 幫我列出指派給我的 issue」

---

## Outline Reader MCP（`outline/`）

### 已完成的設定

已在 **全域** MCP 設定加入 `outline-reader` 伺服器時，請指向 **outline 目錄**：

- 設定檔位置：`~/.cursor/mcp.json`
- 啟動方式：在專案目錄執行時，需切到 `outline` 再啟動，例如（請將路徑改為你本機的專案絕對路徑）：
  ```bash
  cd /ABSOLUTE/PATH/TO/mcp/outline && node index.js
  ```

### 使用前請先

1. **Build Outline MCP**（若尚未 build）  
   ```bash
   cd outline && npm install && npm run build
   ```

2. **重啟 Cursor 或重新載入 MCP**  
   - 關閉再開啟 Cursor，或  
   - 到 **Cursor Settings → Features → MCP**，對 MCP 清單按重新整理

### 如何測試

1. 在 Cursor 裡開啟 **Composer**（Cmd+I 或 Ctrl+I）或 **Chat**。
2. 在對話中輸入例如：
   - 「用 outline-reader 搜尋關鍵字 XXX」
   - 「請用 get_outline_document 讀取文件 ID：某個-uuid」
3. 若 MCP 連線正常，AI 會使用 `search_outline` 或 `get_outline_document` 工具並回傳結果。

### 可用的 MCP 工具

| 工具名稱 | 說明 |
|----------|------|
| `get_outline_document` | 用文件 ID 取得 Outline 文件內容（Markdown） |
| `search_outline` | 在 Outline 內搜尋文件關鍵字 |

### 環境變數

- `OUTLINE_API_KEY`：**必填**。Outline API 金鑰（於 Outline 設定 → API Keys 建立）；未設則啟動時會報錯並退出。
- `OUTLINE_BASE_URL`：Outline 伺服器網址（未設則需在程式內或設定檔指定）

在 `~/.cursor/mcp.json` 的 `outline-reader` 裡可加 `env`，並將 `args` 改為指向 **outline** 目錄，例如（請將路徑改為你本機的專案絕對路徑）：

```json
"outline-reader": {
  "command": "sh",
  "args": ["-c", "cd /ABSOLUTE/PATH/TO/mcp/outline && node index.js"],
  "env": {
    "OUTLINE_API_KEY": "你的金鑰",
    "OUTLINE_BASE_URL": "https://你的-outline 網址"
  }
}
```

### 若工具沒出現

- 到 **Cursor Settings → Features → MCP** 確認 `outline-reader` 有出現且為啟用。
- 檢查該伺服器是否有錯誤訊息（例如路徑錯誤、`node` 找不到）。
- 確認已在 **outline** 目錄執行過 `npm install` 與 `npm run build`。

---

## Hacker News MCP（`hacker-news/`）

### 功能說明

從 [Hacker News](https://news.ycombinator.com/) 抓取 AI 與科技相關熱門內容（以 [Algolia API](https://hn.algolia.com/) 搜尋），回傳筆數由 `HN_TOP_COUNT` 決定（預設 20 則），標題翻譯成繁體中文。不需 API key；Algolia 失敗時會改以 Firebase API 備援。另提供「過去一週」精選工具。

### 已完成的設定

在 **全域** MCP 設定加入 `hacker-news` 伺服器時，請指向 **hacker-news** 目錄並使用該目錄的 Python 虛擬環境：

- 設定檔位置：`~/.cursor/mcp.json`
- 啟動方式範例（請將路徑改為你本機的專案絕對路徑）：
  ```bash
  cd /ABSOLUTE/PATH/TO/mcp/hacker-news && .venv/bin/python main.py
  ```

### 使用前請先

1. **建立虛擬環境並安裝依賴**
   ```bash
   cd hacker-news && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
   ```

2. **重啟 Cursor 或重新載入 MCP**  
   - 到 **Cursor Settings → Features → MCP** 對 MCP 清單按重新整理

### 如何測試

1. 在 Cursor 裡開啟 **Composer** 或 **Chat**。
2. 在對話中輸入例如：
   - 「用 hacker-news 抓一下今天 HN 熱門並翻譯成中文」
   - 「請呼叫 get_hacker_news_top10 取得 Hacker News 熱門」
   - 「用 get_hacker_news_past_week 取得過去一週重要科技新聞」
3. 若 MCP 連線正常，AI 會使用 `get_hacker_news_top10` 或 `get_hacker_news_past_week` 並回傳已翻譯的精選列表。

### 可用的 MCP 工具

| 工具名稱 | 說明 |
|----------|------|
| `get_hacker_news_top10` | 抓取 HN 熱門（AI/科技，Algolia 搜尋），筆數由 `HN_TOP_COUNT` 決定（預設 20），標題翻譯成繁體中文後回傳（Markdown） |
| `get_hacker_news_past_week` | 抓取過去一週內 AI/科技相關、熱度較高之前 15 則，標題翻譯成繁體中文（Markdown） |

### `~/.cursor/mcp.json` 範例

```json
"hacker-news": {
  "command": "sh",
  "args": ["-c", "cd /ABSOLUTE/PATH/TO/mcp/hacker-news && .venv/bin/python main.py"]
}
```

若要自訂筆數，可加上 `env`，例如回傳 30 則：

```json
"hacker-news": {
  "command": "sh",
  "args": ["-c", "cd /ABSOLUTE/PATH/TO/mcp/hacker-news && .venv/bin/python main.py"],
  "env": { "HN_TOP_COUNT": "30" }
}
```

### 環境變數（可選）

| 變數 | 說明 | 預設 |
|------|------|------|
| `HN_TOP_COUNT` | 回傳的熱門筆數（1～50） | `20` |

（無需 API key；翻譯使用 Google 翻譯，需網路連線。）

### 若工具沒出現

- 到 **Cursor Settings → Features → MCP** 確認 `hacker-news` 有出現且為啟用。
- 確認 `args` 中的路徑為你的專案絕對路徑，且 `hacker-news/.venv` 已建立並安裝過 `requirements.txt`。
- 若翻譯失敗，工具仍會回傳英文標題。

---

## Redmine MCP（`redmine/`）

### 功能說明

串接 `https://redmine.thortron.dev/` 等 Redmine 服務，透過 REST API：

- 讀取指派給自己的任務（issue）
- 建立新的 issue
- 更新既有 issue 的狀態 / 備註 / 標題 / 優先權

### 安裝與啟動

```bash
cd redmine
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### `~/.cursor/mcp.json` 範例

```json
"redmine": {
  "command": "sh",
  "args": [
    "-c",
    "cd /ABSOLUTE/PATH/TO/mcp/redmine && .venv/bin/python main.py"
  ],
  "env": {
    "REDMINE_BASE_URL": "{{PROJECT_BASE_URL}}",
    "REDMINE_API_TOKEN": "{{PROJECT_API_TOKEN}}",
    "REDMINE_PROJECT_IDS": "{{PROJECT_PROJECT_IDS}}",
    "REDMINE_SELF_NAME": "{{PROJECT_SELF_NAME}}"
  }
}
```

### 主要工具

- `get_my_issues(limit: int = 20, include_closed: bool = False)`  
  取得指派給目前 API token 使用者的 issue 列表。

- `create_issue(project_identifier: str, subject: str, description: str | None = None, tracker_id: int | None = None, status_id: int | None = None, priority_id: int | None = None)`  
  在指定專案底下建立新 issue。

- `update_issue(issue_id: int, status_id: int | None = None, notes: str | None = None, subject: str | None = None, priority_id: int | None = None)`  
  更新既有 issue 的狀態 / 備註 / 標題 / 優先權。

---

## 新增其他 MCP 伺服器

1. **建立子目錄**
   - 在專案根目錄下建立新資料夾，例如 `my-mcp/`。

2. **建立對應執行入口**
   - Node.js：建立 `package.json` 與 `index.js` / `dist/index.js` 作為進入點。
   - Python：建立 `main.py`，建議搭配虛擬環境與 `requirements.txt`。

3. **在 `~/.cursor/mcp.json` 新增設定**
   - 以此專案其他 MCP 為範本，將 `command` / `args` 指向該目錄與進入點：
   ```json
   "my-mcp": {
     "command": "sh",
     "args": ["-c", "cd /ABSOLUTE/PATH/TO/mcp/my-mcp && <your-command>"]
   }
   ```

4. **重新載入 MCP**
   - 在 Cursor 中到 **Settings → Features → MCP** 重新整理，或重啟 Cursor，即可在 Chat 中呼叫新 MCP 的工具。
