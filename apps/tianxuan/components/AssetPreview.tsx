"use client";

import { useEffect, useRef, useState } from "react";
import { authHeaders } from "@/lib/auth";

export type ReviewAsset = { kind: "concept" | "model"; module: string; revision: string; path: string; digest: string; decision: string };

export function objectPath(asset: ReviewAsset) {
  const path = asset.path.split("/").map(encodeURIComponent).join("/");
  return "/api/v1/native/modules/" + encodeURIComponent(asset.module) + "/revisions/" + encodeURIComponent(asset.revision) + "/objects/" + path;
}

const previewLimit = 32 * 1024 * 1024;

// Read only bounded bytes even if a proxy omits Content-Length.
async function previewBytes(response: Response) {
  if (!response.ok) throw Error("读取修订失败（" + response.status + "）");
  const reader = response.body?.getReader();
  if (!reader) throw Error("无法读取预览数据");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > previewLimit) {
        await reader.cancel();
        throw Error("文件超过 32 MiB 预览上限");
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}

function checkPng(bytes: Uint8Array) {
  const data = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (data.byteLength < 33 || data.getUint32(0) !== 0x89504e47 || data.getUint32(4) !== 0x0d0a1a0a ||
      data.getUint32(8) !== 13 || data.getUint32(12) !== 0x49484452) throw Error("文件缺少有效的 PNG 图像头");
  const pixels = data.getUint32(16) * data.getUint32(20);
  if (!pixels || pixels > 16_777_216) throw Error("图像尺寸超出预览范围");
}

function checkGlb(bytes: Uint8Array) {
  const data = new DataView(bytes.buffer);
  if (data.byteLength < 28 || data.getUint32(0, true) !== 0x46546c67 || data.getUint32(4, true) !== 2 ||
      data.getUint32(8, true) !== data.byteLength || data.getUint32(16, true) !== 0x4e4f534a) throw Error("文件缺少有效的 GLB 2.0 模型头");
  const jsonEnd = 20 + data.getUint32(12, true);
  if (jsonEnd > 4 * 1024 * 1024 || jsonEnd + 8 > bytes.length || data.getUint32(jsonEnd + 4, true) !== 0x004e4942 ||
      jsonEnd + 8 + data.getUint32(jsonEnd, true) !== bytes.length) throw Error("模型需要内嵌几何数据");
  const gltf = JSON.parse(new TextDecoder().decode(bytes.subarray(20, jsonEnd)), (key, value) => {
    if (key === "uri" || key === "extensions" && Object.keys(value).length) {
      throw Error("此模型包含外部资源或扩展，请下载查看");
    }
    return value;
  });
  if (gltf.asset?.version !== "2.0" || gltf.buffers?.length !== 1 || !gltf.meshes?.length ||
      gltf.extensionsRequired?.length || gltf.extensionsUsed?.length) throw Error("预览支持标准自包含 GLB 2.0 网格");
  if (!Array.isArray(gltf.accessors) || gltf.accessors.some((a: {count: number}) => !Number.isSafeInteger(a.count) || a.count < 1 || a.count > 2_000_000)) throw Error("模型几何数据超出预览范围");
}

export function AssetPreview({ asset, actor }: { asset: ReviewAsset; actor: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const {kind, digest, path} = asset;
  const source = objectPath(asset);
  useEffect(() => {
    const controller = new AbortController();
    const target = host.current;
    let url = "";
    setError("");
    setReady(false);
    async function show() {
      if (!target) return;
      const response = await fetch(source, { headers: authHeaders(actor), signal: controller.signal, cache: "no-store", redirect: "error" });
      const bytes = await previewBytes(response);
      const hash = await crypto.subtle.digest("SHA-256", bytes);
      if (Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, "0")).join("") !== digest) throw Error("资产摘要与提交记录不符");
      let media: HTMLElement;
      const isImage = kind === "concept";
      if (isImage) {
        checkPng(bytes);
        media = document.createElement("img");
        media.setAttribute("alt", "概念图 " + path);
      } else {
        checkGlb(bytes);
        await import("@google/model-viewer");
        media = document.createElement("model-viewer");
        media.setAttribute("camera-controls", "");
        media.setAttribute("loading", "eager");
        media.setAttribute("alt", "三维模型 " + path);
      }
      if (controller.signal.aborted) return;
      media.addEventListener("load", () => setReady(true), {signal:controller.signal});
      media.addEventListener("error", () => setError("浏览器无法显示此修订，可下载核对"), {signal:controller.signal});
      url = URL.createObjectURL(new Blob([bytes], { type: isImage ? "image/png" : "model/gltf-binary" }));
      media.setAttribute("src", url);
      target.replaceChildren(media);
    }
    show().catch(reason => { if (!controller.signal.aborted) setError(String(reason)); });
    return () => { controller.abort(); target?.replaceChildren(); if (url) URL.revokeObjectURL(url); };
  }, [actor, kind, digest, path, source, attempt]);
  return <div><div ref={host} aria-label="固定修订预览" />
    <p role="status">{error || (!ready ? "正在读取固定修订…" : "")}</p>
    {error && <button type="button" onClick={() => setAttempt(n => n + 1)}>重试预览</button>}
  </div>;
}
