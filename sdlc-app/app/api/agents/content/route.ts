import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function PUT(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.file || body.content === undefined) {
    return NextResponse.json({ error: "file and content are required" }, { status: 400 });
  }

  // Try backend first
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${backendUrl}/agents/content`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Backend offline — write directly to local filesystem (dev mode only)
  }

  try {
    const agentsDir = path.resolve(process.cwd(), "services", "copilot-agent", "agents");
    const safeFile = path.basename(body.file as string);
    const filePath = path.resolve(agentsDir, safeFile);
    if (!filePath.startsWith(agentsDir + path.sep) && filePath !== agentsDir) {
      return NextResponse.json({ error: "Invalid file path" }, { status: 400 });
    }
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: "Agent file not found" }, { status: 404 });
    }

    // Archive current version locally
    const versionsDir = path.join(agentsDir, "versions");
    fs.mkdirSync(versionsDir, { recursive: true });
    const existing = fs.readdirSync(versionsDir).filter((f) => f.startsWith(safeFile + ".v"));
    const nextV = existing.length + 1;
    fs.copyFileSync(filePath, path.join(versionsDir, `${safeFile}.v${nextV}`));

    fs.writeFileSync(filePath, body.content as string, "utf-8");
    return NextResponse.json({ file: safeFile, version: nextV + 1, archived_as: `versions/${safeFile}.v${nextV}` });
  } catch {
    return NextResponse.json({ error: "Failed to update agent file" }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  const file = request.nextUrl.searchParams.get("file");
  if (!file) {
    return NextResponse.json({ error: "Missing file parameter" }, { status: 400 });
  }

  // Try backend first
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(
      `${backendUrl}/agents/content?file=${encodeURIComponent(file)}`,
      { next: { revalidate: 0 } }
    );
    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }
  } catch {
    // Backend not available — fall through to filesystem fallback
  }

  // Fallback: read agent file directly from the local filesystem
  try {
    const agentsDir = path.resolve(process.cwd(), "services", "copilot-agent", "agents");
    // Guard against path traversal — only the basename is used
    const safeFile = path.basename(file);
    const filePath = path.resolve(agentsDir, safeFile);
    if (!filePath.startsWith(agentsDir + path.sep) && filePath !== agentsDir) {
      return NextResponse.json({ error: "Invalid file path" }, { status: 400 });
    }

    const raw = fs.readFileSync(filePath, "utf-8");

    // Parse YAML frontmatter if present
    const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
    if (fmMatch) {
      const metadata = parseSimpleFrontmatter(fmMatch[1]);
      return NextResponse.json({ file: safeFile, content: fmMatch[2], metadata });
    }

    return NextResponse.json({ file: safeFile, content: raw, metadata: {} });
  } catch {
    return NextResponse.json({ error: "Agent file not found" }, { status: 404 });
  }
}

/** Minimal YAML parser for the known scalar and list fields used in agent files. */
function parseSimpleFrontmatter(yaml: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const lines = yaml.split(/\r?\n/);
  let currentKey: string | null = null;
  let currentList: string[] | null = null;

  for (const line of lines) {
    // List item
    const listItem = line.match(/^\s+-\s+"?(.+?)"?\s*$/);
    if (listItem && currentKey && currentList) {
      currentList.push(listItem[1]);
      continue;
    }

    // Inline list: key: [a, b, c]
    const inlineList = line.match(/^(\w[\w-]*):\s*\[(.+)\]\s*$/);
    if (inlineList) {
      currentKey = inlineList[1];
      currentList = null;
      result[currentKey] = inlineList[2]
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""));
      continue;
    }

    // Key: value
    const kv = line.match(/^(\w[\w-]*):\s*(.+)$/);
    if (kv) {
      currentKey = kv[1];
      currentList = null;
      result[currentKey] = kv[2].replace(/^["']|["']$/g, "").trim();
      continue;
    }

    // Key: (start of block list)
    const blockListKey = line.match(/^(\w[\w-]*):\s*$/);
    if (blockListKey) {
      currentKey = blockListKey[1];
      currentList = [];
      result[currentKey] = currentList;
    }
  }

  return result;
}
