const prompts = [
  ..."abcdefghijklmnopqrstuvwxyz",
  ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ",
  ..."0123456789",
  "+", "-", "=", "×", "÷", "±", "≠", "<", ">", "≤", "≥",
  "(", ")", "[", "]", "{", "}", "/", "\\", "^", "_",
  ".", ",", ":", ";", "'", "\"", "√", "∑", "∫", "∞", "π", "θ", "Δ"
];

const requiredSamples = new Set(prompts);
const sampleStorageKey = "handwriting-formula-lab.samples.v1";

const state = {
  promptIndex: 0,
  drawing: false,
  samples: new Map(),
  currentStroke: null,
  lastPoint: null,
  generatedFontUrl: null,
  generatedFontName: "PersonalMathHand"
};

const drawCanvas = document.getElementById("drawCanvas");
const drawCtx = drawCanvas.getContext("2d", { willReadFrequently: true });
const previewCanvas = document.getElementById("previewCanvas");
const previewCtx = previewCanvas.getContext("2d");

const els = {
  promptText: document.getElementById("promptText"),
  promptIndex: document.getElementById("promptIndex"),
  sampleCount: document.getElementById("sampleCount"),
  fontState: document.getElementById("fontState"),
  densityMetric: document.getElementById("densityMetric"),
  baselineMetric: document.getElementById("baselineMetric"),
  coverageMetric: document.getElementById("coverageMetric"),
  sentenceInput: document.getElementById("sentenceInput"),
  variationRange: document.getElementById("variationRange"),
  slantRange: document.getElementById("slantRange"),
  spacingRange: document.getElementById("spacingRange"),
  lineRange: document.getElementById("lineRange")
};

function setupCanvas() {
  drawCtx.lineCap = "round";
  drawCtx.lineJoin = "round";
  drawCtx.strokeStyle = "#1f211d";
  drawCtx.lineWidth = 5;
  loadSamples();
  clearCanvas();
  updatePrompt();
  updateStatus();
  renderPreview();
}

function clearCanvas() {
  drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
  drawCtx.fillStyle = "#fbfaf5";
  drawCtx.fillRect(0, 0, drawCanvas.width, drawCanvas.height);
  drawGuides();
  state.currentStroke = null;
  state.lastPoint = null;
}

function resetCurrentSample() {
  const char = prompts[state.promptIndex];
  state.samples.delete(char);
  state.samples.delete(`__draft__${char}`);
  persistSamples();
  clearCanvas();
  updateStatus("현재 샘플 지움");
}

function updatePrompt() {
  els.promptText.textContent = prompts[state.promptIndex];
  els.promptIndex.textContent = `${state.promptIndex + 1} / ${prompts.length}`;
  clearCanvas();
  drawSavedSample(prompts[state.promptIndex]);
}

function drawGuides() {
  drawCtx.save();
  drawCtx.strokeStyle = "rgba(31, 122, 91, 0.08)";
  drawCtx.lineWidth = 1;
  drawCtx.setLineDash([12, 10]);
  drawCtx.strokeRect(drawCanvas.width * 0.447, drawCanvas.height * 0.414, drawCanvas.width * 0.106, drawCanvas.height * 0.172);
  drawCtx.beginPath();
  drawCtx.moveTo(drawCanvas.width * 0.447, drawCanvas.height * 0.434);
  drawCtx.lineTo(drawCanvas.width * 0.553, drawCanvas.height * 0.434);
  drawCtx.moveTo(drawCanvas.width * 0.447, drawCanvas.height * 0.5);
  drawCtx.lineTo(drawCanvas.width * 0.553, drawCanvas.height * 0.5);
  drawCtx.moveTo(drawCanvas.width * 0.447, drawCanvas.height * 0.566);
  drawCtx.lineTo(drawCanvas.width * 0.553, drawCanvas.height * 0.566);
  drawCtx.moveTo(drawCanvas.width * 0.5, drawCanvas.height * 0.414);
  drawCtx.lineTo(drawCanvas.width * 0.5, drawCanvas.height * 0.586);
  drawCtx.stroke();
  drawCtx.restore();
}

function updateStatus(message) {
  els.sampleCount.textContent = `샘플 ${state.samples.size}개`;
  els.fontState.textContent = message || (state.generatedFontUrl ? "TTF 생성됨" : "폰트 대기 중");
  const collected = [...state.samples.keys()].filter((char) => requiredSamples.has(char)).length;
  const coverage = Math.round((collected / requiredSamples.size) * 100);
  els.coverageMetric.textContent = `${coverage}%`;
}

function getCanvasPoint(event) {
  const rect = drawCanvas.getBoundingClientRect();
  const source = event.touches ? event.touches[0] : event;
  return {
    x: ((source.clientX - rect.left) / rect.width) * drawCanvas.width,
    y: ((source.clientY - rect.top) / rect.height) * drawCanvas.height,
    pressure: source.force || (event.pressure && event.pressure > 0 ? event.pressure : 0.55),
    t: performance.now()
  };
}

function startDraw(event) {
  event.preventDefault();
  document.body.classList.add("is-drawing");
  document.getSelection?.().removeAllRanges?.();
  if (event.pointerId !== undefined) drawCanvas.setPointerCapture?.(event.pointerId);
  const point = getCanvasPoint(event);
  state.drawing = true;
  state.currentStroke = [point];
  state.lastPoint = point;
}

function moveDraw(event) {
  if (!state.drawing || !state.currentStroke) return;
  event.preventDefault();
  document.getSelection?.().removeAllRanges?.();
  const events = typeof event.getCoalescedEvents === "function" ? event.getCoalescedEvents() : [event];
  events.forEach((sourceEvent) => appendDrawPoint(sourceEvent));
}

function appendDrawPoint(event) {
  const point = getCanvasPoint(event);
  state.currentStroke.push(point);

  const width = 2.2 + point.pressure * 7;
  drawCtx.lineWidth = width;
  drawCtx.beginPath();
  drawCtx.moveTo(state.lastPoint.x, state.lastPoint.y);
  drawCtx.lineTo(point.x, point.y);
  drawCtx.stroke();
  state.lastPoint = point;
}

function stopDraw() {
  if (!state.drawing || !state.currentStroke) return;
  const sample = getActiveDraftSample();
  if (sample) {
    sample.strokes.push(state.currentStroke);
  }
  state.drawing = false;
  state.currentStroke = null;
  state.lastPoint = null;
  document.body.classList.remove("is-drawing");
}

function getActiveDraftSample() {
  const char = prompts[state.promptIndex];
  if (!state.samples.has(`__draft__${char}`)) {
    state.samples.set(`__draft__${char}`, { char, strokes: [] });
  }
  return state.samples.get(`__draft__${char}`);
}

function saveSample() {
  stopDraw();
  const char = prompts[state.promptIndex];
  const draftKey = `__draft__${char}`;
  const draft = state.samples.get(draftKey);
  if (!draft || !draft.strokes.length) {
    updateStatus("먼저 글자를 작성하세요");
    return;
  }

  state.samples.delete(draftKey);
  state.samples.set(char, {
    char,
    strokes: draft.strokes,
    png: drawCanvas.toDataURL("image/png"),
    metrics: measureCanvasInk()
  });

  persistSamples();
  updateSampleMetrics();
  state.promptIndex = Math.min(prompts.length - 1, state.promptIndex + 1);
  updatePrompt();
  updateStatus("샘플 저장됨");
  clearCanvas();
}

function persistSamples() {
  const samples = [...state.samples.values()].filter((sample) => !String(sample.char).startsWith("__draft__"));
  localStorage.setItem(sampleStorageKey, JSON.stringify(samples));
}

function loadSamples() {
  try {
    const saved = JSON.parse(localStorage.getItem(sampleStorageKey) || "[]");
    saved.forEach((sample) => {
      if (sample?.char && Array.isArray(sample.strokes)) state.samples.set(sample.char, sample);
    });
  } catch {
    localStorage.removeItem(sampleStorageKey);
  }
}

function drawSavedSample(char) {
  const sample = state.samples.get(char);
  if (!sample?.strokes?.length) return;
  drawCtx.save();
  drawCtx.strokeStyle = "#1f211d";
  drawCtx.lineCap = "round";
  drawCtx.lineJoin = "round";
  sample.strokes.forEach((stroke) => {
    for (let index = 1; index < stroke.length; index++) {
      const previous = stroke[index - 1];
      const point = stroke[index];
      drawCtx.lineWidth = 2.2 + (point.pressure || 0.55) * 7;
      drawCtx.beginPath();
      drawCtx.moveTo(previous.x, previous.y);
      drawCtx.lineTo(point.x, point.y);
      drawCtx.stroke();
    }
  });
  drawCtx.restore();
}

function measureCanvasInk() {
  const data = drawCtx.getImageData(0, 0, drawCanvas.width, drawCanvas.height).data;
  let minX = drawCanvas.width;
  let minY = drawCanvas.height;
  let maxX = 0;
  let maxY = 0;
  let count = 0;

  for (let y = 0; y < drawCanvas.height; y += 3) {
    for (let x = 0; x < drawCanvas.width; x += 3) {
      const index = (y * drawCanvas.width + x) * 4;
      const r = data[index];
      const g = data[index + 1];
      const b = data[index + 2];
      if (r + g + b < 650) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
        count++;
      }
    }
  }

  if (!count) return { density: 0, baseline: 0 };
  return {
    density: count / ((drawCanvas.width * drawCanvas.height) / 9),
    baseline: 1 - Math.abs(maxY / drawCanvas.height - 0.76),
    width: maxX - minX,
    height: maxY - minY
  };
}

function updateSampleMetrics() {
  const samples = [...state.samples.values()].filter((sample) => !String(sample.char).startsWith("__draft__"));
  if (!samples.length) return;
  const density = samples.reduce((sum, sample) => sum + (sample.metrics?.density || 0), 0) / samples.length;
  const baseline = samples.reduce((sum, sample) => sum + (sample.metrics?.baseline || 0), 0) / samples.length;
  els.densityMetric.textContent = `${Math.round(Math.min(1, density * 18) * 100)}%`;
  els.baselineMetric.textContent = `${Math.round(Math.max(0, baseline) * 100)}%`;
}

async function generateFontProfile() {
  stopDraw();
  const samples = [...state.samples.values()].filter((sample) => !String(sample.char).startsWith("__draft__"));
  if (!samples.length) {
    updateStatus("저장된 샘플이 필요합니다");
    return;
  }

  updateStatus("TTF 생성 중...");
  const response = await fetch("/api/font", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      familyName: state.generatedFontName,
      canvas: { width: drawCanvas.width, height: drawCanvas.height },
      targetText: els.sentenceInput.value,
      samples: samples.map((sample) => ({
        char: sample.char,
        strokes: sample.strokes
      }))
    })
  });

  if (!response.ok) {
    updateStatus("서버 생성 실패");
    throw new Error(await response.text());
  }

  const blob = await response.blob();
  if (state.generatedFontUrl) URL.revokeObjectURL(state.generatedFontUrl);
  state.generatedFontUrl = URL.createObjectURL(blob);
  const font = new FontFace(state.generatedFontName, `url(${state.generatedFontUrl})`);
  await font.load();
  document.fonts.add(font);

  updateStatus("TTF 생성됨");
  renderPreview();
}

async function importSourceFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  updateStatus("파일 읽는 중...");

  try {
    if (file.type === "text/plain" || file.name.toLowerCase().endsWith(".txt")) {
      els.sentenceInput.value = await file.text();
    } else if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
      const response = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/pdf" },
        body: await file.arrayBuffer()
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      els.sentenceInput.value = result.text || "";
    } else {
      updateStatus("txt 또는 pdf만 지원");
      return;
    }
    updateStatus("파일 입력 완료");
    renderPreview();
  } catch (error) {
    console.error(error);
    updateStatus("파일 읽기 실패");
  } finally {
    event.target.value = "";
  }
}

function exportSamples() {
  const samples = [...state.samples.values()].filter((sample) => !String(sample.char).startsWith("__draft__"));
  const blob = new Blob([JSON.stringify({
    createdAt: new Date().toISOString(),
    canvas: { width: drawCanvas.width, height: drawCanvas.height },
    samples
  }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "handwriting-samples.json";
  link.click();
  URL.revokeObjectURL(url);
}

function seededNoise(seed) {
  const x = Math.sin(seed * 999) * 10000;
  return x - Math.floor(x);
}

function renderPreview() {
  previewCtx.fillStyle = "#fff";
  previewCtx.fillRect(0, 0, previewCanvas.width, previewCanvas.height);

  const text = els.sentenceInput.value || "";
  const marginX = 82;
  let x = marginX;
  let y = 90;
  const fontSize = 16;
  const spacing = Number(els.spacingRange.value);
  const lineHeight = Math.max(22, Number(els.lineRange.value) * 0.38);
  const variation = Number(els.variationRange.value) / 100;
  const slant = Number(els.slantRange.value) / 100;

  previewCtx.fillStyle = "#1f211d";
  previewCtx.textBaseline = "middle";
  previewCtx.textAlign = "left";
  previewCtx.font = state.generatedFontUrl
    ? `${fontSize}px "${state.generatedFontName}", "Bradley Hand", "Comic Sans MS", cursive`
    : `${fontSize}px "Bradley Hand", "Comic Sans MS", cursive`;

  const chars = [...text];
  chars.forEach((char, index) => {
    const nextChar = chars[index + 1] || "";
    const measuredWidth = previewCtx.measureText(char).width || fontSize * 0.5;

    if (char === "\n" || x + measuredWidth > previewCanvas.width - 82) {
      x = marginX;
      y += lineHeight;
      if (char === "\n") return;
    }
    if (char === " ") {
      x += fontSize * 0.42;
      return;
    }

    previewCtx.save();
    const jitterX = (seededNoise(index + 10) - 0.5) * variation * 2;
    const jitterY = (seededNoise(index + 13) - 0.5) * variation * 2.4;
    const rotate = (seededNoise(index + 17) - 0.5) * variation * 0.018;
    previewCtx.translate(x + jitterX, y + jitterY);
    previewCtx.transform(1, 0, slant, 1, 0, 0);
    previewCtx.rotate(rotate);
    previewCtx.fillText(char, 0, 0);
    previewCtx.restore();

    x += measuredWidth + pairSpacing(char, nextChar, spacing);
  });
}

function pairSpacing(char, nextChar, baseSpacing) {
  if (!nextChar || nextChar === "\n") return 0;
  if ("([{".includes(char) || ")]},.;:".includes(nextChar)) return Math.min(1, baseSpacing);
  if ("([{".includes(nextChar) || ")]}".includes(char)) return Math.min(2, baseSpacing);
  if ("^_/".includes(char) || "^_/".includes(nextChar)) return Math.min(1, baseSpacing);
  if ("+-=×÷±≠<>≤≥".includes(char) || "+-=×÷±≠<>≤≥".includes(nextChar)) return Math.max(2, baseSpacing * 0.7);
  if (/[0-9]/.test(char) && /[0-9]/.test(nextChar)) return Math.min(2, baseSpacing);
  return baseSpacing;
}

function drawPaperLines(ctx) {
  ctx.strokeStyle = "rgba(151, 129, 99, 0.16)";
  ctx.lineWidth = 1;
  for (let y = 118; y < previewCanvas.height - 80; y += Number(els.lineRange.value)) {
    ctx.beginPath();
    ctx.moveTo(70, y + 18);
    ctx.lineTo(previewCanvas.width - 70, y + 18);
    ctx.stroke();
  }
}

function downloadPdf() {
  renderPreview();
  const jpeg = previewCanvas.toDataURL("image/jpeg", 0.92);
  const pdfBlob = createImagePdf(jpeg, 595.28, 841.89);
  const url = URL.createObjectURL(pdfBlob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "handwriting-font-lab.pdf";
  link.click();
  URL.revokeObjectURL(url);
}

function createImagePdf(dataUrl, pageWidth, pageHeight) {
  const binary = atob(dataUrl.split(",")[1]);
  const imageBytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) imageBytes[i] = binary.charCodeAt(i);

  const encoder = new TextEncoder();
  const chunks = [];
  const offsets = [0];
  let length = 0;

  function addString(value) {
    const bytes = encoder.encode(value);
    chunks.push(bytes);
    length += bytes.length;
  }

  function addBytes(bytes) {
    chunks.push(bytes);
    length += bytes.length;
  }

  function object(id, body) {
    offsets[id] = length;
    addString(`${id} 0 obj\n${body}\nendobj\n`);
  }

  addString("%PDF-1.4\n");
  object(1, "<< /Type /Catalog /Pages 2 0 R >>");
  object(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
  object(3, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`);

  offsets[4] = length;
  addString(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${previewCanvas.width} /Height ${previewCanvas.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${imageBytes.length} >>\nstream\n`);
  addBytes(imageBytes);
  addString("\nendstream\nendobj\n");

  const content = `q\n${pageWidth} 0 0 ${pageHeight} 0 0 cm\n/Im0 Do\nQ`;
  object(5, `<< /Length ${content.length} >>\nstream\n${content}\nendstream`);

  const xrefOffset = length;
  addString("xref\n0 6\n0000000000 65535 f \n");
  for (let i = 1; i <= 5; i++) {
    addString(`${String(offsets[i]).padStart(10, "0")} 00000 n \n`);
  }
  addString(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`);

  const output = new Uint8Array(length);
  let cursor = 0;
  for (const chunk of chunks) {
    output.set(chunk, cursor);
    cursor += chunk.length;
  }
  return new Blob([output], { type: "application/pdf" });
}

document.getElementById("prevPrompt").addEventListener("click", () => {
  state.promptIndex = Math.max(0, state.promptIndex - 1);
  updatePrompt();
});
document.getElementById("nextPrompt").addEventListener("click", () => {
  state.promptIndex = Math.min(prompts.length - 1, state.promptIndex + 1);
  updatePrompt();
});
document.getElementById("clearCanvas").addEventListener("click", resetCurrentSample);
document.getElementById("saveSample").addEventListener("click", saveSample);
document.getElementById("generateFont").addEventListener("click", generateFontProfile);
document.getElementById("exportSamples").addEventListener("click", exportSamples);
document.getElementById("sourceFile").addEventListener("change", importSourceFile);
document.getElementById("renderPreview").addEventListener("click", renderPreview);
document.getElementById("downloadPdf").addEventListener("click", downloadPdf);

[els.variationRange, els.slantRange, els.spacingRange, els.lineRange, els.sentenceInput].forEach((element) => {
  element.addEventListener("input", renderPreview);
});

if (window.PointerEvent) {
  drawCanvas.addEventListener("pointerdown", startDraw);
  drawCanvas.addEventListener("pointermove", moveDraw);
  window.addEventListener("pointerup", stopDraw);
  window.addEventListener("pointercancel", stopDraw);
} else {
  drawCanvas.addEventListener("mousedown", startDraw);
  drawCanvas.addEventListener("mousemove", moveDraw);
  window.addEventListener("mouseup", stopDraw);
  drawCanvas.addEventListener("touchstart", startDraw, { passive: false });
  drawCanvas.addEventListener("touchmove", moveDraw, { passive: false });
  window.addEventListener("touchend", stopDraw, { passive: false });
  window.addEventListener("touchcancel", stopDraw, { passive: false });
}
document.addEventListener("selectstart", (event) => {
  if (!event.target.closest("textarea")) event.preventDefault();
});
document.addEventListener("dragstart", (event) => {
  if (!event.target.closest("textarea")) event.preventDefault();
});

setupCanvas();
