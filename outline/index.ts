import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// 設定 Outline 資訊（self-hosted：Settings → API Keys 建立金鑰；BASE_URL 為瀏覽器開啟 Outline 的網址）
const OUTLINE_API_KEY = process.env.OUTLINE_API_KEY?.trim() ?? "";
const OUTLINE_BASE_URL = (process.env.OUTLINE_BASE_URL ?? "").trim().replace(/\/$/, "");
const OUTLINE_API_PATH_PREFIX = "api";

if (!OUTLINE_API_KEY) {
  console.error("請設定環境變數 OUTLINE_API_KEY（於 Outline 設定 → API Keys 建立）");
  process.exit(1);
}

/** Outline API 單一文件（documents.info 回傳的 data） */
interface OutlineDocument {
  id: string;
  title?: string;
  text?: string;
  content?: string;
  [key: string]: unknown;
}

/** Outline API 成功回應 */
interface OutlineSuccessResponse<T> {
  ok: true;
  data: T;
}

/** Outline API 錯誤回應 */
interface OutlineErrorResponse {
  ok: false;
  error: string;
}

type OutlineApiResponse<T> = OutlineSuccessResponse<T> | OutlineErrorResponse;

/** 搜尋結果中的項目（documents.search 的 data 陣列元素） */
interface OutlineSearchHit {
  document: { id: string; title?: string; [key: string]: unknown };
  [key: string]: unknown;
}

const server = new McpServer(
  { name: "outline-reader", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// 1. 註冊工具：讓 AI 知道可以「讀取文件」與「搜尋文件」
server.registerTool(
  "get_outline_document",
  {
    description: "透過 ID 獲取 Outline 文件的內容（Markdown 格式）",
    inputSchema: { id: z.string().describe("文件的 UUID") }
  },
  async (args) => {
    const id = args?.id != null ? String(args.id).trim() : "";
    if (!id) {
      return {
        content: [{ type: "text", text: "錯誤：請提供文件 id 參數。" }],
        isError: true
      };
    }
    const result = await outlineFetch<OutlineDocument>("documents.info", { id });
    if (!result.ok) {
      return {
        content: [{ type: "text", text: `Outline API 錯誤：${result.error}` }],
        isError: true
      };
    }
    const doc = result.data;
    const text = doc?.text ?? doc?.content ?? "";
    const title = doc?.title ? `# ${doc.title}\n\n` : "";
    const body = text || "（此文件無文字內容）";
    return {
      content: [{ type: "text", text: `${title}${body}`.trim() }]
    };
  }
);

server.registerTool(
  "search_outline",
  {
    description: "搜尋 Outline 內的文件關鍵字",
    inputSchema: { query: z.string().describe("關鍵字") }
  },
  async (args) => {
    const query = args?.query != null ? String(args.query).trim() : "";
    if (!query) {
      return {
        content: [{ type: "text", text: "錯誤：請提供 query 參數。" }],
        isError: true
      };
    }
    const result = await outlineFetch<OutlineSearchHit[]>("documents.search", { query });
    if (!result.ok) {
      return {
        content: [{ type: "text", text: `Outline API 錯誤：${result.error}` }],
        isError: true
      };
    }
    const list = Array.isArray(result.data) ? result.data : [];
    const lines = list.map(
      (hit) => `[${hit.document?.title ?? "無標題"}] ID: ${hit.document?.id ?? ""}`
    );
    return {
      content: [{ type: "text", text: lines.length > 0 ? lines.join("\n") : "找不到相關結果" }]
    };
  }
);

/** 呼叫 Outline API 並處理錯誤（路徑格式：{BASE_URL}/api/{method}） */
async function outlineFetch<T>(method: string, body: Record<string, unknown>): Promise<OutlineApiResponse<T>> {
  const url = `${OUTLINE_BASE_URL}/${OUTLINE_API_PATH_PREFIX}/${method}`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OUTLINE_API_KEY}`,
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: JSON.stringify(body)
  });

  const raw = (await response.json().catch(() => ({}))) as { ok?: boolean; error?: string; data?: T };

  if (!response.ok) {
    const err = typeof raw?.error === "string" ? raw.error : `HTTP ${response.status}`;
    return { ok: false, error: err };
  }

  if (raw?.ok === false && typeof raw.error === "string") {
    return { ok: false, error: raw.error };
  }

  return { ok: true, data: raw.data as T };
}

const transport = new StdioServerTransport();
await server.connect(transport);
