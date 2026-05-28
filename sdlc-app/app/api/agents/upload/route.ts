import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.filename || body.content === undefined) {
    return NextResponse.json({ error: "filename and content are required" }, { status: 400 });
  }

  // Try backend first
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${backendUrl}/agents/upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Backend offline — write directly to local filesystem (dev mode only)
  }

  try {
    const safeFile = path.basename(body.filename as string);
    if (!safeFile.endsWith(".agent.md") && !safeFile.endsWith(".md")) {
      return NextResponse.json({ error: "Filename must end in .agent.md or .md" }, { status: 400 });
    }
    if (["readme.md", "index.md"].includes(safeFile.toLowerCase())) {
      return NextResponse.json({ error: "Cannot upload readme.md or index.md" }, { status: 400 });
    }

    const agentsDir = path.resolve(process.cwd(), "services", "copilot-agent", "agents");
    fs.mkdirSync(agentsDir, { recursive: true });
    const filePath = path.join(agentsDir, safeFile);

    if (fs.existsSync(filePath) && !body.overwrite) {
      return NextResponse.json(
        { error: `Agent '${safeFile}' already exists. Set overwrite=true to replace.` },
        { status: 409 },
      );
    }

    fs.writeFileSync(filePath, body.content as string, "utf-8");
    return NextResponse.json({ file: safeFile, created: true }, { status: 201 });
  } catch {
    return NextResponse.json({ error: "Failed to upload agent file" }, { status: 500 });
  }
}
