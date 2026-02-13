# 在 Cursor 使用 Outline Reader MCP

## 已完成的設定

已在 **全域** MCP 設定加入 `outline-reader` 伺服器：

- 設定檔位置：`~/.cursor/mcp.json`
- 啟動方式：在專案目錄執行 `node index.js`（使用絕對路徑以確保任何工作區都能連到）

## 使用前請先

1. **Build 專案**（若尚未 build）  
   ```bash
   npm run build
   ```

2. **重啟 Cursor 或重新載入 MCP**  
   - 關閉再開啟 Cursor，或  
   - 到 **Cursor Settings → Features → MCP**，對 MCP 清單按重新整理

## 如何測試

1. 在 Cursor 裡開啟 **Composer**（Cmd+I 或 Ctrl+I）或 **Chat**。
2. 在對話中輸入例如：
   - 「用 outline-reader 搜尋關鍵字 XXX」
   - 「請用 get_outline_document 讀取文件 ID：某個-uuid」
3. 若 MCP 連線正常，AI 會使用 `search_outline` 或 `get_outline_document` 工具並回傳結果。

## 可用的 MCP 工具

| 工具名稱 | 說明 |
|----------|------|
| `get_outline_document` | 用文件 ID 取得 Outline 文件內容（Markdown） |
| `search_outline` | 在 Outline 內搜尋文件關鍵字 |

## 環境變數（可選）

- `OUTLINE_API_KEY`：Outline API 金鑰（未設則用程式內預設）
- `OUTLINE_BASE_URL`：Outline 伺服器網址（未設則用程式內預設）

在 `~/.cursor/mcp.json` 的 `outline-reader` 裡可加 `env`，例如：

```json
"outline-reader": {
  "command": "sh",
  "args": ["-c", "cd /Users/chu-cheng-yang/cases/mcp && node index.js"],
  "env": {
    "OUTLINE_API_KEY": "你的金鑰",
    "OUTLINE_BASE_URL": "https://你的-outline 網址"
  }
}
```

## 若工具沒出現

- 到 **Cursor Settings → Features → MCP** 確認 `outline-reader` 有出現且為啟用。
- 檢查該伺服器是否有錯誤訊息（例如路徑錯誤、`node` 找不到）。
- 確認已在此目錄執行過 `npm install` 與 `npm run build`。
