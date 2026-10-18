import { describe, expect, it } from "vitest";
import type { Capability } from "./api";
import { catalog, formatBytes, formatDuration, optionValueLabel, outputsFor, relevantOptions } from "./converter";

const caps: Capability[] = [
  { category: "document", input: "docx", output: "pdf", note: null },
  { category: "document", input: "pdf", output: "docx", note: "perde layout" },
  { category: "image", input: "heic", output: "jpg", note: null },
  { category: "image", input: "heic", output: "png", note: null },
  { category: "video", input: "mp4", output: "mp3", note: null },
];

const ALL = {
  resolution: ["original", "720"], quality: ["alta", "media"], fps: ["original", "30"],
  bitrate: ["128k"], sample_rate: ["original"], channels: ["original", "1"],
};

describe("converter helpers", () => {
  it("lists only outputs available for the detected input", () => {
    expect(outputsFor(caps, "heic").map((c) => c.output)).toEqual(["jpg", "png"]);
    expect(outputsFor(caps, "xls")).toEqual([]);
  });

  it("groups and searches the catalog", () => {
    const all = catalog(caps, "");
    expect(Object.keys(all).sort()).toEqual(["document", "image", "video"]);
    expect(catalog(caps, "heic").image).toEqual([{ input: "heic", outputs: ["jpg", "png"] }]);
    expect(catalog(caps, "mp3").video?.[0].input).toBe("mp4"); // matches outputs too
    expect(catalog(caps, "zzz")).toEqual({});
  });

  it("shows only relevant options", () => {
    expect(relevantOptions("video", "mp3", ALL).sort()).toEqual(["bitrate", "channels", "sample_rate"]);
    expect(relevantOptions("video", "mp4", ALL).sort()).toEqual(["fps", "quality", "resolution"]);
    expect(relevantOptions("video", "gif", ALL)).toEqual([]);
    expect(relevantOptions("audio", "flac", { bitrate: ["128k"], channels: ["1"] })).toEqual(["channels"]);
    expect(relevantOptions("image", "png", { quality: ["alta"] })).toEqual([]);
  });

  it("labels values in pt-BR", () => {
    expect(optionValueLabel("bitrate", "192k")).toBe("192 kbps");
    expect(optionValueLabel("channels", "1")).toBe("Mono");
    expect(optionValueLabel("resolution", "720")).toBe("720p");
    expect(optionValueLabel("sample_rate", "44100")).toBe("44,1 kHz");
    expect(optionValueLabel("fps", "original")).toBe("Original");
  });

  it("formats sizes and durations", () => {
    expect(formatBytes(95 * 1024 * 1024)).toBe("95 MB");
    expect(formatBytes(1536)).toBe("1,5 KB");
    expect(formatDuration(600)).toBe("10:00");
    expect(formatDuration(65.4)).toBe("1:05");
  });
});
